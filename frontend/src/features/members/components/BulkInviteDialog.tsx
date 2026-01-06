import { AlertCircle, Check, ChevronsUpDown, Info, Upload, Users } from "lucide-react"
import Papa from "papaparse"
import { useCallback, useMemo, useRef, useState } from "react"

import { Button } from "@/components/ui/button"
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
} from "@/components/ui/command"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { EmailTagInput } from "@/components/ui/email-tag-input"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { useCurrentUser } from "@/features/auth/queries"
import { useOrganization } from "@/features/organization/queries"
import { COUNTRIES, type Country, getCountryByCode } from "@/lib/countries"
import { cn } from "@/lib/utils"

import {
  analyzePhones,
  type ColumnType,
  EMAIL_REGEX,
  extractCountryFromPhone,
  parseCsvData,
  type ParsedRow,
  parseRowsWithMappings,
} from "../utils/csv-import"

type Tab = "manual" | "csv"
type CsvStep = "upload" | "mapping" | "preview"

// Popular countries for the country code selector
const POPULAR_CODES = ["US", "GB", "CA", "DE", "PL", "FR"]
const POPULAR_COUNTRIES = POPULAR_CODES.map((code) =>
  COUNTRIES.find((c) => c.code === code)
).filter((c): c is Country => c !== undefined)
const OTHER_COUNTRIES = COUNTRIES.filter((c) => !POPULAR_CODES.includes(c.code))

interface BulkInviteMember {
  email: string
  name: string
  phone: string
  role: string
}

interface BulkInviteDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onInvite: (members: BulkInviteMember[]) => void
  isLoading?: boolean
}

/**
 * Bulk invite dialog with tabs for manual email entry and CSV import.
 * CSV import includes inline column mapping and preview.
 */
export function BulkInviteDialog({
  open,
  onOpenChange,
  onInvite,
  isLoading = false,
}: BulkInviteDialogProps) {
  // Organization and user data for country detection
  const { data: organization } = useOrganization()
  const { data: currentUser } = useCurrentUser()

  // Tab state
  const [activeTab, setActiveTab] = useState<Tab>("manual")

  // Manual entry state
  const [emails, setEmails] = useState<string[]>([])
  const [role, setRole] = useState<"member" | "admin">("member")

  // CSV import state
  const [csvStep, setCsvStep] = useState<CsvStep>("upload")
  const [headers, setHeaders] = useState<string[]>([])
  const [rawData, setRawData] = useState<string[][]>([])
  const [columnMappings, setColumnMappings] = useState<Record<number, ColumnType>>({})
  const [parsedRows, setParsedRows] = useState<ParsedRow[]>([])
  const [assumedCountryCode, setAssumedCountryCode] = useState<Country | null>(null)
  const [phonesNeedingCountryCode, setPhonesNeedingCountryCode] = useState(0)
  const [countryCodePopoverOpen, setCountryCodePopoverOpen] = useState(false)

  const fileInputRef = useRef<HTMLInputElement>(null)

  // Determine default country code from organization billing or user phone
  const orgBillingCountry = organization?.billing.address.country
  const userPhoneNumber = currentUser?.user.phone_number

  const defaultCountryCode = useMemo((): Country | null => {
    // Priority 1: Organization billing address country
    if (orgBillingCountry) {
      const country = getCountryByCode(orgBillingCountry)
      if (country) return country
    }

    // Priority 2: User's phone country
    if (userPhoneNumber) {
      const country = extractCountryFromPhone(userPhoneNumber)
      if (country) return country
    }

    return null
  }, [orgBillingCountry, userPhoneNumber])

  const reset = () => {
    setEmails([])
    setRole("member")
    setActiveTab("manual")
    setCsvStep("upload")
    setHeaders([])
    setRawData([])
    setColumnMappings({})
    setParsedRows([])
    setAssumedCountryCode(null)
    setPhonesNeedingCountryCode(0)
    setCountryCodePopoverOpen(false)
  }

  const handleClose = (newOpen: boolean) => {
    if (!newOpen) reset()
    onOpenChange(newOpen)
  }

  const handleManualInvite = () => {
    if (emails.length === 0) return

    const members: BulkInviteMember[] = emails.map((email) => ({
      email,
      name: "",
      phone: "",
      role,
    }))

    onInvite(members)
  }

  // Handle file selection
  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    Papa.parse<string[]>(file, {
      complete: (results) => {
        const data = results.data.filter((row) => row.some((cell) => cell.trim()))

        if (data.length === 0) return

        const parsed = parseCsvData(data)

        setHeaders(parsed.headers)
        setRawData(parsed.rows)
        setColumnMappings(parsed.columnMappings)
        setCsvStep("mapping")
      },
      skipEmptyLines: true,
    })

    // Reset file input so same file can be selected again
    e.target.value = ""
  }, [])

  const openFilePicker = () => {
    fileInputRef.current?.click()
  }

  // Column mapping change handler
  const handleColumnMappingChange = useCallback((colIndex: number, type: ColumnType) => {
    setColumnMappings((prev) => {
      const updated = { ...prev }

      // If another column already has this type (except 'skip'), clear it
      if (type !== "skip") {
        Object.entries(updated).forEach(([key, value]) => {
          if (value === type && Number(key) !== colIndex) {
            updated[Number(key)] = "skip"
          }
        })
      }

      updated[colIndex] = type
      return updated
    })
  }, [])

  // Parse rows and move to preview step
  const handleContinueToPreview = useCallback(() => {
    if (!Object.values(columnMappings).includes("email")) {
      setParsedRows([])
      return
    }

    // Get phone column to analyze phones
    const phoneColIndex = Object.entries(columnMappings).find(([, t]) => t === "phone")?.[0]
    const rawPhones = phoneColIndex !== undefined
      ? rawData.map((row) => row[Number(phoneColIndex)] || "")
      : []

    // Analyze phones to determine if we need to assume a country code
    const userCountry = userPhoneNumber
      ? extractCountryFromPhone(userPhoneNumber)
      : null
    const phoneAnalysis = analyzePhones(rawPhones, userCountry)

    // Track how many phones need country codes
    setPhonesNeedingCountryCode(phoneAnalysis.phonesNeedingCode)

    // Determine assumed country code:
    // 1. If phones look like US format, use US
    // 2. Otherwise use org billing country or user phone country
    // 3. If neither, default to US as fallback
    let countryCodeToAssume: Country | null = null
    if (phoneAnalysis.phonesNeedingCode > 0) {
      if (phoneAnalysis.looksLikeUS) {
        countryCodeToAssume = COUNTRIES.find((c) => c.code === "US") ?? null
      } else if (defaultCountryCode) {
        countryCodeToAssume = defaultCountryCode
      } else {
        // No default available - default to US as fallback
        countryCodeToAssume = COUNTRIES.find((c) => c.code === "US") ?? null
      }
    }
    setAssumedCountryCode(countryCodeToAssume)

    // Parse rows with the assumed dial code
    const parsed = parseRowsWithMappings(
      rawData,
      columnMappings,
      countryCodeToAssume?.dialCode
    )

    setParsedRows(parsed)
    setCsvStep("preview")
  }, [rawData, columnMappings, userPhoneNumber, defaultCountryCode])

  // Handle assumed country code change - re-parse all rows
  const handleAssumedCountryCodeChange = useCallback((countryCode: string) => {
    const newCountryCode = countryCode === "none"
      ? null
      : COUNTRIES.find((c) => c.code === countryCode) ?? null
    setAssumedCountryCode(newCountryCode)
    setCountryCodePopoverOpen(false)

    // Re-parse rows with the new assumed dial code
    const parsed = parseRowsWithMappings(
      rawData,
      columnMappings,
      newCountryCode?.dialCode
    )
    setParsedRows(parsed)
  }, [rawData, columnMappings])

  // Update a parsed row
  const updateParsedRow = useCallback((index: number, field: keyof ParsedRow, value: string) => {
    setParsedRows((prev) => {
      const updated = [...prev]
      const row = { ...updated[index] }

      if (field === "email") {
        row.email = value.toLowerCase()
        row.errors = row.errors.filter((e) => !e.includes("email"))
        if (!EMAIL_REGEX.test(row.email)) {
          row.errors.push("Invalid email format")
        }
      } else if (field === "name") {
        row.name = value
      } else if (field === "phone") {
        // When manually editing phone, store the raw value and mark as not assumed
        row.rawPhone = value
        row.phoneAssumed = false
        // Re-parse with assumed dial code if needed
        const parsed = parseRowsWithMappings([[value]], { 0: "phone" }, assumedCountryCode?.dialCode)
        row.phone = parsed[0]?.phone ?? ""
        row.errors = row.errors.filter((e) => !e.includes("phone"))
        if (value && !row.phone) {
          row.errors.push("Invalid phone format")
        }
      } else if (field === "role") {
        row.role = value === "admin" ? "admin" : "member"
      }

      updated[index] = row
      return updated
    })
  }, [assumedCountryCode?.dialCode])

  // Remove a row
  const removeRow = useCallback((index: number) => {
    setParsedRows((prev) => prev.filter((_, i) => i !== index))
  }, [])

  // Handle CSV import
  const handleCsvImport = useCallback(() => {
    const validRows = parsedRows.filter((row) => row.errors.length === 0 && row.email)
    if (validRows.length === 0) return

    onInvite(
      validRows.map((row) => ({
        email: row.email,
        name: row.name,
        phone: row.phone,
        role: row.role,
      }))
    )
  }, [parsedRows, onInvite])

  // Computed values
  const hasEmailColumn = Object.values(columnMappings).includes("email")
  const validRowCount = parsedRows.filter((r) => r.errors.length === 0 && r.email).length
  const errorRowCount = parsedRows.filter((r) => r.errors.length > 0).length

  // Dialog should be wider when showing CSV preview
  const dialogWidth = activeTab === "csv" && csvStep === "preview" ? "sm:max-w-4xl" : "sm:max-w-lg"

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className={cn(dialogWidth, "max-h-[85vh] overflow-hidden flex flex-col")}>
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Users className="h-5 w-5" />
            Bulk Invite Members
          </DialogTitle>
          <DialogDescription>
            {activeTab === "manual" && "Invite multiple members to your organization at once"}
            {activeTab === "csv" && csvStep === "upload" && "Upload a CSV file with member data"}
            {activeTab === "csv" && csvStep === "mapping" && "Map CSV columns to member fields"}
            {activeTab === "csv" && csvStep === "preview" && "Review and edit data before importing"}
          </DialogDescription>
        </DialogHeader>

        {/* Tab buttons */}
        <div className="flex gap-1 p-1 bg-muted rounded-lg">
          <button
            type="button"
            onClick={() => { setActiveTab("manual"); }}
            className={cn(
              "flex-1 px-3 py-1.5 text-sm font-medium rounded-md transition-colors",
              activeTab === "manual"
                ? "bg-background text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            Enter Emails
          </button>
          <button
            type="button"
            onClick={() => { setActiveTab("csv"); }}
            className={cn(
              "flex-1 px-3 py-1.5 text-sm font-medium rounded-md transition-colors",
              activeTab === "csv"
                ? "bg-background text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            Import CSV
          </button>
        </div>

        {/* Tab content - px-0.5 provides space for focus ring outside overflow boundary */}
        <div className="flex-1 overflow-auto py-2 px-0.5">
          {/* Manual entry tab */}
          {activeTab === "manual" && (
            <div className="space-y-4">
              <div>
                <label className="text-sm font-medium block mb-2">
                  Email addresses
                </label>
                <EmailTagInput
                  value={emails}
                  onChange={setEmails}
                  placeholder="Enter or paste email addresses..."
                  disabled={isLoading}
                />
                <p className="text-xs text-muted-foreground mt-1.5">
                  Press Enter, Tab, or comma to add. Paste multiple emails separated by commas or newlines.
                </p>
              </div>

              <div>
                <label className="text-sm font-medium block mb-2">
                  Role for all invitees
                </label>
                <Select
                  value={role}
                  onValueChange={(value) => { setRole(value as "member" | "admin"); }}
                  disabled={isLoading}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="member">Member</SelectItem>
                    <SelectItem value="admin">Admin</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          )}

          {/* CSV tab - Upload step */}
          {activeTab === "csv" && csvStep === "upload" && (
            <div className="space-y-4">
              <input
                ref={fileInputRef}
                type="file"
                accept=".csv,.txt"
                onChange={handleFileSelect}
                className="hidden"
              />

              <div
                onClick={openFilePicker}
                className="border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors hover:border-primary/50"
              >
                <Upload className="h-10 w-10 mx-auto text-muted-foreground mb-3" />
                <p className="text-sm font-medium">Click to upload CSV</p>
                <p className="text-xs text-muted-foreground mt-1">
                  Import emails, names, phone numbers, and roles
                </p>
              </div>

              <div className="text-xs text-muted-foreground space-y-1">
                <p className="font-medium">Supported formats:</p>
                <ul className="list-disc list-inside space-y-0.5">
                  <li>Email column only</li>
                  <li>Email + Name + Phone + Role columns</li>
                  <li>Any column order (auto-detected)</li>
                </ul>
              </div>
            </div>
          )}

          {/* CSV tab - Mapping step */}
          {activeTab === "csv" && csvStep === "mapping" && (
            <div className="space-y-4">
              <div className="grid gap-3">
                {headers.map((header, index) => (
                  <div key={index} className="flex items-center gap-3">
                    <span className="w-28 text-sm truncate" title={header}>
                      {header}
                    </span>
                    <Select
                      value={columnMappings[index] ?? "skip"}
                      onValueChange={(value) => { handleColumnMappingChange(index, value as ColumnType); }}
                    >
                      <SelectTrigger className="w-32">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="email">Email *</SelectItem>
                        <SelectItem value="name">Name</SelectItem>
                        <SelectItem value="phone">Phone</SelectItem>
                        <SelectItem value="role">Role</SelectItem>
                        <SelectItem value="skip">Skip</SelectItem>
                      </SelectContent>
                    </Select>
                    <span className="text-xs text-muted-foreground truncate flex-1">
                      {rawData[0]?.[index] || "(empty)"}
                    </span>
                  </div>
                ))}
              </div>

              {!hasEmailColumn && (
                <div className="flex items-center gap-2 p-3 bg-destructive/10 text-destructive rounded-md text-sm">
                  <AlertCircle className="h-4 w-4 flex-shrink-0" />
                  <span>Please map at least one column as Email</span>
                </div>
              )}
            </div>
          )}

          {/* CSV tab - Preview step */}
          {activeTab === "csv" && csvStep === "preview" && (
            <div className="space-y-4">
              {/* Assumed country code banner */}
              {phonesNeedingCountryCode > 0 && (
                <div className="flex items-start gap-3 p-3 bg-blue-50 dark:bg-blue-950/30 text-blue-800 dark:text-blue-200 rounded-md text-sm">
                  <Info className="h-4 w-4 flex-shrink-0 mt-0.5" />
                  <div className="flex-1 space-y-2">
                    <p>
                      {phonesNeedingCountryCode} phone {phonesNeedingCountryCode === 1 ? "number doesn't" : "numbers don't"} have a country code.
                      {assumedCountryCode
                        ? ` We assumed ${assumedCountryCode.flag} ${assumedCountryCode.name} (${assumedCountryCode.dialCode}).`
                        : " Please select a country code to apply."}
                    </p>
                    <div className="flex items-center gap-2">
                      <span>Country code:</span>
                      <Popover open={countryCodePopoverOpen} onOpenChange={setCountryCodePopoverOpen}>
                        <PopoverTrigger asChild>
                          <Button
                            variant="outline"
                            role="combobox"
                            aria-expanded={countryCodePopoverOpen}
                            className="h-7 w-56 justify-between text-sm font-normal bg-white dark:bg-gray-800"
                          >
                            {assumedCountryCode ? (
                              <span className="flex items-center gap-1.5 truncate">
                                <span>{assumedCountryCode.flag}</span>
                                <span className="truncate">{assumedCountryCode.name}</span>
                                <span className="text-muted-foreground">({assumedCountryCode.dialCode})</span>
                              </span>
                            ) : (
                              <span className="text-muted-foreground">Don't add country code</span>
                            )}
                            <ChevronsUpDown className="ml-1 h-3.5 w-3.5 shrink-0 opacity-50" />
                          </Button>
                        </PopoverTrigger>
                        <PopoverContent className="w-[280px] p-0" align="start">
                          <Command>
                            <CommandInput placeholder="Search country..." />
                            <CommandList>
                              <CommandEmpty>No country found.</CommandEmpty>
                              <CommandGroup>
                                <CommandItem
                                  value="none"
                                  onSelect={() => { handleAssumedCountryCodeChange("none"); }}
                                >
                                  <Check
                                    className={cn(
                                      "mr-2 h-4 w-4",
                                      !assumedCountryCode ? "opacity-100" : "opacity-0"
                                    )}
                                  />
                                  <span>Don't add country code</span>
                                </CommandItem>
                              </CommandGroup>
                              <CommandSeparator />
                              <CommandGroup heading="Popular">
                                {POPULAR_COUNTRIES.map((country) => (
                                  <CommandItem
                                    key={country.code}
                                    value={`${country.name} ${country.code} ${country.dialCode}`}
                                    onSelect={() => { handleAssumedCountryCodeChange(country.code); }}
                                  >
                                    <Check
                                      className={cn(
                                        "mr-2 h-4 w-4",
                                        assumedCountryCode?.code === country.code ? "opacity-100" : "opacity-0"
                                      )}
                                    />
                                    <span className="mr-1.5">{country.flag}</span>
                                    <span className="truncate">{country.name}</span>
                                    <span className="ml-auto text-xs text-muted-foreground">{country.dialCode}</span>
                                  </CommandItem>
                                ))}
                              </CommandGroup>
                              <CommandSeparator />
                              <CommandGroup heading="All countries">
                                {OTHER_COUNTRIES.map((country) => (
                                  <CommandItem
                                    key={country.code}
                                    value={`${country.name} ${country.code} ${country.dialCode}`}
                                    onSelect={() => { handleAssumedCountryCodeChange(country.code); }}
                                  >
                                    <Check
                                      className={cn(
                                        "mr-2 h-4 w-4",
                                        assumedCountryCode?.code === country.code ? "opacity-100" : "opacity-0"
                                      )}
                                    />
                                    <span className="mr-1.5">{country.flag}</span>
                                    <span className="truncate">{country.name}</span>
                                    <span className="ml-auto text-xs text-muted-foreground">{country.dialCode}</span>
                                  </CommandItem>
                                ))}
                              </CommandGroup>
                            </CommandList>
                          </Command>
                        </PopoverContent>
                      </Popover>
                    </div>
                  </div>
                </div>
              )}

              {/* Summary */}
              <div className="flex items-center gap-4 text-sm">
                <span className="text-muted-foreground">
                  {validRowCount} valid {validRowCount === 1 ? "row" : "rows"}
                </span>
                {errorRowCount > 0 && (
                  <span className="text-destructive">
                    {errorRowCount} with errors
                  </span>
                )}
              </div>

              {/* Preview table */}
              <div className="border rounded-md overflow-auto max-h-[300px]">
                <table className="w-full text-sm">
                  <thead className="bg-muted sticky top-0 z-10">
                    <tr>
                      <th className="px-3 py-2 text-left font-medium">Email</th>
                      <th className="px-3 py-2 text-left font-medium">Name</th>
                      <th className="px-3 py-2 text-left font-medium">Phone</th>
                      <th className="px-3 py-2 text-left font-medium">Role</th>
                      <th className="px-3 py-2 w-10" />
                    </tr>
                  </thead>
                  <tbody className="divide-y">
                    {parsedRows.map((row, index) => (
                      <tr
                        key={index}
                        className={cn(row.errors.length > 0 && "bg-destructive/5")}
                      >
                        <td className="px-3 py-2">
                          <div className="relative">
                            <input
                              type="text"
                              value={row.email}
                              onChange={(e) => { updateParsedRow(index, "email", e.target.value); }}
                              className={cn(
                                "w-full px-2 py-1 text-sm bg-transparent border rounded",
                                row.errors.some((e) => e.toLowerCase().includes("email"))
                                  ? "border-destructive pr-6"
                                  : "border-transparent hover:border-border focus:border-ring"
                              )}
                            />
                            {row.errors.some((e) => e.toLowerCase().includes("email")) && (
                              <span
                                className="absolute right-1 top-1/2 -translate-y-1/2 text-destructive cursor-help"
                                title={row.errors.find((e) => e.toLowerCase().includes("email"))}
                              >
                                ⚠
                              </span>
                            )}
                          </div>
                        </td>
                        <td className="px-3 py-2">
                          <input
                            type="text"
                            value={row.name}
                            onChange={(e) => { updateParsedRow(index, "name", e.target.value); }}
                            className="w-full px-2 py-1 text-sm bg-transparent border border-transparent rounded hover:border-border focus:border-ring"
                          />
                        </td>
                        <td className="px-3 py-2">
                          <div className="relative">
                            <input
                              type="text"
                              value={row.phone}
                              onChange={(e) => { updateParsedRow(index, "phone", e.target.value); }}
                              placeholder="+1..."
                              className={cn(
                                "w-full px-2 py-1 text-sm bg-transparent border rounded",
                                row.errors.some((e) => e.toLowerCase().includes("phone"))
                                  ? "border-destructive pr-6"
                                  : "border-transparent hover:border-border focus:border-ring"
                              )}
                            />
                            {row.errors.some((e) => e.toLowerCase().includes("phone")) && (
                              <span
                                className="absolute right-1 top-1/2 -translate-y-1/2 text-destructive cursor-help"
                                title={row.errors.find((e) => e.toLowerCase().includes("phone"))}
                              >
                                ⚠
                              </span>
                            )}
                          </div>
                        </td>
                        <td className="px-3 py-2">
                          <Select
                            value={row.role}
                            onValueChange={(value) => { updateParsedRow(index, "role", value); }}
                          >
                            <SelectTrigger className="h-7 text-sm">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="member">Member</SelectItem>
                              <SelectItem value="admin">Admin</SelectItem>
                            </SelectContent>
                          </Select>
                        </td>
                        <td className="px-3 py-2">
                          <button
                            type="button"
                            onClick={() => { removeRow(index); }}
                            className="text-muted-foreground hover:text-destructive text-xs"
                          >
                            Remove
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {errorRowCount > 0 && (
                <p className="text-xs text-muted-foreground">
                  Rows with errors will be skipped. Fix them above or remove them.
                </p>
              )}
            </div>
          )}
        </div>

        {/* Footer buttons */}
        <DialogFooter>
          {/* Cancel / Back button */}
          {activeTab === "manual" && (
            <Button variant="outline" onClick={() => { handleClose(false); }} disabled={isLoading}>
              Cancel
            </Button>
          )}
          {activeTab === "csv" && csvStep === "upload" && (
            <Button variant="outline" onClick={() => { handleClose(false); }} disabled={isLoading}>
              Cancel
            </Button>
          )}
          {activeTab === "csv" && csvStep === "mapping" && (
            <Button variant="outline" onClick={() => { setCsvStep("upload"); }}>
              Back
            </Button>
          )}
          {activeTab === "csv" && csvStep === "preview" && (
            <Button variant="outline" onClick={() => { setCsvStep("mapping"); }}>
              Back
            </Button>
          )}

          {/* Action button */}
          {activeTab === "manual" && (
            <Button
              onClick={handleManualInvite}
              disabled={emails.length === 0 || isLoading}
            >
              {isLoading ? "Inviting..." : `Invite ${emails.length > 0 ? String(emails.length) : ""} ${emails.length === 1 ? "Member" : "Members"}`}
            </Button>
          )}
          {activeTab === "csv" && csvStep === "mapping" && (
            <Button onClick={handleContinueToPreview} disabled={!hasEmailColumn}>
              Continue
            </Button>
          )}
          {activeTab === "csv" && csvStep === "preview" && (
            <Button onClick={handleCsvImport} disabled={validRowCount === 0 || isLoading}>
              {isLoading ? "Inviting..." : `Invite ${String(validRowCount)} ${validRowCount === 1 ? "Member" : "Members"}`}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
