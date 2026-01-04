import { useState, useCallback } from "react"
import { useDropzone } from "react-dropzone"
import { Upload, X, User, Building2 } from "lucide-react"
import { toast } from "sonner"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "./alert-dialog"
import { ImageCropper } from "./image-cropper"
import { useImageUpload } from "../../hooks/useImageUpload"
import { cn } from "../../lib/utils"
import { MEDIA_UPLOAD } from "../../lib/constants"

interface ImageUploaderProps {
  type: "avatar" | "logo"
  value?: string // Current image URL
  onChange: (url: string) => void
  onError?: (error: Error) => void
  disabled?: boolean
  className?: string
}

export function ImageUploader({
  type,
  value,
  onChange,
  onError,
  disabled = false,
  className,
}: ImageUploaderProps) {
  const [selectedFile, setSelectedFile] = useState<string | null>(null)
  const [showCropper, setShowCropper] = useState(false)
  const [originalFilename, setOriginalFilename] = useState("")
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)

  const { upload, isUploading, progress } = useImageUpload(type, {
    onSuccess: (result) => {
      onChange(result.url)
      toast.success(
        `${type === "avatar" ? "Avatar" : "Logo"} updated successfully`
      )
    },
    onError: (error) => {
      toast.error(error.message)
      onError?.(error)
    },
  })

  const isCircular = type === "avatar"
  const label = type === "avatar" ? "profile picture" : "logo"

  const onDrop = useCallback(
    async (acceptedFiles: File[]) => {
      const file = acceptedFiles[0]
      if (!file) return

      // Validate file size
      if (file.size > MEDIA_UPLOAD.MAX_SIZE_BYTES) {
        toast.error(
          `File too large. Maximum size is ${MEDIA_UPLOAD.MAX_SIZE_MB}MB`
        )
        return
      }

      // SVG files can't be cropped - upload directly
      if (file.type === "image/svg+xml") {
        const filename = `${type}-${Date.now()}.svg`
        await upload(file, filename)
        return
      }

      // Create object URL for cropper
      const objectUrl = URL.createObjectURL(file)
      setSelectedFile(objectUrl)
      setOriginalFilename(file.name)
      setShowCropper(true)
    },
    [type, upload]
  )

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: MEDIA_UPLOAD.ACCEPTED_TYPES,
    maxFiles: 1,
    disabled: disabled || isUploading,
  })

  const handleCropComplete = async (croppedBlob: Blob) => {
    setShowCropper(false)

    // Clean up object URL
    if (selectedFile) {
      URL.revokeObjectURL(selectedFile)
      setSelectedFile(null)
    }

    // Upload cropped image
    const ext = originalFilename.split(".").pop() || "png"
    const filename = `${type}-${Date.now()}.${ext}`
    await upload(croppedBlob, filename)
  }

  const handleCropCancel = () => {
    setShowCropper(false)
    if (selectedFile) {
      URL.revokeObjectURL(selectedFile)
      setSelectedFile(null)
    }
  }

  const handleRemoveConfirm = () => {
    onChange("")
    setDeleteDialogOpen(false)
  }

  const PlaceholderIcon = type === "avatar" ? User : Building2

  return (
    <>
      <div className={cn("flex items-center gap-4", className)}>
        {/* Preview */}
        <div className="relative">
          <div
            className={cn(
              "flex items-center justify-center bg-muted border-2 border-dashed border-border overflow-hidden",
              isCircular ? "rounded-full w-20 h-20" : "rounded-lg w-24 h-24"
            )}
          >
            {value ? (
              <img
                src={value}
                alt={type}
                className="w-full h-full object-cover"
              />
            ) : (
              <PlaceholderIcon className="w-8 h-8 text-muted-foreground" />
            )}

            {/* Upload progress overlay */}
            {isUploading && (
              <div className="absolute inset-0 flex items-center justify-center bg-black/50">
                <div className="text-white text-xs font-medium">
                  {progress}%
                </div>
              </div>
            )}
          </div>

          {/* Delete button - positioned outside overflow container */}
          {value && !disabled && !isUploading && (
            <button
              type="button"
              onClick={() => setDeleteDialogOpen(true)}
              className="absolute -top-1 -right-1 z-10 p-1 bg-muted-foreground/80 text-background rounded-full hover:bg-muted-foreground transition-colors shadow-sm cursor-pointer"
            >
              <X className="w-3 h-3" />
            </button>
          )}
        </div>

        {/* Dropzone */}
        <div className="flex-1">
          <div
            {...getRootProps()}
            className={cn(
              "border-2 border-dashed rounded-lg p-4 text-center cursor-pointer transition-colors",
              isDragActive
                ? "border-primary bg-primary/5"
                : "border-border hover:border-primary/50",
              (disabled || isUploading) && "opacity-50 cursor-not-allowed"
            )}
          >
            <input {...getInputProps()} />
            <div className="flex flex-col items-center gap-1">
              <Upload className="w-5 h-5 text-muted-foreground" />
              <p className="text-sm text-muted-foreground">
                {isDragActive ? (
                  "Drop the image here"
                ) : (
                  <>
                    Drag & drop or{" "}
                    <span className="text-primary font-medium">browse</span>
                  </>
                )}
              </p>
              <p className="text-xs text-muted-foreground">
                PNG, JPG, WebP, SVG, AVIF (max {MEDIA_UPLOAD.MAX_SIZE_MB}MB)
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Cropper Modal */}
      {showCropper && selectedFile && (
        <ImageCropper
          image={selectedFile}
          aspect={1}
          cropShape={isCircular ? "round" : "rect"}
          onCropComplete={handleCropComplete}
          onCancel={handleCropCancel}
        />
      )}

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Remove {label}</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to remove this {label}? This action cannot
              be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleRemoveConfirm}>
              Remove
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}
