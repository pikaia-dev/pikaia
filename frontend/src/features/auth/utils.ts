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
    const ua = navigator.userAgent

    // Detect browser
    let browser = "Browser"
    if (ua.includes("Chrome") && !ua.includes("Edg")) browser = "Chrome"
    else if (ua.includes("Safari") && !ua.includes("Chrome")) browser = "Safari"
    else if (ua.includes("Firefox")) browser = "Firefox"
    else if (ua.includes("Edg")) browser = "Edge"

    // Detect device type
    let device = ""
    if (ua.includes("iPhone")) device = "iPhone"
    else if (ua.includes("iPad")) device = "iPad"
    else if (ua.includes("Mac")) device = "Mac"
    else if (ua.includes("Windows")) device = "Windows"
    else if (ua.includes("Android")) device = "Android"
    else if (ua.includes("Linux")) device = "Linux"

    return device ? `${device} ${browser}` : browser
}
