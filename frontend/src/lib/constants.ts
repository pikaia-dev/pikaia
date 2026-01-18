/**
 * Stytch RBAC role identifiers.
 *
 * These must match the role IDs configured in the Stytch Dashboard.
 * @see https://stytch.com/docs/b2b/guides/rbac/overview
 */
export const STYTCH_ROLES = {
  /** Admin role ID - grants full organization management permissions */
  ADMIN: 'stytch_admin',
} as const

/**
 * Media upload configuration.
 *
 * These limits should match the backend settings in config/settings/base.py
 */
export const MEDIA_UPLOAD = {
  /** Maximum file size in bytes (10MB) */
  MAX_SIZE_BYTES: 10 * 1024 * 1024,
  /** Maximum file size in MB for display */
  MAX_SIZE_MB: 10,
  /** Accepted MIME types mapped to file extensions */
  ACCEPTED_TYPES: {
    'image/jpeg': ['.jpg', '.jpeg', '.JPG', '.JPEG'],
    'image/png': ['.png', '.PNG'],
    'image/webp': ['.webp', '.WEBP'],
    'image/svg+xml': ['.svg', '.SVG'],
    'image/avif': ['.avif', '.AVIF'],
  },
} as const
