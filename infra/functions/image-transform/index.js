/**
 * Image Transform Lambda@Edge Handler
 *
 * Performs on-the-fly image resizing using Sharp.
 * This Lambda runs at CloudFront edge locations as an Origin Response handler.
 *
 * URL Format:
 * - /{width}x{height}/{key} - Resize to exact dimensions
 * - /fit-in/{width}x{height}/{key} - Fit within dimensions (maintain aspect ratio)
 * - /cover/{width}x{height}/{key} - Cover dimensions (crop to fill)
 * - /contain/{width}x{height}/{key} - Contain within dimensions
 *
 * Example: /fit-in/200x300/avatars/1/photo.png
 */

const { S3Client, GetObjectCommand } = require('@aws-sdk/client-s3');
const sharp = require('sharp');

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

/** Supported output formats */
const SUPPORTED_FORMATS = ['jpeg', 'png', 'webp', 'avif'];

/** Map file extensions to Sharp format names */
const EXTENSION_TO_FORMAT = {
    '.jpg': 'jpeg',
    '.jpeg': 'jpeg',
    '.png': 'png',
    '.webp': 'webp',
    '.avif': 'avif',
};

/** Map fit modes to Sharp fit options */
const FIT_MODE_MAP = {
    'fit-in': 'inside',
    'cover': 'cover',
    'contain': 'contain',
    'default': 'fill', // Default: exact resize
};

// Lazy-initialized S3 client (reused across invocations)
let s3Client = null;

/**
 * Get or create S3 client.
 * Uses environment variable for bucket region.
 */
function getS3Client(region) {
    if (!s3Client) {
        s3Client = new S3Client({ region: region || 'us-east-1' });
    }
    return s3Client;
}

/**
 * Validate that dimensions are positive integers within reasonable bounds.
 * Uses strict parsing to reject values like '123abc'.
 *
 * @param {string} width - Width as string
 * @param {string} height - Height as string
 * @returns {{ valid: boolean, width?: number, height?: number, error?: string }}
 */
function validateDimensions(width, height) {
    const w = Number(width);
    const h = Number(height);

    if (Number.isNaN(w) || Number.isNaN(h)) {
        return { valid: false, error: 'Invalid dimensions: not a number' };
    }

    if (!Number.isInteger(w) || !Number.isInteger(h)) {
        return { valid: false, error: 'Invalid dimensions: must be integers' };
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
 * Get output format from file extension.
 *
 * @param {string} key - S3 object key
 * @returns {string} Sharp format name
 */
function getOutputFormat(key) {
    const ext = key.substring(key.lastIndexOf('.')).toLowerCase();
    return EXTENSION_TO_FORMAT[ext] || 'jpeg';
}

/**
 * Create error response.
 *
 * @param {string} status - HTTP status code
 * @param {string} message - Error message
 * @returns {object} CloudFront response object
 */
function errorResponse(status, message) {
    return {
        status,
        statusDescription: status === '400' ? 'Bad Request' : 'Internal Server Error',
        headers: {
            'content-type': [{ key: 'Content-Type', value: 'text/plain' }],
            'cache-control': [{ key: 'Cache-Control', value: 'no-store' }],
        },
        body: message,
    };
}

/**
 * CloudFront Origin Response handler.
 *
 * This function intercepts responses from S3 origin, transforms images
 * if requested, and returns the transformed image.
 *
 * @param {object} event - CloudFront event object
 * @returns {object} Modified response with transformed image
 */
exports.handler = async (event) => {
    try {
        const request = event.Records[0].cf.request;
        const response = event.Records[0].cf.response;
        const uri = request.uri;

        // Parse transform parameters from original request URI
        // Note: request.uri has already been rewritten if using Origin Request
        // We need to check the original path from custom headers or use Origin Response
        const transformWidth = request.headers['x-transform-width']?.[0]?.value;
        const transformHeight = request.headers['x-transform-height']?.[0]?.value;
        const transformFit = request.headers['x-transform-fit']?.[0]?.value || null;

        // If no transform headers, this is a passthrough request
        if (!transformWidth || !transformHeight) {
            return response;
        }

        // If origin returned an error, pass it through
        if (response.status !== '200') {
            return response;
        }

        // Validate dimensions
        const validation = validateDimensions(transformWidth, transformHeight);
        if (!validation.valid) {
            return errorResponse('400', validation.error);
        }

        // Get S3 bucket and key from the request
        const s3Domain = request.origin?.s3?.domainName;
        if (!s3Domain) {
            console.error('No S3 origin domain found');
            return response;
        }

        // Extract bucket name from domain (format: bucket-name.s3.region.amazonaws.com)
        const bucketMatch = s3Domain.match(/^([^.]+)\.s3\.([^.]+)\.amazonaws\.com$/);
        if (!bucketMatch) {
            console.error('Could not parse S3 domain:', s3Domain);
            return response;
        }

        const bucketName = bucketMatch[1];
        const region = bucketMatch[2];
        const objectKey = uri.startsWith('/') ? uri.slice(1) : uri;

        // Fetch original image from S3
        const s3 = getS3Client(region);
        const getCommand = new GetObjectCommand({
            Bucket: bucketName,
            Key: objectKey,
        });

        let originalImage;
        try {
            const s3Response = await s3.send(getCommand);
            originalImage = await s3Response.Body.transformToByteArray();
        } catch (err) {
            console.error('Failed to fetch from S3:', err);
            return response; // Return original response on S3 error
        }

        // Determine output format
        const outputFormat = getOutputFormat(objectKey);

        // Skip transformation for SVG (Sharp doesn't handle SVG output)
        if (objectKey.toLowerCase().endsWith('.svg')) {
            return response;
        }

        // Transform image using Sharp
        const sharpFit = FIT_MODE_MAP[transformFit] || FIT_MODE_MAP['default'];
        let transformer = sharp(Buffer.from(originalImage))
            .resize(validation.width, validation.height, {
                fit: sharpFit,
                withoutEnlargement: true, // Don't upscale small images
            });

        // Apply format-specific optimizations
        switch (outputFormat) {
            case 'jpeg':
                transformer = transformer.jpeg({ quality: 85, progressive: true });
                break;
            case 'png':
                transformer = transformer.png({ compressionLevel: 8 });
                break;
            case 'webp':
                transformer = transformer.webp({ quality: 85 });
                break;
            case 'avif':
                transformer = transformer.avif({ quality: 80 });
                break;
        }

        const transformedBuffer = await transformer.toBuffer();

        // Return transformed image
        const contentTypeMap = {
            jpeg: 'image/jpeg',
            png: 'image/png',
            webp: 'image/webp',
            avif: 'image/avif',
        };

        return {
            status: '200',
            statusDescription: 'OK',
            headers: {
                'content-type': [{ key: 'Content-Type', value: contentTypeMap[outputFormat] }],
                'cache-control': [{ key: 'Cache-Control', value: 'public, max-age=31536000' }],
                'x-transformed': [{ key: 'X-Transformed', value: 'true' }],
            },
            body: transformedBuffer.toString('base64'),
            bodyEncoding: 'base64',
        };
    } catch (err) {
        console.error('Image transform handler error:', err);
        return errorResponse('500', 'Image transformation error');
    }
};

/**
 * Origin Request handler for URL rewriting.
 *
 * This function runs before S3 origin request to:
 * 1. Parse transform URL and extract original key
 * 2. Store transform params in headers for Origin Response
 * 3. Rewrite URI to fetch original image
 *
 * @param {object} event - CloudFront event object
 * @returns {object} Modified request with rewritten URI
 */
exports.originRequestHandler = async (event) => {
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
            return errorResponse('400', validation.error);
        }

        // Rewrite URI to original image
        request.uri = '/' + params.key;

        // Store transform params in headers for Origin Response handler
        request.headers['x-transform-width'] = [{ key: 'X-Transform-Width', value: String(validation.width) }];
        request.headers['x-transform-height'] = [{ key: 'X-Transform-Height', value: String(validation.height) }];
        if (params.fit) {
            request.headers['x-transform-fit'] = [{ key: 'X-Transform-Fit', value: params.fit }];
        }

        return request;
    } catch (err) {
        console.error('Origin request handler error:', err);
        return errorResponse('500', 'Image transformation error');
    }
};

// Export for testing
exports.parseTransformUri = parseTransformUri;
exports.validateDimensions = validateDimensions;
exports.getOutputFormat = getOutputFormat;
exports.TRANSFORM_URL_PATTERN = TRANSFORM_URL_PATTERN;
exports.MAX_DIMENSION = MAX_DIMENSION;
exports.MIN_DIMENSION = MIN_DIMENSION;
exports.FIT_MODE_MAP = FIT_MODE_MAP;
