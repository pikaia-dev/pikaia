import { useState, useEffect, useRef, useCallback } from 'react'
import { loadGooglePlacesScript, parseAddressComponents, type ParsedAddress } from '@/lib/google-places'
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
 * Address input with Google Places autocomplete
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
    const inputRef = useRef<HTMLInputElement>(null)
    const autocompleteRef = useRef<google.maps.places.Autocomplete | null>(null)
    const [isLoaded, setIsLoaded] = useState(false)
    const [loadError, setLoadError] = useState(false)

    // Load Google Places script
    useEffect(() => {
        const apiKey = import.meta.env.VITE_GOOGLE_PLACES_API_KEY

        if (!apiKey) {
            console.warn('VITE_GOOGLE_PLACES_API_KEY not set, address autocomplete disabled')
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

    // Initialize autocomplete when script is loaded and input is ready
    useEffect(() => {
        if (!isLoaded || !inputRef.current || autocompleteRef.current) return

        const autocomplete = new google.maps.places.Autocomplete(inputRef.current, {
            types: ['address'],
            fields: ['address_components', 'formatted_address'],
        })

        autocomplete.addListener('place_changed', () => {
            const place = autocomplete.getPlace()

            if (place.formatted_address) {
                onChange(place.formatted_address)

                if (onAddressSelect) {
                    const parsed = parseAddressComponents(place)
                    onAddressSelect(parsed)
                }
            }
        })

        autocompleteRef.current = autocomplete

        return () => {
            // Cleanup: Remove the pac-container elements
            const pacContainers = document.querySelectorAll('.pac-container')
            pacContainers.forEach((el) => el.remove())
        }
    }, [isLoaded, onChange, onAddressSelect])

    // Sync external value changes to input
    const handleChange = useCallback(
        (e: React.ChangeEvent<HTMLInputElement>) => {
            onChange(e.target.value)
        },
        [onChange]
    )

    return (
        <input
            ref={inputRef}
            id={id}
            type="text"
            value={value}
            onChange={handleChange}
            placeholder={loadError ? 'Enter address' : placeholder}
            disabled={disabled}
            className={cn(
                'w-full px-3 py-2 border border-border rounded-md bg-background text-sm',
                'focus:outline-none focus:ring-2 focus:ring-ring',
                'disabled:opacity-50 disabled:cursor-not-allowed',
                className
            )}
            autoComplete="off"
        />
    )
}
