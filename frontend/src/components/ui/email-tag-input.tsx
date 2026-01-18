import { X } from 'lucide-react'
import { type KeyboardEvent, useCallback, useRef, useState } from 'react'

import { cn } from '@/lib/utils'

/** Regex for basic email validation */
const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

/** Delimiters that trigger email extraction */
const DELIMITERS = /[,;\s\n]+/

interface EmailTagInputProps {
  value: string[]
  onChange: (emails: string[]) => void
  placeholder?: string
  disabled?: boolean
  className?: string
  id?: string
  maxEmails?: number
}

/**
 * Email tag input component for entering multiple email addresses.
 *
 * Features:
 * - Display emails as removable tags
 * - Auto-split on paste (comma, semicolon, newline, space)
 * - Visual validation feedback (red border for invalid emails)
 * - Keyboard navigation (Backspace to delete, Enter/Tab/comma to add)
 */
export function EmailTagInput({
  value,
  onChange,
  placeholder = 'Enter email addresses...',
  disabled = false,
  className,
  id,
  maxEmails = 100,
}: EmailTagInputProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [inputValue, setInputValue] = useState('')

  const isValidEmail = useCallback((email: string) => {
    return EMAIL_REGEX.test(email.trim())
  }, [])

  const addEmails = useCallback(
    (text: string) => {
      // Split by delimiters and filter valid emails
      const newEmails = text
        .split(DELIMITERS)
        .map((e) => e.trim().toLowerCase())
        .filter((e) => e.length > 0)

      if (newEmails.length === 0) return

      // Add unique, non-duplicate emails
      const existingSet = new Set(value.map((e) => e.toLowerCase()))
      const uniqueNew = newEmails.filter((e) => !existingSet.has(e))

      if (uniqueNew.length > 0) {
        const remaining = maxEmails - value.length
        const toAdd = uniqueNew.slice(0, remaining)
        onChange([...value, ...toAdd])
      }

      setInputValue('')
    },
    [value, onChange, maxEmails]
  )

  const removeEmail = useCallback(
    (index: number) => {
      onChange(value.filter((_, i) => i !== index))
    },
    [value, onChange]
  )

  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLInputElement>) => {
      const trimmed = inputValue.trim()

      if (e.key === 'Enter' || e.key === 'Tab' || e.key === ',') {
        if (trimmed) {
          e.preventDefault()
          addEmails(trimmed)
        }
      } else if (e.key === 'Backspace' && !inputValue && value.length > 0) {
        // Delete last email when backspace on empty input
        removeEmail(value.length - 1)
      }
    },
    [inputValue, value, addEmails, removeEmail]
  )

  const handlePaste = useCallback(
    (e: React.ClipboardEvent) => {
      e.preventDefault()
      const pastedText = e.clipboardData.getData('text')
      addEmails(pastedText)
    },
    [addEmails]
  )

  const handleBlur = useCallback(() => {
    const trimmed = inputValue.trim()
    if (trimmed) {
      addEmails(trimmed)
    }
  }, [inputValue, addEmails])

  const handleContainerClick = useCallback(() => {
    inputRef.current?.focus()
  }, [])

  return (
    // biome-ignore lint/a11y/noStaticElementInteractions: Click delegates to input focus
    <div
      onClick={handleContainerClick}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          handleContainerClick()
        }
      }}
      className={cn(
        'flex flex-wrap items-start content-start gap-1.5 p-2 min-h-[80px] max-h-[200px] overflow-y-auto',
        'border border-input rounded-md bg-background',
        'focus-within:outline-none focus-within:ring-1 focus-within:ring-ring focus-within:ring-offset-0',
        disabled && 'opacity-50 cursor-not-allowed',
        className
      )}
    >
      {/* Email tags */}
      {value.map((email, index) => {
        const isValid = isValidEmail(email)
        return (
          <span
            key={`${email}-${String(index)}`}
            className={cn(
              'inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-sm max-w-full',
              'transition-colors shrink-0',
              isValid
                ? 'bg-primary/10 text-primary border border-primary/20'
                : 'bg-destructive/10 text-destructive border border-destructive/30'
            )}
          >
            <span className="truncate">{email}</span>
            {!disabled && (
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation()
                  removeEmail(index)
                }}
                className={cn(
                  'rounded-full p-0.5 hover:bg-black/10 dark:hover:bg-white/10 shrink-0',
                  'focus:outline-none focus:ring-1 focus:ring-ring'
                )}
                tabIndex={-1}
              >
                <X className="h-3 w-3" />
              </button>
            )}
          </span>
        )
      })}

      {/* Input field */}
      {value.length < maxEmails && (
        <input
          ref={inputRef}
          id={id}
          type="text"
          value={inputValue}
          onChange={(e) => {
            setInputValue(e.target.value)
          }}
          onKeyDown={handleKeyDown}
          onPaste={handlePaste}
          onBlur={handleBlur}
          placeholder={value.length === 0 ? placeholder : ''}
          disabled={disabled}
          autoComplete="off"
          className={cn(
            'flex-1 min-w-[120px] h-6 outline-none bg-transparent text-sm',
            'placeholder:text-muted-foreground'
          )}
        />
      )}
    </div>
  )
}
