/**
 * Google Places Autocomplete utilities
 * Provides address autocomplete with structured address parsing
 */

export interface ParsedAddress {
    formatted_address: string
    street_address: string
    city: string
    state: string
    postal_code: string
    country: string
    country_code: string
}

/**
 * Parse Google Places address components into structured format
 */
export function parseAddressComponents(
    place: google.maps.places.PlaceResult
): ParsedAddress {
    const components = place.address_components || []

    const getComponent = (types: string[]): string => {
        const component = components.find((c) =>
            types.some((type) => c.types.includes(type))
        )
        return component?.long_name || ''
    }

    const getComponentShort = (types: string[]): string => {
        const component = components.find((c) =>
            types.some((type) => c.types.includes(type))
        )
        return component?.short_name || ''
    }

    // Build street address from components
    const streetNumber = getComponent(['street_number'])
    const route = getComponent(['route'])
    const streetAddress = [streetNumber, route].filter(Boolean).join(' ')

    return {
        formatted_address: place.formatted_address || '',
        street_address: streetAddress,
        city: getComponent(['locality', 'sublocality', 'administrative_area_level_3']),
        state: getComponent(['administrative_area_level_1']),
        postal_code: getComponent(['postal_code']),
        country: getComponent(['country']),
        country_code: getComponentShort(['country']).toLowerCase(),
    }
}

/**
 * Load Google Places API script dynamically
 */
export function loadGooglePlacesScript(apiKey: string): Promise<void> {
    return new Promise((resolve, reject) => {
        // Already loaded
        if (window.google?.maps?.places) {
            resolve()
            return
        }

        // Check if script is already being loaded
        const existingScript = document.querySelector(
            'script[src*="maps.googleapis.com/maps/api/js"]'
        )
        if (existingScript) {
            existingScript.addEventListener('load', () => resolve())
            existingScript.addEventListener('error', () => reject(new Error('Failed to load Google Places')))
            return
        }

        const script = document.createElement('script')
        script.src = `https://maps.googleapis.com/maps/api/js?key=${apiKey}&libraries=places`
        script.async = true
        script.defer = true
        script.onload = () => resolve()
        script.onerror = () => reject(new Error('Failed to load Google Places'))
        document.head.appendChild(script)
    })
}

// Extend window for google types
declare global {
    interface Window {
        google?: typeof google
    }
}
