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
 * @returns {object} Modified request object
 */
exports.handler = async (event) => {
    const request = event.Records[0].cf.request;
    const uri = request.uri;

    const params = parseTransformUri(uri);

    if (!params) {
        // No transformation requested, pass through
        return request;
    }

    // Rewrite URI to original image
    request.uri = '/' + params.key;

    // Store transform params in custom headers for origin response Lambda
    request.headers['x-transform-width'] = [{ key: 'X-Transform-Width', value: params.width }];
    request.headers['x-transform-height'] = [{ key: 'X-Transform-Height', value: params.height }];
    if (params.fit) {
        request.headers['x-transform-fit'] = [{ key: 'X-Transform-Fit', value: params.fit }];
    }

    return request;
};

// Export for testing
exports.parseTransformUri = parseTransformUri;
exports.TRANSFORM_URL_PATTERN = TRANSFORM_URL_PATTERN;
