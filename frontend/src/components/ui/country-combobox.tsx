import { Check, ChevronsUpDown } from "lucide-react"
import * as React from "react"

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
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import { COUNTRIES, type Country,getCountryByCode } from "@/lib/countries"
import { cn } from "@/lib/utils"

// Popular countries shown at top
const POPULAR_CODES = ["US", "GB", "CA", "DE"]
const POPULAR_COUNTRIES = POPULAR_CODES.map((code) =>
  COUNTRIES.find((c) => c.code === code)
).filter((c): c is Country => c !== undefined)

// Other countries (excluding popular ones)
const OTHER_COUNTRIES = COUNTRIES.filter((c) => !POPULAR_CODES.includes(c.code))

interface CountryComboboxProps {
  value: string
  onValueChange: (value: string) => void
  placeholder?: string
  className?: string
}

export function CountryCombobox({
  value,
  onValueChange,
  placeholder = "Select country...",
  className,
}: CountryComboboxProps) {
  const [open, setOpen] = React.useState(false)
  const selectedCountry = getCountryByCode(value)

  const renderCountryItem = (country: Country) => (
    <CommandItem
      key={country.code}
      value={`${country.name} ${country.code}`}
      onSelect={() => {
        onValueChange(country.code)
        setOpen(false)
      }}
    >
      <Check
        className={cn(
          "mr-2 h-4 w-4",
          value === country.code ? "opacity-100" : "opacity-0"
        )}
      />
      <span className="mr-2">{country.flag}</span>
      <span>{country.name}</span>
      <span className="ml-auto text-xs text-muted-foreground">
        {country.code}
      </span>
    </CommandItem>
  )

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          role="combobox"
          aria-expanded={open}
          className={cn("w-full justify-between font-normal", className)}
        >
          {selectedCountry ? (
            <span className="flex items-center gap-2">
              <span>{selectedCountry.flag}</span>
              <span className="truncate">{selectedCountry.name}</span>
            </span>
          ) : (
            <span className="text-muted-foreground">{placeholder}</span>
          )}
          <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[300px] p-0" align="start">
        <Command>
          <CommandInput placeholder="Search country..." />
          <CommandList>
            <CommandEmpty>No country found.</CommandEmpty>
            <CommandGroup heading="Popular">
              {POPULAR_COUNTRIES.map(renderCountryItem)}
            </CommandGroup>
            <CommandSeparator />
            <CommandGroup heading="All countries">
              {OTHER_COUNTRIES.map(renderCountryItem)}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  )
}
