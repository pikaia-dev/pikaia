import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
    parseTransformUri,
    validateDimensions,
    getOutputFormat,
    TRANSFORM_URL_PATTERN,
    MAX_DIMENSION,
    MIN_DIMENSION,
    FIT_MODE_MAP,
} from '../index.js';

// Mock AWS SDK and Sharp for handler tests
vi.mock('@aws-sdk/client-s3', () => ({
    S3Client: vi.fn(() => ({
        send: vi.fn(),
    })),
    GetObjectCommand: vi.fn(),
}));

vi.mock('sharp', () => ({
    default: vi.fn(() => ({
        resize: vi.fn().mockReturnThis(),
        jpeg: vi.fn().mockReturnThis(),
        png: vi.fn().mockReturnThis(),
        webp: vi.fn().mockReturnThis(),
        avif: vi.fn().mockReturnThis(),
        toBuffer: vi.fn().mockResolvedValue(Buffer.from('transformed')),
    })),
}));

/**
 * Create a mock CloudFront Origin Request event.
 */
function mockCloudFrontRequest(uri, headers = {}) {
    return {
        Records: [
            {
                cf: {
                    request: {
                        uri,
                        headers,
                        origin: {
                            s3: {
                                domainName: 'test-bucket.s3.us-east-1.amazonaws.com',
                            },
                        },
                    },
                },
            },
        ],
    };
}

/**
 * Create a mock CloudFront Origin Response event.
 */
function mockCloudFrontResponse(uri, status = '200', headers = {}) {
    return {
        Records: [
            {
                cf: {
                    request: {
                        uri,
                        headers,
                        origin: {
                            s3: {
                                domainName: 'test-bucket.s3.us-east-1.amazonaws.com',
                            },
                        },
                    },
                    response: {
                        status,
                        statusDescription: status === '200' ? 'OK' : 'Error',
                        headers: {},
                    },
                },
            },
        ],
    };
}

describe('TRANSFORM_URL_PATTERN', () => {
    it('matches basic resize URL', () => {
        expect('/200x300/avatars/1/photo.png').toMatch(TRANSFORM_URL_PATTERN);
    });

    it('matches fit-in URL', () => {
        expect('/fit-in/200x300/avatars/1/photo.png').toMatch(TRANSFORM_URL_PATTERN);
    });

    it('matches cover URL', () => {
        expect('/cover/200x300/avatars/1/photo.png').toMatch(TRANSFORM_URL_PATTERN);
    });

    it('matches contain URL', () => {
        expect('/contain/200x300/avatars/1/photo.png').toMatch(TRANSFORM_URL_PATTERN);
    });

    it('does not match plain path', () => {
        expect('/avatars/1/photo.png').not.toMatch(TRANSFORM_URL_PATTERN);
    });

    it('does not match invalid dimensions', () => {
        expect('/abcxdef/avatars/1/photo.png').not.toMatch(TRANSFORM_URL_PATTERN);
    });
});

describe('parseTransformUri', () => {
    it('parses basic resize URL', () => {
        const result = parseTransformUri('/200x300/avatars/1/photo.png');
        expect(result).toEqual({
            fit: null,
            width: '200',
            height: '300',
            key: 'avatars/1/photo.png',
        });
    });

    it('parses fit-in URL', () => {
        const result = parseTransformUri('/fit-in/100x150/logos/2/logo.webp');
        expect(result).toEqual({
            fit: 'fit-in',
            width: '100',
            height: '150',
            key: 'logos/2/logo.webp',
        });
    });

    it('parses cover URL', () => {
        const result = parseTransformUri('/cover/400x400/avatars/3/avatar.jpg');
        expect(result).toEqual({
            fit: 'cover',
            width: '400',
            height: '400',
            key: 'avatars/3/avatar.jpg',
        });
    });

    it('returns null for non-transform URL', () => {
        const result = parseTransformUri('/avatars/1/photo.png');
        expect(result).toBeNull();
    });

    it('returns null for invalid format', () => {
        const result = parseTransformUri('/invalid/path');
        expect(result).toBeNull();
    });
});

describe('validateDimensions', () => {
    it('accepts valid dimensions', () => {
        const result = validateDimensions('200', '300');
        expect(result).toEqual({ valid: true, width: 200, height: 300 });
    });

    it('rejects dimensions below minimum', () => {
        const result = validateDimensions('0', '100');
        expect(result.valid).toBe(false);
        expect(result.error).toContain(`at least ${MIN_DIMENSION}`);
    });

    it('rejects dimensions above maximum', () => {
        const result = validateDimensions('5000', '100');
        expect(result.valid).toBe(false);
        expect(result.error).toContain(`not exceed ${MAX_DIMENSION}`);
    });

    it('accepts maximum dimension', () => {
        const result = validateDimensions(String(MAX_DIMENSION), String(MAX_DIMENSION));
        expect(result.valid).toBe(true);
    });

    it('accepts minimum dimension', () => {
        const result = validateDimensions(String(MIN_DIMENSION), String(MIN_DIMENSION));
        expect(result.valid).toBe(true);
    });

    it('rejects non-integer dimensions', () => {
        const result = validateDimensions('100.5', '200');
        expect(result.valid).toBe(false);
        expect(result.error).toContain('must be integers');
    });

    it('rejects non-numeric dimensions', () => {
        const result = validateDimensions('abc', '200');
        expect(result.valid).toBe(false);
        expect(result.error).toContain('not a number');
    });
});

describe('getOutputFormat', () => {
    it('returns jpeg for .jpg files', () => {
        expect(getOutputFormat('image.jpg')).toBe('jpeg');
    });

    it('returns jpeg for .jpeg files', () => {
        expect(getOutputFormat('image.jpeg')).toBe('jpeg');
    });

    it('returns png for .png files', () => {
        expect(getOutputFormat('image.png')).toBe('png');
    });

    it('returns webp for .webp files', () => {
        expect(getOutputFormat('image.webp')).toBe('webp');
    });

    it('returns avif for .avif files', () => {
        expect(getOutputFormat('image.avif')).toBe('avif');
    });

    it('returns jpeg for unknown extensions', () => {
        expect(getOutputFormat('image.bmp')).toBe('jpeg');
    });

    it('handles uppercase extensions', () => {
        expect(getOutputFormat('image.PNG')).toBe('png');
    });
});

describe('FIT_MODE_MAP', () => {
    it('maps fit-in to inside', () => {
        expect(FIT_MODE_MAP['fit-in']).toBe('inside');
    });

    it('maps cover to cover', () => {
        expect(FIT_MODE_MAP['cover']).toBe('cover');
    });

    it('maps contain to contain', () => {
        expect(FIT_MODE_MAP['contain']).toBe('contain');
    });

    it('maps default to fill', () => {
        expect(FIT_MODE_MAP['default']).toBe('fill');
    });
});

describe('originRequestHandler', () => {
    let originRequestHandler;

    beforeEach(async () => {
        // Re-import to get fresh instance
        const module = await import('../index.js');
        originRequestHandler = module.originRequestHandler;
    });

    it('rewrites transform URL and sets headers', async () => {
        const event = mockCloudFrontRequest('/200x300/avatars/1/photo.png');
        const result = await originRequestHandler(event);

        expect(result.uri).toBe('/avatars/1/photo.png');
        expect(result.headers['x-transform-width'][0].value).toBe('200');
        expect(result.headers['x-transform-height'][0].value).toBe('300');
        expect(result.headers['x-transform-fit']).toBeUndefined();
    });

    it('sets fit header for fit-in URL', async () => {
        const event = mockCloudFrontRequest('/fit-in/100x100/logos/1/logo.png');
        const result = await originRequestHandler(event);

        expect(result.uri).toBe('/logos/1/logo.png');
        expect(result.headers['x-transform-fit'][0].value).toBe('fit-in');
    });

    it('passes through non-transform URL unchanged', async () => {
        const event = mockCloudFrontRequest('/avatars/1/photo.png');
        const result = await originRequestHandler(event);

        expect(result.uri).toBe('/avatars/1/photo.png');
        expect(result.headers['x-transform-width']).toBeUndefined();
        expect(result.headers['x-transform-height']).toBeUndefined();
    });

    it('handles nested paths correctly', async () => {
        const event = mockCloudFrontRequest('/cover/50x50/deep/nested/path/to/image.avif');
        const result = await originRequestHandler(event);

        expect(result.uri).toBe('/deep/nested/path/to/image.avif');
        expect(result.headers['x-transform-width'][0].value).toBe('50');
        expect(result.headers['x-transform-height'][0].value).toBe('50');
        expect(result.headers['x-transform-fit'][0].value).toBe('cover');
    });

    it('returns 400 for dimensions exceeding maximum', async () => {
        const event = mockCloudFrontRequest('/10000x10000/avatars/1/photo.png');
        const result = await originRequestHandler(event);

        expect(result.status).toBe('400');
        expect(result.statusDescription).toBe('Bad Request');
        expect(result.body).toContain('not exceed');
    });

    it('returns 400 for zero dimensions', async () => {
        const event = mockCloudFrontRequest('/0x100/avatars/1/photo.png');
        const result = await originRequestHandler(event);

        expect(result.status).toBe('400');
        expect(result.body).toContain('at least');
    });
});

describe('handler (Origin Response)', () => {
    let handler;

    beforeEach(async () => {
        vi.clearAllMocks();
        const module = await import('../index.js');
        handler = module.handler;
    });

    it('passes through response without transform headers', async () => {
        const event = mockCloudFrontResponse('/avatars/1/photo.png', '200', {});
        const result = await handler(event);

        // Should return original response
        expect(result.status).toBe('200');
    });

    it('passes through non-200 responses', async () => {
        const event = mockCloudFrontResponse('/avatars/1/photo.png', '404', {
            'x-transform-width': [{ value: '200' }],
            'x-transform-height': [{ value: '300' }],
        });
        const result = await handler(event);

        expect(result.status).toBe('404');
    });

    it('handles malformed events gracefully', async () => {
        const result = await handler({});

        expect(result.status).toBe('500');
        expect(result.statusDescription).toBe('Internal Server Error');
    });
});
