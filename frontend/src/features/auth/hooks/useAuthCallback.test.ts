import { act, renderHook, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { useAuthCallback } from "./useAuthCallback"

// Mock react-router-dom
const mockSearchParams = new URLSearchParams()
vi.mock("react-router-dom", () => ({
    useSearchParams: () => [mockSearchParams],
}))

// Mock Stytch client
const mockStytchClient = {
    magicLinks: {
        discovery: {
            authenticate: vi.fn(),
        },
        authenticate: vi.fn(),
    },
    oauth: {
        discovery: {
            authenticate: vi.fn(),
        },
    },
    discovery: {
        intermediateSessions: {
            exchange: vi.fn(),
        },
    },
    impersonation: {
        authenticate: vi.fn(),
    },
    session: {
        updateSession: vi.fn(),
    },
}

vi.mock("@stytch/react/b2b", () => ({
    useStytchB2BClient: () => mockStytchClient,
}))

// Mock org-api
vi.mock("../utils/org-api", () => ({
    createOrganization: vi.fn(),
    isConflictError: vi.fn((err) => {
        if (!(err instanceof Error)) return false
        const msg = err.message.toLowerCase()
        return msg.includes("slug") || msg.includes("name") || msg.includes("use")
    }),
}))

// Mock env
vi.mock("@/lib/env", () => ({
    config: {
        apiUrl: "http://localhost:8000/api/v1",
    },
}))

// Helper to create mock discovered organizations
function createMockOrg(id: string, membershipType: string) {
    return {
        organization: {
            organization_id: id,
            organization_name: `Org ${id}`,
            organization_slug: `org-${id}`,
        },
        membership: {
            type: membershipType,
            details: null,
            member: null,
        },
        member_authenticated: false,
    }
}

describe("useAuthCallback", () => {
    const mockOnRedirectToLogin = vi.fn()

    beforeEach(() => {
        vi.clearAllMocks()
        mockSearchParams.delete("stytch_token_type")
        mockSearchParams.delete("token")

        // Reset window.location
        Object.defineProperty(window, "location", {
            value: { href: "" },
            writable: true,
        })

        // Reset sessionStorage
        vi.stubGlobal("sessionStorage", {
            setItem: vi.fn(),
            getItem: vi.fn(),
            removeItem: vi.fn(),
            clear: vi.fn(),
        })
    })

    afterEach(() => {
        vi.unstubAllGlobals()
    })

    describe("initial state", () => {
        it("starts in loading state", () => {
            const { result } = renderHook(() =>
                useAuthCallback({ onRedirectToLogin: mockOnRedirectToLogin })
            )

            expect(result.current.state.isLoading).toBe(true)
            expect(result.current.state.error).toBeNull()
            expect(result.current.state.showOrgSelector).toBe(false)
        })
    })

    describe("when no token in URL", () => {
        it("calls onRedirectToLogin", async () => {
            renderHook(() =>
                useAuthCallback({ onRedirectToLogin: mockOnRedirectToLogin })
            )

            await waitFor(() => {
                expect(mockOnRedirectToLogin).toHaveBeenCalled()
            })
        })
    })

    describe("discovery token handling", () => {
        beforeEach(() => {
            mockSearchParams.set("stytch_token_type", "discovery")
            mockSearchParams.set("token", "discovery_token_123")
        })

        it("auto-logs in when single active organization", async () => {
            const mockOrg = createMockOrg("org-1", "active_member")
            mockStytchClient.magicLinks.discovery.authenticate.mockResolvedValueOnce(
                {
                    discovered_organizations: [mockOrg],
                    email_address: "user@example.com",
                    intermediate_session_token: "ist_123",
                }
            )
            mockStytchClient.discovery.intermediateSessions.exchange.mockResolvedValueOnce(
                {}
            )

            renderHook(() =>
                useAuthCallback({ onRedirectToLogin: mockOnRedirectToLogin })
            )

            await waitFor(() => {
                expect(
                    mockStytchClient.magicLinks.discovery.authenticate
                ).toHaveBeenCalledWith({
                    discovery_magic_links_token: "discovery_token_123",
                })
            })

            await waitFor(() => {
                expect(
                    mockStytchClient.discovery.intermediateSessions.exchange
                ).toHaveBeenCalledWith({
                    organization_id: "org-1",
                    session_duration_minutes: 43200, // 30 days
                })
            })

            expect(sessionStorage.setItem).toHaveBeenCalledWith(
                "stytch_just_logged_in",
                "true"
            )
            expect(window.location.href).toBe("/dashboard")
        })

        it("shows org selector when multiple organizations", async () => {
            const mockOrgs = [
                createMockOrg("org-1", "active_member"),
                createMockOrg("org-2", "active_member"),
            ]
            mockStytchClient.magicLinks.discovery.authenticate.mockResolvedValueOnce(
                {
                    discovered_organizations: mockOrgs,
                    email_address: "user@example.com",
                    intermediate_session_token: "ist_123",
                }
            )

            const { result } = renderHook(() =>
                useAuthCallback({ onRedirectToLogin: mockOnRedirectToLogin })
            )

            await waitFor(() => {
                expect(result.current.state.showOrgSelector).toBe(true)
            })

            expect(result.current.state.discoveredOrgs).toHaveLength(2)
            expect(result.current.state.email).toBe("user@example.com")
            expect(result.current.state.isLoading).toBe(false)
        })

        it("sets error state on authentication failure", async () => {
            mockStytchClient.magicLinks.discovery.authenticate.mockRejectedValueOnce(
                new Error("Invalid token")
            )

            const { result } = renderHook(() =>
                useAuthCallback({ onRedirectToLogin: mockOnRedirectToLogin })
            )

            await waitFor(() => {
                expect(result.current.state.error).toBe("Invalid token")
            })

            expect(result.current.state.isLoading).toBe(false)
        })
    })

    describe("OAuth token handling", () => {
        beforeEach(() => {
            mockSearchParams.set("stytch_token_type", "discovery_oauth")
            mockSearchParams.set("token", "oauth_token_123")
        })

        it("processes OAuth discovery tokens", async () => {
            const mockOrg = createMockOrg("org-1", "active_member")
            mockStytchClient.oauth.discovery.authenticate.mockResolvedValueOnce({
                discovered_organizations: [mockOrg],
                email_address: "user@example.com",
                intermediate_session_token: "ist_123",
            })
            mockStytchClient.discovery.intermediateSessions.exchange.mockResolvedValueOnce(
                {}
            )

            renderHook(() =>
                useAuthCallback({ onRedirectToLogin: mockOnRedirectToLogin })
            )

            await waitFor(() => {
                expect(
                    mockStytchClient.oauth.discovery.authenticate
                ).toHaveBeenCalledWith({
                    discovery_oauth_token: "oauth_token_123",
                })
            })
        })
    })

    describe("invite token handling", () => {
        beforeEach(() => {
            mockSearchParams.set("stytch_token_type", "multi_tenant_magic_links")
            mockSearchParams.set("token", "invite_token_123")
        })

        it("authenticates invite tokens directly", async () => {
            mockStytchClient.magicLinks.authenticate.mockResolvedValueOnce({})

            renderHook(() =>
                useAuthCallback({ onRedirectToLogin: mockOnRedirectToLogin })
            )

            await waitFor(() => {
                expect(mockStytchClient.magicLinks.authenticate).toHaveBeenCalledWith(
                    {
                        magic_links_token: "invite_token_123",
                        session_duration_minutes: 43200,
                    }
                )
            })

            expect(sessionStorage.setItem).toHaveBeenCalledWith(
                "stytch_just_logged_in",
                "true"
            )
            expect(window.location.href).toBe("/dashboard")
        })

        it("sets error on invite authentication failure", async () => {
            mockStytchClient.magicLinks.authenticate.mockRejectedValueOnce(
                new Error("Invite expired")
            )

            const { result } = renderHook(() =>
                useAuthCallback({ onRedirectToLogin: mockOnRedirectToLogin })
            )

            await waitFor(() => {
                expect(result.current.state.error).toBe("Invite expired")
            })
        })
    })

    describe("impersonation token handling", () => {
        beforeEach(() => {
            mockSearchParams.set("stytch_token_type", "impersonation")
            mockSearchParams.set("token", "impersonation_token_123")
        })

        it("authenticates impersonation tokens", async () => {
            mockStytchClient.impersonation.authenticate.mockResolvedValueOnce({})

            renderHook(() =>
                useAuthCallback({ onRedirectToLogin: mockOnRedirectToLogin })
            )

            await waitFor(() => {
                expect(
                    mockStytchClient.impersonation.authenticate
                ).toHaveBeenCalledWith({
                    impersonation_token: "impersonation_token_123",
                })
            })

            expect(window.location.href).toBe("/dashboard")
        })
    })

    describe("unknown token type", () => {
        it("redirects to login for unknown token types", async () => {
            mockSearchParams.set("stytch_token_type", "unknown_type")
            mockSearchParams.set("token", "some_token")

            renderHook(() =>
                useAuthCallback({ onRedirectToLogin: mockOnRedirectToLogin })
            )

            await waitFor(() => {
                expect(mockOnRedirectToLogin).toHaveBeenCalled()
            })
        })
    })

    describe("exchangeSession", () => {
        beforeEach(() => {
            mockSearchParams.set("stytch_token_type", "discovery")
            mockSearchParams.set("token", "token_123")
        })

        it("exchanges session for selected organization", async () => {
            const mockOrgs = [
                createMockOrg("org-1", "active_member"),
                createMockOrg("org-2", "active_member"),
            ]
            mockStytchClient.magicLinks.discovery.authenticate.mockResolvedValueOnce(
                {
                    discovered_organizations: mockOrgs,
                    email_address: "user@example.com",
                    intermediate_session_token: "ist_123",
                }
            )
            mockStytchClient.discovery.intermediateSessions.exchange.mockResolvedValueOnce(
                {}
            )

            const { result } = renderHook(() =>
                useAuthCallback({ onRedirectToLogin: mockOnRedirectToLogin })
            )

            await waitFor(() => {
                expect(result.current.state.showOrgSelector).toBe(true)
            })

            act(() => {
                result.current.exchangeSession("org-2")
            })

            await waitFor(() => {
                expect(
                    mockStytchClient.discovery.intermediateSessions.exchange
                ).toHaveBeenCalledWith({
                    organization_id: "org-2",
                    session_duration_minutes: 43200,
                })
            })
        })

        it("sets error on exchange failure", async () => {
            const mockOrgs = [
                createMockOrg("org-1", "active_member"),
                createMockOrg("org-2", "active_member"),
            ]
            mockStytchClient.magicLinks.discovery.authenticate.mockResolvedValueOnce(
                {
                    discovered_organizations: mockOrgs,
                    email_address: "user@example.com",
                    intermediate_session_token: "ist_123",
                }
            )
            mockStytchClient.discovery.intermediateSessions.exchange.mockRejectedValueOnce(
                new Error("Organization not found")
            )

            const { result } = renderHook(() =>
                useAuthCallback({ onRedirectToLogin: mockOnRedirectToLogin })
            )

            await waitFor(() => {
                expect(result.current.state.showOrgSelector).toBe(true)
            })

            act(() => {
                result.current.exchangeSession("org-invalid")
            })

            await waitFor(() => {
                expect(result.current.state.error).toBe("Organization not found")
            })
        })
    })

    describe("goToLogin", () => {
        it("calls onRedirectToLogin callback", async () => {
            mockSearchParams.set("stytch_token_type", "discovery")
            mockSearchParams.set("token", "token_123")

            const mockOrgs = [
                createMockOrg("org-1", "active_member"),
                createMockOrg("org-2", "active_member"),
            ]
            mockStytchClient.magicLinks.discovery.authenticate.mockResolvedValueOnce(
                {
                    discovered_organizations: mockOrgs,
                    email_address: "user@example.com",
                    intermediate_session_token: "ist_123",
                }
            )

            const { result } = renderHook(() =>
                useAuthCallback({ onRedirectToLogin: mockOnRedirectToLogin })
            )

            await waitFor(() => {
                expect(result.current.state.showOrgSelector).toBe(true)
            })

            act(() => {
                result.current.goToLogin()
            })

            expect(mockOnRedirectToLogin).toHaveBeenCalled()
        })
    })

    describe("token processing guard", () => {
        it("only processes token once (React Strict Mode protection)", async () => {
            mockSearchParams.set("stytch_token_type", "discovery")
            mockSearchParams.set("token", "token_123")

            const mockOrg = createMockOrg("org-1", "active_member")
            mockStytchClient.magicLinks.discovery.authenticate.mockResolvedValue({
                discovered_organizations: [mockOrg],
                email_address: "user@example.com",
                intermediate_session_token: "ist_123",
            })
            mockStytchClient.discovery.intermediateSessions.exchange.mockResolvedValue(
                {}
            )

            const { rerender } = renderHook(() =>
                useAuthCallback({ onRedirectToLogin: mockOnRedirectToLogin })
            )

            // Simulate React Strict Mode double-invoke
            rerender()
            rerender()

            await waitFor(() => {
                expect(
                    mockStytchClient.magicLinks.discovery.authenticate
                ).toHaveBeenCalledTimes(1)
            })
        })
    })
})
