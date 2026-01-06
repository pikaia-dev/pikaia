/**
 * CSV import utilities for bulk member invite.
 *
 * Extracted for testability - all parsing and detection logic lives here.
 */

import { COUNTRIES, type Country } from "@/lib/countries"

/** Email validation regex */
export const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

/** Phone validation regex (basic E.164-like) */
export const PHONE_REGEX = /^\+[0-9]{8,15}$/

/** Common dial codes sorted by length (longest first for matching) */
const DIAL_CODES_BY_LENGTH = COUNTRIES
  .map((c) => ({ code: c.code, dialCode: c.dialCode.replace("+", "") }))
  .sort((a, b) => b.dialCode.length - a.dialCode.length)

/** Column types we can map */
export type ColumnType = "email" | "name" | "phone" | "role" | "skip"

/** Parsed row with validation errors */
export interface ParsedRow {
  email: string
  name: string
  phone: string
  /** The original phone value before normalization */
  rawPhone: string
  /** Whether a country code was assumed for this phone */
  phoneAssumed: boolean
  role: string
  errors: string[]
}

/** Result of CSV parsing */
export interface CsvParseResult {
  headers: string[]
  rows: string[][]
  columnMappings: Record<number, ColumnType>
  hasHeader: boolean
}

/** Common header keywords */
const HEADER_KEYWORDS = ["email", "e-mail", "name", "phone", "mobile", "role", "type", "permission"]

/**
 * Detect if the first row is a header row.
 *
 * Rules:
 * - It's a header if it contains header keywords AND no emails
 * - It's data if any cell looks like an email
 */
export function detectHasHeader(firstRow: string[]): boolean {
  const hasHeaderKeyword = firstRow.some((cell) =>
    HEADER_KEYWORDS.some((kw) => cell.toLowerCase().includes(kw))
  )
  const hasEmailInFirstRow = firstRow.some((cell) => EMAIL_REGEX.test(cell.trim()))

  // Only treat as header if it has header keywords and NO emails
  return hasHeaderKeyword && !hasEmailInFirstRow
}

/**
 * Auto-detect column type based on header name and sample content.
 *
 * Priority:
 * 1. Header name matching (email, name, phone, role keywords)
 * 2. Content pattern matching:
 *    - Contains @ → email
 *    - Looks like phone number → phone
 *    - Looks like role → role
 *    - Text only → name
 */
export function detectColumnType(header: string, samples: string[]): ColumnType {
  const h = header.toLowerCase()

  // Check header name first
  if (h.includes("email") || h.includes("e-mail")) return "email"
  if (h.includes("name") || h.includes("full_name") || h.includes("fullname")) return "name"
  if (h.includes("phone") || h.includes("mobile") || h.includes("tel")) return "phone"
  if (h.includes("role") || h.includes("type") || h.includes("permission")) return "role"

  // Check content patterns
  const validSamples = samples.filter((s) => s.trim().length > 0).slice(0, 10)
  if (validSamples.length === 0) return "skip"

  // Check if most samples look like emails (>= 50% with @, and most pass email regex)
  const emailLikeSamples = validSamples.filter((s) => s.includes("@"))
  if (emailLikeSamples.length >= validSamples.length * 0.5) {
    const validEmailCount = validSamples.filter((s) => EMAIL_REGEX.test(s.trim())).length
    if (validEmailCount >= validSamples.length * 0.5) return "email"
  }

  // Check if most samples look like phone numbers (>= 50%)
  const phoneLikeSamples = validSamples.filter((s) => {
    const cleaned = s.replace(/[\s\-()]/g, "")
    return /^\+?\d{7,}$/.test(cleaned)
  })
  if (phoneLikeSamples.length >= validSamples.length * 0.5) return "phone"

  // Check if most samples look like roles (>= 50%)
  const rolePatterns = ["admin", "member", "user", "viewer", "owner"]
  const roleLikeSamples = validSamples.filter((s) =>
    rolePatterns.some((r) => s.toLowerCase().includes(r))
  )
  if (roleLikeSamples.length >= validSamples.length * 0.5) return "role"

  // Default to name if most samples look like text (letters, spaces, hyphens, apostrophes)
  const nameLikeSamples = validSamples.filter((s) => /^[a-zA-Z\s\-']+$/.test(s.trim()))
  if (nameLikeSamples.length >= validSamples.length * 0.5) return "name"

  return "skip"
}

/**
 * Parse raw CSV data into headers, rows, and auto-detected column mappings.
 */
export function parseCsvData(data: string[][]): CsvParseResult {
  if (data.length === 0) {
    return { headers: [], rows: [], columnMappings: {}, hasHeader: false }
  }

  const firstRow = data[0]
  const hasHeader = detectHasHeader(firstRow)

  let headers: string[]
  let rows: string[][]

  if (hasHeader) {
    headers = firstRow.map((h, i) => h.trim() || `Column ${String(i + 1)}`)
    rows = data.slice(1)
  } else {
    // No header row - generate column names and include all rows as data
    headers = firstRow.map((_, i) => `Column ${String(i + 1)}`)
    rows = data
  }

  // Auto-detect column mappings
  const columnMappings: Record<number, ColumnType> = {}
  headers.forEach((header, index) => {
    const samples = rows.map((row) => row[index] || "")
    columnMappings[index] = detectColumnType(header, samples)
  })

  return { headers, rows, columnMappings, hasHeader }
}

/** Result of parsing a phone number */
export interface PhoneParseResult {
  /** The normalized E.164 phone number (or empty if invalid) */
  phone: string
  /** Whether the original had a country code */
  hadCountryCode: boolean
  /** The country code that was detected or applied */
  countryCode: string | null
  /** Whether an assumed country code was applied */
  assumedCountryCode: boolean
}

/**
 * Clean a phone string by removing formatting characters.
 * Handles formats like: (555) 123-4567, 555.123.4567, +1-555-123-4567
 */
export function cleanPhoneString(phone: string): string {
  return phone.replace(/[\s\-().]/g, "")
}

/**
 * Check if a cleaned phone number already has a country code.
 * Handles formats: +48..., 0048..., 1-555-123-4567 (US with leading 1)
 */
export function phoneHasCountryCode(cleaned: string): { hasCode: boolean; countryCode: string | null; nationalNumber: string } {
  // Starts with + → definitely has country code
  if (cleaned.startsWith("+")) {
    const digits = cleaned.slice(1)
    for (const { code, dialCode } of DIAL_CODES_BY_LENGTH) {
      if (digits.startsWith(dialCode)) {
        return { hasCode: true, countryCode: code, nationalNumber: digits.slice(dialCode.length) }
      }
    }
    // Has + but unrecognized code - still treat as having a code
    return { hasCode: true, countryCode: null, nationalNumber: digits }
  }

  // Starts with 00 → international format (00 = +)
  if (cleaned.startsWith("00")) {
    const digits = cleaned.slice(2)
    for (const { code, dialCode } of DIAL_CODES_BY_LENGTH) {
      if (digits.startsWith(dialCode)) {
        return { hasCode: true, countryCode: code, nationalNumber: digits.slice(dialCode.length) }
      }
    }
  }

  // US number with leading 1: 11 digits starting with 1 (e.g., 1-555-123-4567 → 15551234567)
  // This is the NANP format (North American Numbering Plan)
  if (cleaned.startsWith("1") && cleaned.length === 11 && /^\d+$/.test(cleaned)) {
    return { hasCode: true, countryCode: "US", nationalNumber: cleaned.slice(1) }
  }

  // No explicit country code prefix
  return { hasCode: false, countryCode: null, nationalNumber: cleaned }
}

/**
 * Detect if phone numbers in a list look like US format.
 * US patterns: 10 digits, dots as separators (555.123.4567), parentheses
 */
export function looksLikeUSPhones(phones: string[]): boolean {
  const validPhones = phones.filter((p) => p.trim().length > 0)
  if (validPhones.length === 0) return false

  let usLikeCount = 0
  for (const phone of validPhones) {
    const cleaned = cleanPhoneString(phone)
    // US patterns:
    // - Exactly 10 digits (no country code)
    // - Uses dots as separators
    // - Uses parentheses for area code
    const isUSLength = /^\d{10}$/.test(cleaned)
    const hasDots = phone.includes(".")
    const hasParens = phone.includes("(") && phone.includes(")")

    if (isUSLength || hasDots || hasParens) {
      usLikeCount++
    }
  }

  return usLikeCount >= validPhones.length * 0.5
}

/**
 * Extract country code from a user's E.164 phone number.
 * Returns the ISO country code (e.g., "PL", "US") or null if not found.
 */
export function extractCountryFromPhone(phone: string): Country | null {
  if (!phone) return null

  const cleaned = cleanPhoneString(phone)
  const { countryCode } = phoneHasCountryCode(cleaned)

  if (countryCode) {
    return COUNTRIES.find((c) => c.code === countryCode) ?? null
  }
  return null
}

/**
 * Normalize phone number to E.164 format.
 * Returns empty string if invalid.
 *
 * @param phone - Raw phone input
 * @param assumedDialCode - Optional dial code to apply if phone has no country code (e.g., "+48")
 */
export function normalizePhone(phone: string, assumedDialCode?: string): string {
  if (!phone) return ""

  const cleaned = cleanPhoneString(phone)
  const { hasCode, nationalNumber } = phoneHasCountryCode(cleaned)

  let normalized: string
  if (hasCode) {
    // Already has country code - normalize to + format
    if (cleaned.startsWith("+")) {
      normalized = cleaned
    } else if (cleaned.startsWith("00")) {
      normalized = "+" + cleaned.slice(2)
    } else {
      normalized = "+" + cleaned
    }
  } else if (assumedDialCode) {
    // Apply assumed country code
    const dialCode = assumedDialCode.startsWith("+") ? assumedDialCode : `+${assumedDialCode}`
    normalized = dialCode + nationalNumber
  } else {
    // No country code and none assumed - keep as-is if it looks like a valid local number
    // Must be 7-15 digits only (no letters, no special chars except what was cleaned)
    if (/^\d{7,15}$/.test(cleaned)) {
      return cleaned
    }
    return "" // Invalid - not a recognizable phone number
  }

  if (!PHONE_REGEX.test(normalized)) {
    return "" // Invalid
  }

  return normalized
}

/**
 * Parse a phone number with full details about country code detection.
 */
export function parsePhone(phone: string, assumedDialCode?: string): PhoneParseResult {
  if (!phone) {
    return { phone: "", hadCountryCode: false, countryCode: null, assumedCountryCode: false }
  }

  const cleaned = cleanPhoneString(phone)
  const { hasCode, countryCode } = phoneHasCountryCode(cleaned)
  const normalized = normalizePhone(phone, assumedDialCode)

  return {
    phone: normalized,
    hadCountryCode: hasCode,
    countryCode: hasCode ? countryCode : (assumedDialCode ? extractCountryCodeFromDialCode(assumedDialCode) : null),
    assumedCountryCode: !hasCode && !!assumedDialCode && normalized !== "",
  }
}

/**
 * Get country code from a dial code string.
 */
function extractCountryCodeFromDialCode(dialCode: string): string | null {
  const digits = dialCode.replace(/^\+/, "")
  for (const { code, dialCode: dc } of DIAL_CODES_BY_LENGTH) {
    if (dc === digits) return code
  }
  return null
}

/**
 * Analyze phone numbers in CSV data to determine if country codes need to be assumed.
 */
export interface PhoneAnalysis {
  /** Total phones in the data */
  totalPhones: number
  /** Phones that already have country codes */
  phonesWithCode: number
  /** Phones that need a country code */
  phonesNeedingCode: number
  /** Whether the phones look like US format */
  looksLikeUS: boolean
  /** Suggested country to assume (based on detected patterns) */
  suggestedCountry: Country | null
}

/**
 * Analyze a list of phone numbers to determine country code status.
 *
 * @param phones - Raw phone strings from CSV
 * @param userCountry - The current user's country (from their profile phone)
 */
export function analyzePhones(phones: string[], userCountry: Country | null): PhoneAnalysis {
  const validPhones = phones.filter((p) => p.trim().length > 0)

  let phonesWithCode = 0
  let phonesNeedingCode = 0

  for (const phone of validPhones) {
    const cleaned = cleanPhoneString(phone)
    const { hasCode } = phoneHasCountryCode(cleaned)
    if (hasCode) {
      phonesWithCode++
    } else {
      phonesNeedingCode++
    }
  }

  const isUS = looksLikeUSPhones(validPhones)

  // Determine suggested country
  let suggestedCountry: Country | null = null
  if (phonesNeedingCode > 0) {
    if (isUS) {
      // If phones look like US format, suggest US
      suggestedCountry = COUNTRIES.find((c) => c.code === "US") ?? null
    } else if (userCountry) {
      // Otherwise use the current user's country
      suggestedCountry = userCountry
    }
  }

  return {
    totalPhones: validPhones.length,
    phonesWithCode,
    phonesNeedingCode,
    looksLikeUS: isUS,
    suggestedCountry,
  }
}

/**
 * Normalize role to valid value.
 * Defaults to "member" if not recognized.
 */
export function normalizeRole(role: string): string {
  const lower = role.toLowerCase().trim()

  if (lower === "admin" || lower.includes("admin")) return "admin"
  if (lower === "member" || lower === "user" || lower === "") return "member"

  return "member" // Default
}

/**
 * Validate US phone number format.
 * US numbers must be exactly 10 digits (area code + 7 digit number).
 */
function isValidUSPhoneLength(phone: string): boolean {
  const cleaned = cleanPhoneString(phone)
  const { hasCode, nationalNumber } = phoneHasCountryCode(cleaned)

  if (hasCode) {
    // If it has a country code, check the national number length
    return nationalNumber.length === 10
  }
  // No country code - should be 10 digits
  return cleaned.length === 10
}

/**
 * Parse rows based on column mappings into validated ParsedRow objects.
 *
 * @param rows - Raw CSV data rows
 * @param columnMappings - Column index to type mapping
 * @param assumedDialCode - Optional dial code to apply to phones without country codes (e.g., "+48")
 */
export function parseRowsWithMappings(
  rows: string[][],
  columnMappings: Record<number, ColumnType>,
  assumedDialCode?: string
): ParsedRow[] {
  const emailColIndex = Object.entries(columnMappings).find(([, t]) => t === "email")?.[0]
  const nameColIndex = Object.entries(columnMappings).find(([, t]) => t === "name")?.[0]
  const phoneColIndex = Object.entries(columnMappings).find(([, t]) => t === "phone")?.[0]
  const roleColIndex = Object.entries(columnMappings).find(([, t]) => t === "role")?.[0]

  const isUSAssumed = assumedDialCode === "+1"

  return rows.map((row) => {
    const email = emailColIndex !== undefined
      ? (row[Number(emailColIndex)] || "").trim().toLowerCase()
      : ""
    const name = nameColIndex !== undefined
      ? (row[Number(nameColIndex)] || "").trim()
      : ""
    const rawPhone = phoneColIndex !== undefined
      ? (row[Number(phoneColIndex)] || "").trim()
      : ""
    const rawRole = roleColIndex !== undefined
      ? (row[Number(roleColIndex)] || "").trim()
      : ""

    const errors: string[] = []

    // Validate email
    if (!email) {
      errors.push("Email is required")
    } else if (!EMAIL_REGEX.test(email)) {
      errors.push("Invalid email format")
    }

    // Parse phone with assumed dial code
    const phoneResult = parsePhone(rawPhone, assumedDialCode)
    if (rawPhone && !phoneResult.phone) {
      errors.push("Invalid phone format")
    } else if (rawPhone && isUSAssumed && !isValidUSPhoneLength(rawPhone)) {
      // US phone validation - must be 10 digits
      errors.push("US phone must be 10 digits")
    }

    // Normalize role (defaults to member)
    const role = normalizeRole(rawRole)

    return {
      email,
      name,
      phone: phoneResult.phone,
      rawPhone,
      phoneAssumed: phoneResult.assumedCountryCode,
      role,
      errors,
    }
  })
}
