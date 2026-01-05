/**
 * Passkey (WebAuthn) authentication hook.
 *
 * Provides methods for registering and authenticating with passkeys.
 * Uses the Web Authentication API (navigator.credentials) for cryptographic operations.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { useApi } from "@/hooks/useApi"

// --- API Types ---

interface PasskeyRegistrationOptionsResponse {
    challenge_id: string
    options: string // JSON string of PublicKeyCredentialCreationOptions
}

interface PasskeyRegistrationVerifyResponse {
    id: number
    name: string
    created_at: string
}

interface PasskeyAuthenticationOptionsResponse {
    challenge_id: string
    options: string // JSON string of PublicKeyCredentialRequestOptions
}

interface PasskeyAuthenticationVerifyResponse {
    session_token: string
    session_jwt: string
    member_id: string
    organization_id: string
    user_id: number
}

interface PasskeyListItem {
    id: number
    name: string
    created_at: string
    last_used_at: string | null
    backup_eligible: boolean
    backup_state: boolean
}

interface PasskeyListResponse {
    passkeys: PasskeyListItem[]
}

// --- LocalStorage Passkey Hint ---
// Used to remember if the user has logged in with a passkey before

const PASSKEY_HINT_KEY = "passkey_hint"

/**
 * Check if the user has previously logged in with a passkey.
 */
export function hasPasskeyHint(): boolean {
    if (typeof window === "undefined") return false
    return localStorage.getItem(PASSKEY_HINT_KEY) === "true"
}

/**
 * Set the passkey hint after successful passkey login.
 */
export function setPasskeyHint(): void {
    if (typeof window === "undefined") return
    localStorage.setItem(PASSKEY_HINT_KEY, "true")
}

/**
 * Clear the passkey hint (e.g., on logout or passkey deletion).
 */
export function clearPasskeyHint(): void {
    if (typeof window === "undefined") return
    localStorage.removeItem(PASSKEY_HINT_KEY)
}

// --- Helper Functions ---

/**
 * Check if WebAuthn is supported in the current browser.
 */
export function isWebAuthnSupported(): boolean {
    return (
        typeof window !== "undefined" &&
        typeof PublicKeyCredential !== "undefined" &&
        typeof navigator.credentials !== "undefined"
    )
}

/**
 * Check if the platform supports conditional UI (autofill passkeys).
 */
export async function isConditionalUISupported(): Promise<boolean> {
    if (!isWebAuthnSupported()) return false
    try {
        if (typeof PublicKeyCredential.isConditionalMediationAvailable === "function") {
            return await PublicKeyCredential.isConditionalMediationAvailable()
        }
        return false
    } catch {
        return false
    }
}

/**
 * Convert base64url string to ArrayBuffer.
 */
function base64urlToBuffer(base64url: string): ArrayBuffer {
    const base64 = base64url.replace(/-/g, "+").replace(/_/g, "/")
    const padding = "=".repeat((4 - (base64.length % 4)) % 4)
    const binary = atob(base64 + padding)
    const bytes = new Uint8Array(binary.length)
    for (let i = 0; i < binary.length; i++) {
        bytes[i] = binary.charCodeAt(i)
    }
    return bytes.buffer
}

/**
 * Convert ArrayBuffer to base64url string.
 */
function bufferToBase64url(buffer: ArrayBuffer): string {
    const bytes = new Uint8Array(buffer)
    let binary = ""
    for (let i = 0; i < bytes.length; i++) {
        binary += String.fromCharCode(bytes[i])
    }
    return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=/g, "")
}

// Types for parsing WebAuthn options from JSON
interface JsonCredentialDescriptor {
    id: string
    type: string
    transports?: string[]
}

interface JsonRegistrationOptions {
    challenge: string
    user?: {
        id: string
        name: string
        displayName: string
    }
    excludeCredentials?: JsonCredentialDescriptor[]
    rp: {
        name: string
        id?: string
    }
    pubKeyCredParams: Array<{ type: string; alg: number }>
    timeout?: number
    attestation?: string
    authenticatorSelection?: {
        authenticatorAttachment?: string
        residentKey?: string
        requireResidentKey?: boolean
        userVerification?: string
    }
}

interface JsonAuthenticationOptions {
    challenge: string
    rpId?: string
    timeout?: number
    allowCredentials?: JsonCredentialDescriptor[]
    userVerification?: string
}

/**
 * Parse WebAuthn options from JSON string and convert base64url fields to ArrayBuffer.
 */
function parseRegistrationOptions(
    optionsJson: string
): PublicKeyCredentialCreationOptions {
    const options = JSON.parse(optionsJson) as JsonRegistrationOptions

    const result: PublicKeyCredentialCreationOptions = {
        challenge: base64urlToBuffer(options.challenge),
        rp: options.rp,
        pubKeyCredParams: options.pubKeyCredParams as PublicKeyCredentialParameters[],
        user: options.user
            ? {
                id: base64urlToBuffer(options.user.id),
                name: options.user.name,
                displayName: options.user.displayName,
            }
            : (undefined as unknown as PublicKeyCredentialUserEntity),
        timeout: options.timeout,
        attestation: options.attestation as AttestationConveyancePreference,
        authenticatorSelection:
            options.authenticatorSelection as AuthenticatorSelectionCriteria,
    }

    // Convert excludeCredentials[].id from base64url to ArrayBuffer
    if (options.excludeCredentials) {
        result.excludeCredentials = options.excludeCredentials.map((cred) => ({
            id: base64urlToBuffer(cred.id),
            type: "public-key" as const,
            transports: cred.transports as AuthenticatorTransport[],
        }))
    }

    return result
}

/**
 * Parse authentication options from JSON string.
 */
function parseAuthenticationOptions(
    optionsJson: string
): PublicKeyCredentialRequestOptions {
    const options = JSON.parse(optionsJson) as JsonAuthenticationOptions

    const result: PublicKeyCredentialRequestOptions = {
        challenge: base64urlToBuffer(options.challenge),
        rpId: options.rpId,
        timeout: options.timeout,
        userVerification: options.userVerification as UserVerificationRequirement,
    }

    // Convert allowCredentials[].id from base64url to ArrayBuffer
    if (options.allowCredentials) {
        result.allowCredentials = options.allowCredentials.map((cred) => ({
            id: base64urlToBuffer(cred.id),
            type: "public-key" as const,
            transports: cred.transports as AuthenticatorTransport[],
        }))
    }

    return result
}

/**
 * Serialize credential response for sending to server.
 */
function serializeCredentialForServer(credential: PublicKeyCredential): object {
    const response = credential.response as
        | AuthenticatorAttestationResponse
        | AuthenticatorAssertionResponse

    const serialized: Record<string, unknown> = {
        id: credential.id,
        rawId: bufferToBase64url(credential.rawId),
        type: credential.type,
        response: {
            clientDataJSON: bufferToBase64url(response.clientDataJSON),
        },
    }

    // Handle registration response
    if ("attestationObject" in response) {
        const attestationResponse = response
        serialized.response = {
            ...(serialized.response as object),
            attestationObject: bufferToBase64url(attestationResponse.attestationObject),
            transports: attestationResponse.getTransports?.() ?? [],
        }
    }

    // Handle authentication response
    if ("authenticatorData" in response) {
        const assertionResponse = response
        serialized.response = {
            ...(serialized.response as object),
            authenticatorData: bufferToBase64url(assertionResponse.authenticatorData),
            signature: bufferToBase64url(assertionResponse.signature),
            userHandle: assertionResponse.userHandle
                ? bufferToBase64url(assertionResponse.userHandle)
                : null,
        }
    }

    return serialized
}

// --- Hooks ---

/**
 * Hook for registering a new passkey.
 */
export function useRegisterPasskey() {
    const queryClient = useQueryClient()
    const { api } = useApi()

    return useMutation({
        mutationFn: async (passkeyName: string) => {
            if (!isWebAuthnSupported()) {
                throw new Error("WebAuthn is not supported in this browser")
            }

            // Step 1: Get registration options from server
            const optionsResponse =
                await api.post<PasskeyRegistrationOptionsResponse>(
                    "/auth/passkeys/register/options",
                    {}
                )

            // Step 2: Parse options and create credential
            const options = parseRegistrationOptions(optionsResponse.options)
            const credential = (await navigator.credentials.create({
                publicKey: options,
            })) as PublicKeyCredential | null

            if (!credential) {
                throw new Error("Failed to create credential")
            }

            // Step 3: Send credential to server for verification
            const verifyResponse =
                await api.post<PasskeyRegistrationVerifyResponse>(
                    "/auth/passkeys/register/verify",
                    {
                        challenge_id: optionsResponse.challenge_id,
                        credential: serializeCredentialForServer(credential),
                        name: passkeyName,
                    }
                )

            return verifyResponse
        },
        onSuccess: () => {
            // Invalidate passkey list to show the new passkey
            void queryClient.invalidateQueries({ queryKey: ["passkeys"] })
        },
    })
}

/**
 * Hook for authenticating with a passkey.
 */
export function useAuthenticateWithPasskey() {
    const { api } = useApi()

    return useMutation({
        mutationFn: async (options?: { email?: string; organizationId?: string }) => {
            if (!isWebAuthnSupported()) {
                throw new Error("WebAuthn is not supported in this browser")
            }

            // Step 1: Get authentication options from server
            const optionsResponse =
                await api.post<PasskeyAuthenticationOptionsResponse>(
                    "/auth/passkeys/authenticate/options",
                    { email: options?.email, organization_id: options?.organizationId }
                )

            // Step 2: Parse options and get credential
            const credentialOptions = parseAuthenticationOptions(
                optionsResponse.options
            )
            const credential = (await navigator.credentials.get({
                publicKey: credentialOptions,
            })) as PublicKeyCredential | null

            if (!credential) {
                throw new Error("Failed to get credential")
            }

            // Step 3: Send credential to server for verification
            const verifyResponse =
                await api.post<PasskeyAuthenticationVerifyResponse>(
                    "/auth/passkeys/authenticate/verify",
                    {
                        challenge_id: optionsResponse.challenge_id,
                        credential: serializeCredentialForServer(credential),
                        organization_id: options?.organizationId,
                    }
                )

            // Note: The backend currently returns placeholder tokens.
            // In a full implementation, we would need to exchange these for a real
            // Stytch session. For now, we'll use discovery exchange if available.
            // This is a limitation to be addressed in a future iteration.

            return verifyResponse
        },
    })
}

/**
 * Hook for listing the current user's passkeys.
 */
export function usePasskeys() {
    const { api } = useApi()

    return useQuery({
        queryKey: ["passkeys"],
        queryFn: () => api.get<PasskeyListResponse>("/auth/passkeys"),
        staleTime: 30000, // 30 seconds
    })
}

/**
 * Hook for deleting a passkey.
 */
export function useDeletePasskey() {
    const queryClient = useQueryClient()
    const { api } = useApi()

    return useMutation({
        mutationFn: async (passkeyId: number) => {
            return api.delete(`/auth/passkeys/${String(passkeyId)}`)
        },
        onSuccess: () => {
            void queryClient.invalidateQueries({ queryKey: ["passkeys"] })
        },
    })
}

/**
 * Combined hook for all passkey operations.
 */
export function usePasskeyAuth() {
    const registerMutation = useRegisterPasskey()
    const authenticateMutation = useAuthenticateWithPasskey()
    const passkeysQuery = usePasskeys()
    const deleteMutation = useDeletePasskey()

    return {
        // State
        isSupported: isWebAuthnSupported(),
        passkeys: passkeysQuery.data?.passkeys ?? [],
        isLoadingPasskeys: passkeysQuery.isLoading,

        // Registration
        registerPasskey: registerMutation.mutateAsync,
        isRegistering: registerMutation.isPending,
        registerError: registerMutation.error,

        // Authentication
        authenticateWithPasskey: authenticateMutation.mutateAsync,
        isAuthenticating: authenticateMutation.isPending,
        authError: authenticateMutation.error,

        // Deletion
        deletePasskey: deleteMutation.mutateAsync,
        isDeleting: deleteMutation.isPending,
        deleteError: deleteMutation.error,
    }
}
