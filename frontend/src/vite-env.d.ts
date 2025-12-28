/// <reference types="vite/client" />

interface ImportMetaEnv {
    readonly VITE_STYTCH_PUBLIC_TOKEN: string
    readonly VITE_API_URL: string
}

interface ImportMeta {
    readonly env: ImportMetaEnv
}
