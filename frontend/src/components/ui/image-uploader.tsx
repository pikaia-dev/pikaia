import { useState, useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import { Upload, X, User, Building2 } from 'lucide-react'
import { toast } from 'sonner'
import { ImageCropper } from './image-cropper'
import { useImageUpload } from '../../hooks/useImageUpload'
import { cn } from '../../lib/utils'

interface ImageUploaderProps {
    type: 'avatar' | 'logo'
    value?: string // Current image URL
    onChange: (url: string) => void
    onError?: (error: Error) => void
    disabled?: boolean
    className?: string
}

// Size limits in bytes
const MAX_AVATAR_SIZE = 2 * 1024 * 1024 // 2MB
const MAX_LOGO_SIZE = 5 * 1024 * 1024 // 5MB
const ACCEPTED_TYPES = {
    'image/jpeg': ['.jpg', '.jpeg'],
    'image/png': ['.png'],
    'image/webp': ['.webp'],
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
    const [originalFilename, setOriginalFilename] = useState('')

    const { upload, isUploading, progress } = useImageUpload(type, {
        onSuccess: (result) => {
            onChange(result.url)
            toast.success(`${type === 'avatar' ? 'Avatar' : 'Logo'} updated successfully`)
        },
        onError: (error) => {
            toast.error(error.message)
            onError?.(error)
        },
    })

    const maxSize = type === 'avatar' ? MAX_AVATAR_SIZE : MAX_LOGO_SIZE
    const isCircular = type === 'avatar'

    const onDrop = useCallback((acceptedFiles: File[]) => {
        const file = acceptedFiles[0]
        if (!file) return

        // Validate file size
        if (file.size > maxSize) {
            const maxMb = maxSize / (1024 * 1024)
            toast.error(`File too large. Maximum size is ${maxMb}MB`)
            return
        }

        // Create object URL for cropper
        const objectUrl = URL.createObjectURL(file)
        setSelectedFile(objectUrl)
        setOriginalFilename(file.name)
        setShowCropper(true)
    }, [maxSize])

    const { getRootProps, getInputProps, isDragActive } = useDropzone({
        onDrop,
        accept: ACCEPTED_TYPES,
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
        const ext = originalFilename.split('.').pop() || 'png'
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

    const handleRemove = () => {
        onChange('')
    }

    const PlaceholderIcon = type === 'avatar' ? User : Building2

    return (
        <>
            <div className={cn("flex items-center gap-4", className)}>
                {/* Preview */}
                <div
                    className={cn(
                        "relative flex items-center justify-center bg-muted border-2 border-dashed border-border overflow-hidden",
                        isCircular ? "rounded-full w-20 h-20" : "rounded-lg w-24 h-24"
                    )}
                >
                    {value ? (
                        <>
                            <img
                                src={value}
                                alt={type}
                                className="w-full h-full object-cover"
                            />
                            {!disabled && !isUploading && (
                                <button
                                    type="button"
                                    onClick={handleRemove}
                                    className="absolute -top-1 -right-1 p-1 bg-destructive text-destructive-foreground rounded-full hover:bg-destructive/90 transition-colors"
                                >
                                    <X className="w-3 h-3" />
                                </button>
                            )}
                        </>
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

                {/* Dropzone */}
                <div className="flex-1">
                    <div
                        {...getRootProps()}
                        className={cn(
                            "border-2 border-dashed rounded-lg p-4 text-center cursor-pointer transition-colors",
                            isDragActive ? "border-primary bg-primary/5" : "border-border hover:border-primary/50",
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
                                        Drag & drop or{' '}
                                        <span className="text-primary font-medium">browse</span>
                                    </>
                                )}
                            </p>
                            <p className="text-xs text-muted-foreground">
                                PNG, JPG or WebP (max {maxSize / (1024 * 1024)}MB)
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
                    cropShape={isCircular ? 'round' : 'rect'}
                    onCropComplete={handleCropComplete}
                    onCancel={handleCropCancel}
                />
            )}
        </>
    )
}
