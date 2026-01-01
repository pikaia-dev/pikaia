import { describe, it, expect } from 'vitest';
import { handler, parseTransformUri, TRANSFORM_URL_PATTERN } from '../index.js';

/**
 * Create a mock CloudFront Origin Request event.
 */
function mockCloudFrontEvent(uri) {
    return {
        Records: [
            {
                cf: {
                    request: {
                        uri,
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

describe('handler', () => {
    it('rewrites transform URL and sets headers', async () => {
        const event = mockCloudFrontEvent('/200x300/avatars/1/photo.png');
        const result = await handler(event);

        expect(result.uri).toBe('/avatars/1/photo.png');
        expect(result.headers['x-transform-width'][0].value).toBe('200');
        expect(result.headers['x-transform-height'][0].value).toBe('300');
        expect(result.headers['x-transform-fit']).toBeUndefined();
    });

    it('sets fit header for fit-in URL', async () => {
        const event = mockCloudFrontEvent('/fit-in/100x100/logos/1/logo.svg');
        const result = await handler(event);

        expect(result.uri).toBe('/logos/1/logo.svg');
        expect(result.headers['x-transform-fit'][0].value).toBe('fit-in');
    });

    it('passes through non-transform URL unchanged', async () => {
        const event = mockCloudFrontEvent('/avatars/1/photo.png');
        const result = await handler(event);

        expect(result.uri).toBe('/avatars/1/photo.png');
        expect(result.headers['x-transform-width']).toBeUndefined();
        expect(result.headers['x-transform-height']).toBeUndefined();
    });

    it('handles nested paths correctly', async () => {
        const event = mockCloudFrontEvent('/cover/50x50/deep/nested/path/to/image.avif');
        const result = await handler(event);

        expect(result.uri).toBe('/deep/nested/path/to/image.avif');
        expect(result.headers['x-transform-width'][0].value).toBe('50');
        expect(result.headers['x-transform-height'][0].value).toBe('50');
        expect(result.headers['x-transform-fit'][0].value).toBe('cover');
    });
});
