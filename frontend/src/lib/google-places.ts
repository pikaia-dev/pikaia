/// <reference types="@types/google.maps" />

/**
 * Google Places API utilities (New API - 2025)
 * Uses PlaceAutocompleteElement for address autocomplete
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
 * Parse address components from Place object (New API)
 */
export function parseAddressFromPlace(place: google.maps.places.Place): ParsedAddress {
  const components = place.addressComponents || []

  const getComponent = (types: string[]): string => {
    const component = components.find((c) => types.some((type) => c.types.includes(type)))
    return component?.longText || ''
  }

  const getComponentShort = (types: string[]): string => {
    const component = components.find((c) => types.some((type) => c.types.includes(type)))
    return component?.shortText || ''
  }

  // Build street address from components
  const streetNumber = getComponent(['street_number'])
  const route = getComponent(['route'])
  const streetAddress = [streetNumber, route].filter(Boolean).join(' ')

  // Extract city with proper fallback chain
  // Priority: locality (actual city) > administrative_area_level_2 (often city in some countries)
  // > administrative_area_level_3 > sublocality (district, last resort)
  const city =
    getComponent(['locality']) ||
    getComponent(['administrative_area_level_2']) ||
    getComponent(['administrative_area_level_3']) ||
    getComponent(['sublocality']) ||
    ''

  return {
    formatted_address: place.formattedAddress || '',
    street_address: streetAddress,
    city,
    state: getComponent(['administrative_area_level_1']),
    postal_code: getComponent(['postal_code']),
    country: getComponent(['country']),
    country_code: getComponentShort(['country']).toLowerCase(),
  }
}

// Global callback name for Google Maps API
const CALLBACK_NAME = '__googleMapsCallback'

/**
 * Wait for the Google Maps library to be fully initialized
 * with the importLibrary function available
 */
function waitForGoogleMaps(timeout: number = 10000): Promise<void> {
  return new Promise((resolve, reject) => {
    const startTime = Date.now()

    const check = () => {
      if (
        typeof google !== 'undefined' &&
        typeof google.maps !== 'undefined' &&
        typeof google.maps.importLibrary === 'function'
      ) {
        resolve()
        return
      }

      if (Date.now() - startTime > timeout) {
        reject(new Error('Google Maps initialization timeout'))
        return
      }

      setTimeout(check, 100)
    }

    check()
  })
}

/**
 * Load Google Maps JavaScript API with Places library (New API)
 * Returns a promise that resolves when the API is fully ready
 */
export async function loadGooglePlacesScript(apiKey: string): Promise<void> {
  // Check if already loaded
  if (
    typeof google !== 'undefined' &&
    typeof google.maps !== 'undefined' &&
    typeof google.maps.importLibrary === 'function'
  ) {
    return
  }

  // Check if script is already being loaded
  const existingScript = document.querySelector('script[src*="maps.googleapis.com/maps/api/js"]')

  if (existingScript) {
    await waitForGoogleMaps()
    return
  }

  // Create a promise for the callback
  const callbackPromise = new Promise<void>((resolve) => {
    ;(window as unknown as Record<string, unknown>)[CALLBACK_NAME] = () => {
      Reflect.deleteProperty(window as unknown as Record<string, unknown>, CALLBACK_NAME)
      resolve()
    }
  })

  // Load the script
  const script = document.createElement('script')
  // Use v=beta for access to new features like PlaceAutocompleteElement
  script.src = `https://maps.googleapis.com/maps/api/js?key=${apiKey}&libraries=places&v=beta&callback=${CALLBACK_NAME}`
  script.async = true
  script.defer = true

  const errorPromise = new Promise<never>((_, reject) => {
    script.onerror = () => {
      Reflect.deleteProperty(window as unknown as Record<string, unknown>, CALLBACK_NAME)
      reject(new Error('Failed to load Google Maps script'))
    }
  })

  document.head.appendChild(script)

  // Wait for either success or error
  await Promise.race([callbackPromise, errorPromise])

  // After callback, wait for full initialization
  await waitForGoogleMaps()
}

// Extend window for google types
declare global {
  interface Window {
    google?: typeof google
  }
}
