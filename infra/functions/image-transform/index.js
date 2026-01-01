/**
 * Image Transform Lambda@Edge Handler
 *
 * Parses Thumbor-compatible URLs for on-the-fly image resizing.
 * This Lambda runs at CloudFront edge locations as an Origin Request handler.
 *
 * URL Format:
 * - /{width}x{height}/{key} - Resize to exact dimensions
 * - /fit-in/{width}x{height}/{key} - Fit within dimensions (maintain aspect ratio)
 * - /cover/{width}x{height}/{key} - Cover dimensions (crop to fill)
 * - /contain/{width}x{height}/{key} - Contain within dimensions
 *
 * Example: /fit-in/200x300/avatars/1/photo.png
 *
 * Note: For production with actual image transformation,
 * add Sharp as a Lambda layer or bundle it with the deployment.
 */

/**
 * Regex pattern for parsing transform URLs.
 *
 * Groups:
 * 1. fit mode: "fit-in", "cover", or "contain" (optional)
 * 2. width: numeric dimension
 * 3. height: numeric dimension
 * 4. key: original S3 object key
 */
const TRANSFORM_URL_PATTERN = /^\/(fit-in|cover|contain)?\/?(\d+)x(\d+)\/(.+)$/;

/** Maximum allowed dimension to prevent abuse (4K resolution) */
const MAX_DIMENSION = 4096;
/** Minimum allowed dimension */
const MIN_DIMENSION = 1;

/**
 * Validate that dimensions are positive integers within reasonable bounds.
 *
 * @param {string} width - Width as string
 * @param {string} height - Height as string
 * @returns {{ valid: boolean, width?: number, height?: number, error?: string }}
 */
function validateDimensions(width, height) {
    const w = parseInt(width, 10);
    const h = parseInt(height, 10);

    if (isNaN(w) || isNaN(h)) {
        return { valid: false, error: 'Invalid dimensions: not a number' };
    }

    if (w < MIN_DIMENSION || h < MIN_DIMENSION) {
        return { valid: false, error: `Dimensions must be at least ${MIN_DIMENSION}px` };
    }

    if (w > MAX_DIMENSION || h > MAX_DIMENSION) {
        return { valid: false, error: `Dimensions must not exceed ${MAX_DIMENSION}px` };
    }

    return { valid: true, width: w, height: h };
}

/**
 * Parse transformation parameters from URI.
 *
 * @param {string} uri - The request URI
 * @returns {object|null} Parsed params or null if not a transform URL
 */
function parseTransformUri(uri) {
    const match = uri.match(TRANSFORM_URL_PATTERN);
    if (!match) return null;

    const [, fit, width, height, key] = match;
    return { fit: fit || null, width, height, key };
}

/**
 * CloudFront Origin Request handler.
 *
 * @param {object} event - CloudFront event object
 * @returns {object} Modified request object or error response
 */
exports.handler = async (event) => {
    try {
        const request = event.Records[0].cf.request;
        const uri = request.uri;

        const params = parseTransformUri(uri);

        if (!params) {
            // No transformation requested, pass through
            return request;
        }

        // Validate dimensions
        const validation = validateDimensions(params.width, params.height);
        if (!validation.valid) {
            // Return 400 Bad Request for invalid dimensions
            return {
                status: '400',
                statusDescription: 'Bad Request',
                headers: {
                    'content-type': [{ key: 'Content-Type', value: 'text/plain' }],
                },
                body: validation.error,
            };
        }

        // Rewrite URI to original image
        request.uri = '/' + params.key;

        // Store transform params (as validated numbers) in custom headers
        request.headers['x-transform-width'] = [{ key: 'X-Transform-Width', value: String(validation.width) }];
        request.headers['x-transform-height'] = [{ key: 'X-Transform-Height', value: String(validation.height) }];
        if (params.fit) {
            request.headers['x-transform-fit'] = [{ key: 'X-Transform-Fit', value: params.fit }];
        }

        return request;
    } catch (err) {
        // Log error for debugging (CloudWatch)
        console.error('Image transform handler error:', err);

        // Return 500 for unexpected errors
        return {
            status: '500',
            statusDescription: 'Internal Server Error',
            headers: {
                'content-type': [{ key: 'Content-Type', value: 'text/plain' }],
            },
            body: 'Image transformation error',
        };
    }
};

// Export for testing
exports.parseTransformUri = parseTransformUri;
exports.validateDimensions = validateDimensions;
exports.TRANSFORM_URL_PATTERN = TRANSFORM_URL_PATTERN;
exports.MAX_DIMENSION = MAX_DIMENSION;
exports.MIN_DIMENSION = MIN_DIMENSION;
