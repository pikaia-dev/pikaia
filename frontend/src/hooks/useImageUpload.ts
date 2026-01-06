import { useStytchB2BClient } from "@stytch/react/b2b"
import { useQueryClient } from "@tanstack/react-query"
import { useCallback,useState } from "react"

import { queryKeys } from "../features/shared/query-keys"
import type { ImageResponse,UploadRequest } from "../lib/api"
import { useApi } from "./useApi"

interface UseImageUploadOptions {
  onSuccess?: (result: ImageResponse) => void
  onError?: (error: Error) => void
}

export function useImageUpload(
  imageType: "avatar" | "logo",
  options: UseImageUploadOptions = {}
) {
  const stytch = useStytchB2BClient()
  const queryClient = useQueryClient()
  const { requestUpload, confirmUpload } = useApi()
  const [isUploading, setIsUploading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [error, setError] = useState<Error | null>(null)

  const upload = useCallback(
    async (file: Blob, filename: string): Promise<ImageResponse | null> => {
      setIsUploading(true)
      setProgress(0)
      setError(null)

      try {
        // Step 1: Request upload URL
        setProgress(10)
        const uploadRequest: UploadRequest = {
          filename,
          content_type: file.type || "image/png",
          size_bytes: file.size,
          image_type: imageType,
        }
        const uploadInfo = await requestUpload(uploadRequest)

        // Step 2: Upload to storage
        setProgress(30)

        if (uploadInfo.method === "PUT") {
          // S3 presigned PUT
          const response = await fetch(uploadInfo.upload_url, {
            method: "PUT",
            body: file,
            headers: {
              "Content-Type": file.type || "image/png",
            },
          })
          if (!response.ok) {
            throw new Error("Upload failed")
          }
        } else {
          // Local direct upload (POST with multipart form)
          const formData = new FormData()
          formData.append("file", file, filename)
          formData.append("key", uploadInfo.key)
          formData.append("content_type", file.type || "image/png")

          // Add any additional fields
          for (const [key, value] of Object.entries(uploadInfo.fields)) {
            formData.append(key, value)
          }

          // Get auth token for the request
          const tokens = stytch.session.getTokens()
          const headers: HeadersInit = {}
          if (tokens?.session_jwt) {
            headers["Authorization"] = `Bearer ${tokens.session_jwt}`
          }

          const response = await fetch(uploadInfo.upload_url, {
            method: "POST",
            body: formData,
            headers,
          })
          if (!response.ok) {
            const errorText = await response.text()
            throw new Error(errorText || "Upload failed")
          }
        }

        // Step 3: Confirm upload
        setProgress(80)
        const result = await confirmUpload({
          key: uploadInfo.key,
          image_type: imageType,
        })

        setProgress(100)

        // Invalidate user cache when avatar is updated so sidebar refreshes
        if (imageType === "avatar") {
          void queryClient.invalidateQueries({ queryKey: queryKeys.auth.me() })
        }

        options.onSuccess?.(result)
        return result
      } catch (err) {
        const error = err instanceof Error ? err : new Error("Upload failed")
        setError(error)
        options.onError?.(error)
        return null
      } finally {
        setIsUploading(false)
      }
    },
    [imageType, requestUpload, confirmUpload, options, stytch, queryClient]
  )

  const reset = useCallback(() => {
    setIsUploading(false)
    setProgress(0)
    setError(null)
  }, [])

  return {
    upload,
    isUploading,
    progress,
    error,
    reset,
  }
}
