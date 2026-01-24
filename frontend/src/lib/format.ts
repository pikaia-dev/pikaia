/**
 * Shared formatting utilities.
 */

/**
 * Format a date string to a short format (e.g., "Jan 24, 2026").
 */
export function formatDateShort(dateString: string | null): string {
  if (!dateString) return '—'
  return new Date(dateString).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

/**
 * Format a date string to a long format (e.g., "January 24, 2026").
 */
export function formatDateLong(dateString: string | null): string {
  if (!dateString) return '—'
  return new Date(dateString).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  })
}

/**
 * Format a date string to full datetime (e.g., "1/24/2026, 5:48:31 PM").
 */
export function formatDateTime(dateString: string | null): string {
  if (!dateString) return '—'
  return new Date(dateString).toLocaleString()
}
