/// <reference types="vite/client" />

interface ImportMetaEnv {
    readonly VITE_STYTCH_PUBLIC_TOKEN: string
    readonly VITE_API_URL: string
    readonly VITE_STRIPE_PUBLISHABLE_KEY?: string
    readonly VITE_GOOGLE_PLACES_API_KEY?: string
}

interface ImportMeta {
    readonly env: ImportMetaEnv
}
