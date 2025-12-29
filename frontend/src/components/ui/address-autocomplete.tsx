import { useState, useEffect, useRef, useCallback } from 'react'
import { loadGooglePlacesScript, parseAddressFromPlace, type ParsedAddress } from '@/lib/google-places'
import { cn } from '@/lib/utils'
import { Search, Keyboard } from 'lucide-react'

interface AddressAutocompleteProps {
    value: string
    onChange: (value: string) => void
    onAddressSelect?: (address: ParsedAddress) => void
    placeholder?: string
    disabled?: boolean
    className?: string
    id?: string
}

interface Suggestion {
    placeId: string
    mainText: string
    secondaryText: string
    fullText: string
}

/**
 * Custom address autocomplete with Google Places
 * Shows suggestions in a custom dropdown with "Continue manually" option
 * After selection, shows a regular text input with just the street address
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
    const inputRef = useRef<HTMLInputElement>(null)
    const dropdownRef = useRef<HTMLDivElement>(null)
    const sessionTokenRef = useRef<google.maps.places.AutocompleteSessionToken | null>(null)
    const autocompleteServiceRef = useRef<google.maps.places.AutocompleteService | null>(null)
    const placesServiceRef = useRef<google.maps.places.PlacesService | null>(null)

    const [isLoaded, setIsLoaded] = useState(false)
    const [loadError, setLoadError] = useState(false)
    const [suggestions, setSuggestions] = useState<Suggestion[]>([])
    const [isOpen, setIsOpen] = useState(false)
    const [selectedIndex, setSelectedIndex] = useState(-1)
    const [isFetching, setIsFetching] = useState(false)
    const [isFocused, setIsFocused] = useState(false)

    // Load Google Places
    useEffect(() => {
        const apiKey = import.meta.env.VITE_GOOGLE_PLACES_API_KEY
        if (!apiKey) {
            setLoadError(true)
            return
        }

        loadGooglePlacesScript(apiKey)
            .then(() => setIsLoaded(true))
            .catch(() => setLoadError(true))
    }, [])

    // Initialize services when loaded
    useEffect(() => {
        if (!isLoaded) return

        const initServices = async () => {
            try {
                await google.maps.importLibrary('places')
                autocompleteServiceRef.current = new google.maps.places.AutocompleteService()
                // Create a dummy div for PlacesService (required by API)
                const dummyDiv = document.createElement('div')
                placesServiceRef.current = new google.maps.places.PlacesService(dummyDiv)
                sessionTokenRef.current = new google.maps.places.AutocompleteSessionToken()
            } catch (err) {
                console.error('Failed to initialize Places services:', err)
                setLoadError(true)
            }
        }
        initServices()
    }, [isLoaded])

    // Fetch suggestions when value changes
    const fetchSuggestions = useCallback(async (query: string) => {
        if (!query || query.length < 3 || !autocompleteServiceRef.current) {
            setSuggestions([])
            return
        }

        setIsFetching(true)
        try {
            const request: google.maps.places.AutocompletionRequest = {
                input: query,
                types: ['address'],
                sessionToken: sessionTokenRef.current || undefined,
            }

            autocompleteServiceRef.current.getPlacePredictions(
                request,
                (predictions, status) => {
                    setIsFetching(false)
                    if (status === google.maps.places.PlacesServiceStatus.OK && predictions) {
                        setSuggestions(
                            predictions.slice(0, 5).map((p) => ({
                                placeId: p.place_id,
                                mainText: p.structured_formatting.main_text,
                                secondaryText: p.structured_formatting.secondary_text || '',
                                fullText: p.description,
                            }))
                        )
                        setIsOpen(true)
                    } else {
                        setSuggestions([])
                    }
                }
            )
        } catch {
            setIsFetching(false)
            setSuggestions([])
        }
    }, [])

    // Debounced fetch - only when focused
    useEffect(() => {
        if (!isLoaded || loadError || !isFocused) return

        const timer = setTimeout(() => {
            fetchSuggestions(value)
        }, 300)

        return () => clearTimeout(timer)
    }, [value, isLoaded, loadError, isFocused, fetchSuggestions])

    // Handle suggestion selection
    const handleSelect = useCallback(async (suggestion: Suggestion) => {
        if (!placesServiceRef.current) return

        setIsOpen(false)
        setSuggestions([])

        // Fetch place details
        const request: google.maps.places.PlaceDetailsRequest = {
            placeId: suggestion.placeId,
            fields: ['formatted_address', 'address_components'],
            sessionToken: sessionTokenRef.current || undefined,
        }

        placesServiceRef.current.getDetails(request, (place, status) => {
            if (status === google.maps.places.PlacesServiceStatus.OK && place) {
                // Parse address components
                const parsed = parseAddressFromPlaceResult(place)

                // Update the input with just the street address
                onChange(parsed.street_address || suggestion.mainText)

                // Notify parent with full parsed address
                if (onAddressSelect) {
                    onAddressSelect(parsed)
                }
            }

            // Create new session token for next search
            sessionTokenRef.current = new google.maps.places.AutocompleteSessionToken()
        })
    }, [onChange, onAddressSelect])

    // Handle "continue manually" option
    const handleManualInput = useCallback(() => {
        setIsOpen(false)
        setSuggestions([])
        inputRef.current?.focus()
    }, [])

    // Keyboard navigation
    const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
        const totalItems = suggestions.length + 1 // +1 for "continue manually" option

        if (e.key === 'ArrowDown') {
            e.preventDefault()
            setSelectedIndex((prev) => (prev + 1) % totalItems)
        } else if (e.key === 'ArrowUp') {
            e.preventDefault()
            setSelectedIndex((prev) => (prev - 1 + totalItems) % totalItems)
        } else if (e.key === 'Enter' && isOpen) {
            e.preventDefault()
            if (selectedIndex >= 0 && selectedIndex < suggestions.length) {
                handleSelect(suggestions[selectedIndex])
            } else if (selectedIndex === suggestions.length) {
                handleManualInput()
            }
        } else if (e.key === 'Escape') {
            setIsOpen(false)
            setSelectedIndex(-1)
        }
    }, [suggestions, selectedIndex, isOpen, handleSelect, handleManualInput])

    // Close dropdown on outside click
    useEffect(() => {
        const handleClickOutside = (e: MouseEvent) => {
            if (
                dropdownRef.current &&
                !dropdownRef.current.contains(e.target as Node) &&
                inputRef.current &&
                !inputRef.current.contains(e.target as Node)
            ) {
                setIsOpen(false)
            }
        }
        document.addEventListener('mousedown', handleClickOutside)
        return () => document.removeEventListener('mousedown', handleClickOutside)
    }, [])

    const inputClasses = cn(
        'w-full px-3 py-2 border border-border rounded-md bg-background text-sm',
        'focus:outline-none focus:ring-2 focus:ring-ring',
        'disabled:opacity-50 disabled:cursor-not-allowed',
        className
    )

    return (
        <div className="relative">
            <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none" />
                <input
                    ref={inputRef}
                    id={id}
                    type="text"
                    value={value}
                    onChange={(e) => onChange(e.target.value)}
                    onKeyDown={handleKeyDown}
                    onFocus={() => {
                        setIsFocused(true)
                        if (suggestions.length > 0) setIsOpen(true)
                    }}
                    onBlur={() => setIsFocused(false)}
                    placeholder={loadError ? 'Enter address' : placeholder}
                    disabled={disabled}
                    autoComplete="off"
                    className={cn(inputClasses, 'pl-10')}
                />
            </div>

            {/* Dropdown */}
            {isOpen && (suggestions.length > 0 || value.length >= 3) && (
                <div
                    ref={dropdownRef}
                    className="absolute z-50 w-full mt-1 bg-background border border-border rounded-md shadow-lg overflow-hidden"
                >
                    {suggestions.map((suggestion, index) => (
                        <button
                            key={suggestion.placeId}
                            type="button"
                            onClick={() => handleSelect(suggestion)}
                            className={cn(
                                'w-full px-3 py-2 text-left text-sm hover:bg-accent transition-colors',
                                'flex flex-col',
                                selectedIndex === index && 'bg-accent'
                            )}
                        >
                            <span className="font-medium">{suggestion.mainText}</span>
                            <span className="text-xs text-muted-foreground">{suggestion.secondaryText}</span>
                        </button>
                    ))}

                    {/* "Continue manually" option */}
                    <button
                        type="button"
                        onClick={handleManualInput}
                        className={cn(
                            'w-full px-3 py-2 text-left text-sm hover:bg-accent transition-colors',
                            'flex items-center gap-2 border-t border-border text-muted-foreground',
                            selectedIndex === suggestions.length && 'bg-accent'
                        )}
                    >
                        <Keyboard className="h-4 w-4" />
                        <span>Continue with manual input</span>
                    </button>
                </div>
            )}
        </div>
    )
}

/**
 * Parse address from PlaceResult (legacy API format)
 */
function parseAddressFromPlaceResult(place: google.maps.places.PlaceResult): ParsedAddress {
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

    const streetNumber = getComponent(['street_number'])
    const route = getComponent(['route'])
    const streetAddress = [streetNumber, route].filter(Boolean).join(' ')

    // Priority: locality > administrative_area_level_2 > administrative_area_level_3 > sublocality
    const city = getComponent(['locality']) ||
        getComponent(['administrative_area_level_2']) ||
        getComponent(['administrative_area_level_3']) ||
        getComponent(['sublocality']) ||
        ''

    return {
        formatted_address: place.formatted_address || '',
        street_address: streetAddress,
        city,
        state: getComponent(['administrative_area_level_1']),
        postal_code: getComponent(['postal_code']),
        country: getComponent(['country']),
        country_code: getComponentShort(['country']).toLowerCase(),
    }
}
