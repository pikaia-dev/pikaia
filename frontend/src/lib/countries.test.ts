import { describe, expect, it } from "vitest"

import {
    getCountryByCode,
    getDialCode,
    getPostalCodeLabel,
    getStateLabel,
    getVatPrefix,
    isEuCountry,
    shouldShowTaxId,
    updateVatIdForCountryChange,
} from "./countries"

describe("getDialCode", () => {
    it("returns correct dial code for US", () => {
        expect(getDialCode("US")).toBe("+1")
    })

    it("returns correct dial code for Poland", () => {
        expect(getDialCode("PL")).toBe("+48")
    })

    it("returns +1 as fallback for unknown country", () => {
        expect(getDialCode("XX")).toBe("+1")
    })
})

describe("getCountryByCode", () => {
    it("returns country object for valid code", () => {
        const country = getCountryByCode("DE")
        expect(country).toBeDefined()
        expect(country?.name).toBe("Germany")
        expect(country?.vatPrefix).toBe("DE")
    })

    it("returns undefined for invalid code", () => {
        expect(getCountryByCode("XX")).toBeUndefined()
    })
})

describe("isEuCountry", () => {
    it("returns true for EU countries", () => {
        expect(isEuCountry("DE")).toBe(true)
        expect(isEuCountry("FR")).toBe(true)
        expect(isEuCountry("PL")).toBe(true)
    })

    it("returns false for non-EU countries", () => {
        expect(isEuCountry("US")).toBe(false)
        expect(isEuCountry("GB")).toBe(false)
        expect(isEuCountry("CH")).toBe(false)
    })
})

describe("getVatPrefix", () => {
    it("returns correct prefix for EU countries", () => {
        expect(getVatPrefix("DE")).toBe("DE")
        expect(getVatPrefix("AT")).toBe("ATU")
        expect(getVatPrefix("GR")).toBe("EL") // Greece uses EL
    })

    it("returns undefined for non-EU countries", () => {
        expect(getVatPrefix("US")).toBeUndefined()
        expect(getVatPrefix("GB")).toBeUndefined()
    })
})

describe("updateVatIdForCountryChange", () => {
    it("adds prefix when switching to EU country with empty VAT", () => {
        const result = updateVatIdForCountryChange("", "US", "DE")
        expect(result).toBe("DE")
    })

    it("replaces prefix when switching between EU countries", () => {
        const result = updateVatIdForCountryChange("DE123456789", "DE", "FR")
        expect(result).toBe("FR123456789")
    })

    it("removes prefix when switching from EU to non-EU", () => {
        const result = updateVatIdForCountryChange("DE123456789", "DE", "US")
        expect(result).toBe("123456789")
    })

    it("preserves VAT ID when switching between non-EU countries", () => {
        const result = updateVatIdForCountryChange("TAX123", "US", "CA")
        expect(result).toBe("TAX123")
    })
})

describe("shouldShowTaxId", () => {
    it("returns true for EU countries", () => {
        expect(shouldShowTaxId("DE")).toBe(true)
        expect(shouldShowTaxId("FR")).toBe(true)
    })

    it("returns false for exempt countries", () => {
        expect(shouldShowTaxId("US")).toBe(false)
        expect(shouldShowTaxId("CA")).toBe(false)
        expect(shouldShowTaxId("HK")).toBe(false)
        expect(shouldShowTaxId("SG")).toBe(false)
    })

    it("returns true for other countries", () => {
        expect(shouldShowTaxId("GB")).toBe(true) // UK not exempt
        expect(shouldShowTaxId("AU")).toBe(true) // Australia not exempt
    })

    it("returns false for empty country code", () => {
        expect(shouldShowTaxId("")).toBe(false)
    })
})

describe("getPostalCodeLabel", () => {
    it("returns ZIP code for US", () => {
        expect(getPostalCodeLabel("US")).toBe("ZIP code")
    })

    it("returns Postcode for UK/AU/NZ", () => {
        expect(getPostalCodeLabel("GB")).toBe("Postcode")
        expect(getPostalCodeLabel("AU")).toBe("Postcode")
        expect(getPostalCodeLabel("NZ")).toBe("Postcode")
    })

    it("returns Postal code for other countries", () => {
        expect(getPostalCodeLabel("DE")).toBe("Postal code")
        expect(getPostalCodeLabel("PL")).toBe("Postal code")
    })
})

describe("getStateLabel", () => {
    it("returns State for US/AU", () => {
        expect(getStateLabel("US")).toBe("State")
        expect(getStateLabel("AU")).toBe("State")
    })

    it("returns Province for Canada", () => {
        expect(getStateLabel("CA")).toBe("Province")
    })

    it("returns County for UK/Ireland", () => {
        expect(getStateLabel("GB")).toBe("County")
        expect(getStateLabel("IE")).toBe("County")
    })

    it("returns State / Province for other countries", () => {
        expect(getStateLabel("DE")).toBe("State / Province")
        expect(getStateLabel("PL")).toBe("State / Province")
    })
})
