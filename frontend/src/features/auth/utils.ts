/**
 * Extracts error message from unknown error type.
 * Useful for catch blocks where error type is unknown.
 */
export function getErrorMessage(err: unknown, fallback: string): string {
  return err instanceof Error ? err.message : fallback
}

/**
 * Generate a passkey name based on the user's browser and device.
 */
export function generatePasskeyName(): string {
  const userAgent = navigator.userAgent

  // Detect browser
  let browser = 'Browser'
  if (userAgent.includes('Chrome') && !userAgent.includes('Edg')) browser = 'Chrome'
  else if (userAgent.includes('Safari') && !userAgent.includes('Chrome')) browser = 'Safari'
  else if (userAgent.includes('Firefox')) browser = 'Firefox'
  else if (userAgent.includes('Edg')) browser = 'Edge'

  // Detect device type
  let deviceType = ''
  if (userAgent.includes('iPhone')) deviceType = 'iPhone'
  else if (userAgent.includes('iPad')) deviceType = 'iPad'
  else if (userAgent.includes('Mac')) deviceType = 'Mac'
  else if (userAgent.includes('Windows')) deviceType = 'Windows'
  else if (userAgent.includes('Android')) deviceType = 'Android'
  else if (userAgent.includes('Linux')) deviceType = 'Linux'

  return deviceType ? `${deviceType} ${browser}` : browser
}
