import { useState, useEffect, useRef } from 'react'
import { loadGooglePlacesScript, parseAddressFromPlace, type ParsedAddress } from '@/lib/google-places'
import { cn } from '@/lib/utils'
import { Search } from 'lucide-react'

interface AddressLookupProps {
    onAddressSelect: (address: ParsedAddress) => void
    placeholder?: string
    disabled?: boolean
    className?: string
}

/**
 * Address lookup field using Google Places autocomplete
 * This is a search-only field - it populates other form fields when an address is selected
 * The field clears after selection to indicate it's just a lookup tool
 */
export function AddressLookup({
    onAddressSelect,
    placeholder = 'Search for an address...',
    disabled = false,
    className,
}: AddressLookupProps) {
    const containerRef = useRef<HTMLDivElement>(null)
    const autocompleteRef = useRef<google.maps.places.PlaceAutocompleteElement | null>(null)
    const initAttemptedRef = useRef(false)
    const [isLoaded, setIsLoaded] = useState(false)
    const [loadError, setLoadError] = useState(false)
    const [isInitialized, setIsInitialized] = useState(false)

    // Stable callback ref
    const onAddressSelectRef = useRef(onAddressSelect)
    useEffect(() => {
        onAddressSelectRef.current = onAddressSelect
    }, [onAddressSelect])

    // Load Google Places script
    useEffect(() => {
        const apiKey = import.meta.env.VITE_GOOGLE_PLACES_API_KEY

        if (!apiKey) {
            console.warn('VITE_GOOGLE_PLACES_API_KEY not set')
            setLoadError(true)
            return
        }

        loadGooglePlacesScript(apiKey)
            .then(() => setIsLoaded(true))
            .catch((err) => {
                console.error('Failed to load Google Places:', err)
                setLoadError(true)
            })
    }, [])

    // Initialize PlaceAutocompleteElement
    useEffect(() => {
        if (!isLoaded || !containerRef.current || initAttemptedRef.current) return
        initAttemptedRef.current = true

        const initAutocomplete = async () => {
            try {
                const { PlaceAutocompleteElement } = await google.maps.importLibrary('places') as google.maps.PlacesLibrary

                const autocomplete = new PlaceAutocompleteElement({
                    types: ['address'],
                })

                autocomplete.style.cssText = `
                    width: 100%;
                    --gmpx-color-surface: var(--background, #fff);
                    --gmpx-color-on-surface: var(--foreground, #000);
                    --gmpx-font-family-base: inherit;
                    --gmpx-font-size-base: 0.875rem;
                `

                autocomplete.addEventListener('gmp-select', async (event: Event) => {
                    const selectEvent = event as google.maps.places.PlaceAutocompletePlaceSelectEvent
                    const placePrediction = selectEvent.placePrediction

                    if (placePrediction) {
                        const place = placePrediction.toPlace()

                        await place.fetchFields({
                            fields: ['formattedAddress', 'addressComponents'],
                        })

                        const parsed = parseAddressFromPlace(place)
                        onAddressSelectRef.current(parsed)

                        // Clear the lookup field after selection
                        // This indicates it's just a helper, not a form field
                        setTimeout(() => {
                            const input = autocomplete.querySelector('input') ||
                                autocomplete.shadowRoot?.querySelector('input')
                            if (input) {
                                input.value = ''
                            }
                        }, 100)
                    }
                })

                if (containerRef.current) {
                    containerRef.current.appendChild(autocomplete)
                    autocompleteRef.current = autocomplete
                    setIsInitialized(true)
                }

            } catch (err) {
                console.error('Failed to initialize PlaceAutocompleteElement:', err)
                setLoadError(true)
            }
        }

        initAutocomplete()
    }, [isLoaded])

    if (loadError) {
        return null // Hide the lookup if Google Places fails
    }

    if (!isLoaded) {
        return (
            <div className={cn('relative', className)}>
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <input
                    type="text"
                    placeholder="Loading address lookup..."
                    disabled
                    className="w-full pl-10 pr-3 py-2 border border-border rounded-md bg-muted/50 text-sm opacity-50"
                />
            </div>
        )
    }

    return (
        <div className={cn('relative', className)}>
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground z-10 pointer-events-none" />
            <div
                ref={containerRef}
                className={cn(
                    'address-lookup-container w-full',
                    disabled && 'opacity-50 pointer-events-none'
                )}
                style={{ paddingLeft: '2.5rem' }}
            />
        </div>
    )
}
