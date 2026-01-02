import { useState, useEffect, useRef, useCallback } from 'react'
import { cn } from '@/lib/utils'
import { Search, Keyboard, User } from 'lucide-react'
import { useApi } from '@/hooks/useApi'
import type { DirectoryUser } from '@/lib/api'

/** Minimum characters before triggering autocomplete */
const MIN_QUERY_LENGTH = 2
/** Maximum number of suggestions to display */
const MAX_SUGGESTIONS = 8
/** Debounce delay for fetching suggestions (ms) */
const DEBOUNCE_DELAY_MS = 300

interface EmailAutocompleteProps {
    value: string
    onChange: (value: string) => void
    onSelect?: (user: DirectoryUser) => void
    placeholder?: string
    disabled?: boolean
    className?: string
    id?: string
}

/**
 * Email autocomplete with Google Workspace directory suggestions.
 * 
 * Shows coworker suggestions from the user's Google Workspace domain
 * when they start typing. Gracefully degrades to manual input if
 * Directory API is not available.
 */
export function EmailAutocomplete({
    value,
    onChange,
    onSelect,
    placeholder = 'user@example.com',
    disabled = false,
    className,
    id,
}: EmailAutocompleteProps) {
    const inputRef = useRef<HTMLInputElement>(null)
    const dropdownRef = useRef<HTMLDivElement>(null)

    const { searchDirectory } = useApi()

    const [suggestions, setSuggestions] = useState<DirectoryUser[]>([])
    const [isOpen, setIsOpen] = useState(false)
    const [selectedIndex, setSelectedIndex] = useState(-1)
    const [isFocused, setIsFocused] = useState(false)
    const [isSearching, setIsSearching] = useState(false)

    // Fetch suggestions when value changes
    const fetchSuggestions = useCallback(async (query: string) => {
        if (!query || query.length < MIN_QUERY_LENGTH) {
            setSuggestions([])
            return
        }

        setIsSearching(true)
        try {
            const results = await searchDirectory(query)
            setSuggestions(results.slice(0, MAX_SUGGESTIONS))
            if (results.length > 0) {
                setIsOpen(true)
            }
        } catch {
            // Directory API not available - gracefully degrade
            setSuggestions([])
        } finally {
            setIsSearching(false)
        }
    }, [searchDirectory])

    // Debounced fetch - only when focused
    useEffect(() => {
        if (!isFocused) return

        const timer = setTimeout(() => {
            fetchSuggestions(value)
        }, DEBOUNCE_DELAY_MS)

        return () => clearTimeout(timer)
    }, [value, isFocused, fetchSuggestions])

    // Handle suggestion selection
    const handleSelect = useCallback((user: DirectoryUser) => {
        setIsOpen(false)
        setSuggestions([])
        onChange(user.email)
        onSelect?.(user)
    }, [onChange, onSelect])

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
                    type="email"
                    value={value}
                    onChange={(e) => onChange(e.target.value)}
                    onKeyDown={handleKeyDown}
                    onFocus={() => {
                        setIsFocused(true)
                        if (suggestions.length > 0) setIsOpen(true)
                    }}
                    onBlur={() => setIsFocused(false)}
                    placeholder={placeholder}
                    disabled={disabled}
                    autoComplete="off"
                    required
                    className={cn(inputClasses, 'pl-10')}
                />
            </div>

            {/* Dropdown */}
            {isOpen && suggestions.length > 0 && (
                <div
                    ref={dropdownRef}
                    className="absolute z-50 w-full mt-1 bg-background border border-border rounded-md shadow-lg overflow-hidden"
                >
                    {suggestions.map((user, index) => (
                        <button
                            key={user.email}
                            type="button"
                            onClick={() => handleSelect(user)}
                            className={cn(
                                'w-full px-3 py-2 text-left text-sm hover:bg-accent transition-colors',
                                'flex items-center gap-3',
                                selectedIndex === index && 'bg-accent'
                            )}
                        >
                            {user.avatar_url ? (
                                <img
                                    src={user.avatar_url}
                                    alt=""
                                    className="h-8 w-8 rounded-full object-cover"
                                />
                            ) : (
                                <div className="h-8 w-8 rounded-full bg-muted flex items-center justify-center">
                                    <User className="h-4 w-4 text-muted-foreground" />
                                </div>
                            )}
                            <div className="flex flex-col min-w-0">
                                <span className="font-medium truncate">{user.name || user.email}</span>
                                {user.name && (
                                    <span className="text-xs text-muted-foreground truncate">{user.email}</span>
                                )}
                            </div>
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

            {/* Loading indicator */}
            {isSearching && isFocused && value.length >= MIN_QUERY_LENGTH && (
                <div className="absolute right-3 top-1/2 -translate-y-1/2">
                    <div className="h-4 w-4 border-2 border-muted border-t-foreground rounded-full animate-spin" />
                </div>
            )}
        </div>
    )
}
