import { useState, useEffect, useRef } from 'react'
import { loadGooglePlacesScript, parseAddressFromPlace, type ParsedAddress } from '@/lib/google-places'
import { cn } from '@/lib/utils'

interface AddressAutocompleteProps {
    value: string
    onChange: (value: string) => void
    onAddressSelect?: (address: ParsedAddress) => void
    placeholder?: string
    disabled?: boolean
    className?: string
    id?: string
}

/**
 * Address input with Google Places autocomplete (New API - 2025)
 * Uses PlaceAutocompleteElement for modern address autocomplete
 * Falls back to regular text input if Google Places fails to load
 */
export function AddressAutocomplete({
    value,
    onChange,
    onAddressSelect,
    placeholder = 'Start typing an address...',
    disabled = false,
    className,
    id,
}: AddressAutocompleteProps) {
    const containerRef = useRef<HTMLDivElement>(null)
    const autocompleteRef = useRef<google.maps.places.PlaceAutocompleteElement | null>(null)
    const initAttemptedRef = useRef(false)
    const [isLoaded, setIsLoaded] = useState(false)
    const [loadError, setLoadError] = useState(false)
    const [isInitialized, setIsInitialized] = useState(false)

    // Stable callback refs to avoid re-renders
    const onChangeRef = useRef(onChange)
    const onAddressSelectRef = useRef(onAddressSelect)
    useEffect(() => {
        onChangeRef.current = onChange
        onAddressSelectRef.current = onAddressSelect
    }, [onChange, onAddressSelect])

    // Load Google Places script (only once)
    useEffect(() => {
        const apiKey = import.meta.env.VITE_GOOGLE_PLACES_API_KEY

        if (!apiKey) {
            console.warn('VITE_GOOGLE_PLACES_API_KEY not set, address autocomplete disabled')
            setLoadError(true)
            return
        }

        loadGooglePlacesScript(apiKey)
            .then(() => {
                console.log('Google Places script loaded')
                setIsLoaded(true)
            })
            .catch((err) => {
                console.error('Failed to load Google Places:', err)
                setLoadError(true)
            })
    }, []) // Empty deps - only run once

    // Initialize PlaceAutocompleteElement when script is loaded
    useEffect(() => {
        // Prevent multiple initialization attempts
        if (!isLoaded || !containerRef.current || initAttemptedRef.current) return
        initAttemptedRef.current = true

        const initAutocomplete = async () => {
            try {
                console.log('Initializing PlaceAutocompleteElement...')

                // Import the Places library
                const { PlaceAutocompleteElement } = await google.maps.importLibrary('places') as google.maps.PlacesLibrary

                // Create the PlaceAutocompleteElement with address type
                const autocomplete = new PlaceAutocompleteElement({
                    types: ['address'],
                })

                // Apply styling to match our design system
                autocomplete.style.cssText = `
                    width: 100%;
                    --gmpx-color-surface: var(--background, #fff);
                    --gmpx-color-on-surface: var(--foreground, #000);
                    --gmpx-font-family-base: inherit;
                    --gmpx-font-size-base: 0.875rem;
                `

                // Add the gmp-select listener for when user selects an address
                autocomplete.addEventListener('gmp-select', async (event: Event) => {
                    const selectEvent = event as google.maps.places.PlaceAutocompletePlaceSelectEvent
                    const placePrediction = selectEvent.placePrediction

                    if (placePrediction) {
                        const place = placePrediction.toPlace()

                        // Fetch address components
                        await place.fetchFields({
                            fields: ['formattedAddress', 'addressComponents'],
                        })

                        // Update the value
                        const formattedAddress = place.formattedAddress || ''
                        onChangeRef.current(formattedAddress)

                        // Parse and callback with structured address
                        if (onAddressSelectRef.current) {
                            const parsed = parseAddressFromPlace(place)
                            onAddressSelectRef.current(parsed)
                        }
                    }
                })

                // Append to container
                if (containerRef.current) {
                    containerRef.current.appendChild(autocomplete)
                    autocompleteRef.current = autocomplete
                    setIsInitialized(true)
                    console.log('PlaceAutocompleteElement initialized')
                }

            } catch (err) {
                console.error('Failed to initialize PlaceAutocompleteElement:', err)
                setLoadError(true)
            }
        }

        initAutocomplete()
    }, [isLoaded]) // Only depend on isLoaded

    // Fallback to regular input if Google Places fails to load
    if (loadError) {
        return (
            <input
                id={id}
                type="text"
                value={value}
                onChange={(e) => onChange(e.target.value)}
                placeholder="Enter address"
                disabled={disabled}
                className={cn(
                    'w-full px-3 py-2 border border-border rounded-md bg-background text-sm',
                    'focus:outline-none focus:ring-2 focus:ring-ring',
                    'disabled:opacity-50 disabled:cursor-not-allowed',
                    className
                )}
            />
        )
    }

    // Show loading state while Google Places loads
    if (!isLoaded) {
        return (
            <input
                id={id}
                type="text"
                value={value}
                onChange={(e) => onChange(e.target.value)}
                placeholder="Loading..."
                disabled
                className={cn(
                    'w-full px-3 py-2 border border-border rounded-md bg-background text-sm',
                    'opacity-50 cursor-not-allowed',
                    className
                )}
            />
        )
    }

    // Render the container for PlaceAutocompleteElement
    return (
        <div
            ref={containerRef}
            id={id}
            className={cn(
                'address-autocomplete-container w-full',
                disabled && 'opacity-50 pointer-events-none',
                className
            )}
        />
    )
}
