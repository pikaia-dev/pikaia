import { describe, expect, it } from "vitest"

import {
    emailUpdateSchema,
    phoneOtpSchema,
    profileNameSchema,
} from "./schema"

describe("profileNameSchema", () => {
    it("validates a correct name", () => {
        const result = profileNameSchema.safeParse({ name: "John Doe" })
        expect(result.success).toBe(true)
    })

    it("rejects empty name", () => {
        const result = profileNameSchema.safeParse({ name: "" })
        expect(result.success).toBe(false)
    })

    it("rejects very long name", () => {
        const result = profileNameSchema.safeParse({ name: "a".repeat(256) })
        expect(result.success).toBe(false)
    })
})

describe("emailUpdateSchema", () => {
    it("validates a correct email", () => {
        const result = emailUpdateSchema.safeParse({ email: "test@example.com" })
        expect(result.success).toBe(true)
    })

    it("rejects invalid email format", () => {
        const result = emailUpdateSchema.safeParse({ email: "not-an-email" })
        expect(result.success).toBe(false)
    })

    it("rejects empty email", () => {
        const result = emailUpdateSchema.safeParse({ email: "" })
        expect(result.success).toBe(false)
    })
})

describe("phoneOtpSchema", () => {
    it("validates a 6-digit code", () => {
        const result = phoneOtpSchema.safeParse({ otp_code: "123456" })
        expect(result.success).toBe(true)
    })

    it("rejects code with less than 6 digits", () => {
        const result = phoneOtpSchema.safeParse({ otp_code: "12345" })
        expect(result.success).toBe(false)
    })

    it("rejects code with more than 6 digits", () => {
        const result = phoneOtpSchema.safeParse({ otp_code: "1234567" })
        expect(result.success).toBe(false)
    })

    it("rejects code with non-digit characters", () => {
        const result = phoneOtpSchema.safeParse({ otp_code: "12345a" })
        expect(result.success).toBe(false)
    })
})
