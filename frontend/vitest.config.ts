import path from "path"
import { defineConfig } from "vitest/config"

const __dirname = import.meta.dirname

export default defineConfig({
    test: {
        globals: true,
        environment: "jsdom",
        setupFiles: ["./src/test/setup.ts"],
        include: ["src/**/*.test.{ts,tsx}"],
    },
    resolve: {
        alias: {
            "@": path.resolve(__dirname, "src"),
        },
    },
})
