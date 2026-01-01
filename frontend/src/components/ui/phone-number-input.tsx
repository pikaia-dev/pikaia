/**
 * Phone Number Input component with country code selector.
 *
 * Features:
 * - Integrated country selector with flags
 * - Real-time formatting for display
 * - E.164 format for storage
 * - Auto-detect country from existing number or browser locale
 * - Dynamic placeholder based on selected country
 */

import { useState, useEffect, useMemo, useCallback } from 'react'
import { parsePhoneNumber, getExampleNumber, AsYouType, type CountryCode } from 'libphonenumber-js'
import examples from 'libphonenumber-js/mobile/examples'
import { COUNTRIES, getCountryByCode } from '../../lib/countries'
import { cn } from '../../lib/utils'
import {
    Popover,
    PopoverContent,
    PopoverTrigger,
} from './popover'
import {
    Command,
    CommandEmpty,
    CommandGroup,
    CommandInput,
    CommandItem,
    CommandList,
} from './command'
import { ChevronDown, Check } from 'lucide-react'

interface PhoneNumberInputProps {
    /** Phone number in E.164 format (e.g., "+14155551234") */
    value: string
    /** Called with E.164 format value on change */
    onChange: (value: string) => void
    /** Whether the input is disabled */
    disabled?: boolean
    /** Optional CSS class name */
    className?: string
}

/**
 * Get the user's likely country based on browser locale.
 */
function getDefaultCountryCode(): string {
    // Try to get from browser's navigator.language (e.g., "en-US" -> "US")
    if (typeof navigator !== 'undefined' && navigator.language) {
        const parts = navigator.language.split('-')
        if (parts.length >= 2) {
            const countryCode = parts[parts.length - 1].toUpperCase()
            if (getCountryByCode(countryCode)) {
                return countryCode
            }
        }
    }
    return 'US' // Default fallback
}

/**
 * Parse an E.164 phone number to extract country and national number.
 */
function parseE164(value: string): { countryCode: string; nationalNumber: string } {
    if (!value) {
        return { countryCode: getDefaultCountryCode(), nationalNumber: '' }
    }

    try {
        const parsed = parsePhoneNumber(value)
        if (parsed && parsed.country) {
            return {
                countryCode: parsed.country,
                nationalNumber: parsed.nationalNumber,
            }
        }
    } catch {
        // If parsing fails, try to find country by dial code
        for (const country of COUNTRIES) {
            if (value.startsWith(country.dialCode)) {
                return {
                    countryCode: country.code,
                    nationalNumber: value.slice(country.dialCode.length),
                }
            }
        }
    }

    return { countryCode: getDefaultCountryCode(), nationalNumber: value.replace(/^\+/, '') }
}

/**
 * Get a formatted example phone number for a country.
 */
function getPlaceholder(countryCode: string): string {
    try {
        const example = getExampleNumber(countryCode as CountryCode, examples)
        if (example) {
            return example.formatNational()
        }
    } catch {
        // Ignore errors
    }
    return '123 456 7890'
}

export function PhoneNumberInput({
    value,
    onChange,
    disabled = false,
    className,
}: PhoneNumberInputProps) {
    const [open, setOpen] = useState(false)

    // Parse the initial value
    const { countryCode: initialCountry, nationalNumber: initialNational } = useMemo(
        () => parseE164(value),
        // Only compute on mount
        // eslint-disable-next-line react-hooks/exhaustive-deps
        []
    )

    const [selectedCountry, setSelectedCountry] = useState<string>(initialCountry)
    const [inputValue, setInputValue] = useState<string>(initialNational)

    // Sync external value changes
    useEffect(() => {
        const { countryCode, nationalNumber } = parseE164(value)
        setSelectedCountry(countryCode)
        setInputValue(nationalNumber)
    }, [value])

    const country = useMemo(
        () => getCountryByCode(selectedCountry) || COUNTRIES.find(c => c.code === 'US')!,
        [selectedCountry]
    )

    const placeholder = useMemo(() => getPlaceholder(selectedCountry), [selectedCountry])

    // Format input as user types
    const handleInputChange = useCallback(
        (e: React.ChangeEvent<HTMLInputElement>) => {
            const rawInput = e.target.value

            // Only allow digits
            const digitsOnly = rawInput.replace(/\D/g, '')
            setInputValue(digitsOnly)

            // Build E.164 number
            if (digitsOnly) {
                const e164 = country.dialCode + digitsOnly
                onChange(e164)
            } else {
                onChange('')
            }
        },
        [country.dialCode, onChange]
    )

    // Format for display using AsYouType
    const displayValue = useMemo(() => {
        if (!inputValue) return ''
        try {
            const formatter = new AsYouType(selectedCountry as CountryCode)
            return formatter.input(inputValue)
        } catch {
            return inputValue
        }
    }, [inputValue, selectedCountry])

    const handleCountryChange = useCallback(
        (newCountryCode: string) => {
            setSelectedCountry(newCountryCode)
            setOpen(false)

            // Update the E.164 value with new country code
            if (inputValue) {
                const newCountry = getCountryByCode(newCountryCode)
                if (newCountry) {
                    const e164 = newCountry.dialCode + inputValue
                    onChange(e164)
                }
            }
        },
        [inputValue, onChange]
    )

    return (
        <div className={cn('flex', className)}>
            {/* Country Selector */}
            <Popover open={open} onOpenChange={setOpen}>
                <PopoverTrigger asChild disabled={disabled}>
                    <button
                        type="button"
                        role="combobox"
                        aria-expanded={open}
                        className={cn(
                            'flex items-center gap-1 px-3 py-2 border border-border rounded-l-md bg-background text-sm',
                            'hover:bg-accent focus:outline-none focus:ring-2 focus:ring-ring',
                            'min-w-[100px] justify-between',
                            disabled && 'opacity-50 cursor-not-allowed'
                        )}
                    >
                        <span className="flex items-center gap-2">
                            <span className="text-base">{country.flag}</span>
                            <span className="text-muted-foreground">{country.dialCode}</span>
                        </span>
                        <ChevronDown className="h-4 w-4 opacity-50" />
                    </button>
                </PopoverTrigger>
                <PopoverContent className="w-[300px] p-0" align="start">
                    <Command>
                        <CommandInput placeholder="Search country..." />
                        <CommandEmpty>No country found.</CommandEmpty>
                        <CommandList>
                            <CommandGroup>
                                {COUNTRIES.map((c) => (
                                    <CommandItem
                                        key={c.code}
                                        value={`${c.name} ${c.dialCode}`}
                                        onSelect={() => handleCountryChange(c.code)}
                                    >
                                        <span className="flex items-center gap-2 flex-1">
                                            <span className="text-base">{c.flag}</span>
                                            <span>{c.name}</span>
                                            <span className="text-muted-foreground ml-auto">
                                                {c.dialCode}
                                            </span>
                                        </span>
                                        {selectedCountry === c.code && (
                                            <Check className="h-4 w-4 ml-2" />
                                        )}
                                    </CommandItem>
                                ))}
                            </CommandGroup>
                        </CommandList>
                    </Command>
                </PopoverContent>
            </Popover>

            {/* Phone Number Input */}
            <input
                type="tel"
                inputMode="numeric"
                value={displayValue}
                onChange={handleInputChange}
                disabled={disabled}
                placeholder={placeholder}
                className={cn(
                    'flex-1 px-3 py-2 border border-l-0 border-border rounded-r-md bg-background text-sm',
                    'focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-0',
                    'placeholder:text-muted-foreground',
                    disabled && 'opacity-50 cursor-not-allowed bg-muted'
                )}
            />
        </div>
    )
}
