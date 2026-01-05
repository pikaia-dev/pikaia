import { describe, expect, it } from "vitest"

import { emailSchema } from "./schema"

describe("emailSchema", () => {
    it("accepts valid email addresses", () => {
        expect(emailSchema.safeParse({ email: "test@example.com" }).success).toBe(
            true
        )
        expect(emailSchema.safeParse({ email: "user@domain.org" }).success).toBe(
            true
        )
        expect(
            emailSchema.safeParse({ email: "name.surname@company.co.uk" }).success
        ).toBe(true)
    })

    it("rejects invalid email addresses", () => {
        expect(emailSchema.safeParse({ email: "invalid" }).success).toBe(false)
        expect(emailSchema.safeParse({ email: "no@" }).success).toBe(false)
        expect(emailSchema.safeParse({ email: "@domain.com" }).success).toBe(false)
        expect(emailSchema.safeParse({ email: "" }).success).toBe(false)
    })

    it("rejects missing email", () => {
        expect(emailSchema.safeParse({}).success).toBe(false)
    })

    it("returns proper error message for invalid email", () => {
        const result = emailSchema.safeParse({ email: "invalid" })
        expect(result.success).toBe(false)
        if (!result.success) {
            expect(result.error.issues[0].message).toBe(
                "Please enter a valid email address"
            )
        }
    })
})
