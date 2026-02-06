import { useCallback, useEffect, useRef, useState } from 'react'

/**
 * Manages a keyed record of blob URLs with automatic cleanup.
 *
 * Revokes all blob URLs when the component unmounts to prevent memory leaks
 * from `URL.createObjectURL()`.
 */
export function useBlobUrls() {
  const [urls, setUrls] = useState<Record<string, string>>({})
  const urlsRef = useRef<Record<string, string>>({})

  // Keep ref in sync with state so cleanup always has latest values
  useEffect(() => {
    urlsRef.current = urls
  }, [urls])

  const addUrl = useCallback((key: string, blobUrl: string) => {
    setUrls((prev) => {
      // Revoke old URL for this key if it exists and differs
      if (prev[key] && prev[key] !== blobUrl) {
        URL.revokeObjectURL(prev[key])
      }
      return { ...prev, [key]: blobUrl }
    })
  }, [])

  const clearAll = useCallback(() => {
    setUrls((prev) => {
      for (const blobUrl of Object.values(prev)) {
        URL.revokeObjectURL(blobUrl)
      }
      return {}
    })
  }, [])

  const hasUrl = useCallback((key: string) => Boolean(urlsRef.current[key]), [])

  const getUrl = useCallback((key: string) => urlsRef.current[key] as string | undefined, [])

  // Revoke all blob URLs on unmount
  useEffect(() => {
    return () => {
      for (const blobUrl of Object.values(urlsRef.current)) {
        URL.revokeObjectURL(blobUrl)
      }
    }
  }, [])

  return { urls, addUrl, clearAll, hasUrl, getUrl }
}
