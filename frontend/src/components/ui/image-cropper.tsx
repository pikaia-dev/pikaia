import { useState, useCallback } from "react"
import Cropper from "react-easy-crop"
import type { Area, Point } from "react-easy-crop"
import { Button } from "./button"
import { cn } from "../../lib/utils"

interface ImageCropperProps {
  image: string // Base64 or blob URL
  aspect?: number // Width/Height ratio (default 1 for square)
  cropShape?: "rect" | "round"
  onCropComplete: (croppedBlob: Blob) => void
  onCancel: () => void
}

/**
 * Creates a cropped image blob from canvas data.
 */
async function getCroppedImg(
  imageSrc: string,
  pixelCrop: Area,
  outputSize: number = 512
): Promise<Blob> {
  const image = new Image()
  image.src = imageSrc

  await new Promise((resolve) => {
    image.onload = resolve
  })

  const canvas = document.createElement("canvas")
  const ctx = canvas.getContext("2d")
  if (!ctx) {
    throw new Error("Could not get canvas context")
  }

  // Set canvas size to desired output size
  canvas.width = outputSize
  canvas.height = outputSize

  // Draw the cropped area scaled to output size
  ctx.drawImage(
    image,
    pixelCrop.x,
    pixelCrop.y,
    pixelCrop.width,
    pixelCrop.height,
    0,
    0,
    outputSize,
    outputSize
  )

  // Convert to blob
  return new Promise((resolve, reject) => {
    canvas.toBlob(
      (blob) => {
        if (blob) {
          resolve(blob)
        } else {
          reject(new Error("Failed to create blob"))
        }
      },
      "image/png",
      0.95
    )
  })
}

export function ImageCropper({
  image,
  aspect = 1,
  cropShape = "round",
  onCropComplete,
  onCancel,
}: ImageCropperProps) {
  const [crop, setCrop] = useState<Point>({ x: 0, y: 0 })
  const [zoom, setZoom] = useState(1)
  const [croppedAreaPixels, setCroppedAreaPixels] = useState<Area | null>(null)
  const [isProcessing, setIsProcessing] = useState(false)

  const handleCropComplete = useCallback(
    (_croppedArea: Area, croppedAreaPixels: Area) => {
      setCroppedAreaPixels(croppedAreaPixels)
    },
    []
  )

  const handleSave = async () => {
    if (!croppedAreaPixels) return

    setIsProcessing(true)
    try {
      const croppedBlob = await getCroppedImg(image, croppedAreaPixels)
      onCropComplete(croppedBlob)
    } catch (error) {
      console.error("Failed to crop image:", error)
    } finally {
      setIsProcessing(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80">
      <div className="bg-background rounded-lg shadow-xl w-full max-w-lg mx-4">
        {/* Header */}
        <div className="px-4 py-3 border-b border-border">
          <h3 className="text-lg font-semibold">Crop Image</h3>
          <p className="text-sm text-muted-foreground">
            Drag to reposition, scroll to zoom
          </p>
        </div>

        {/* Cropper Area */}
        <div className="relative h-80 bg-black">
          <Cropper
            image={image}
            crop={crop}
            zoom={zoom}
            aspect={aspect}
            cropShape={cropShape}
            showGrid={false}
            onCropChange={setCrop}
            onZoomChange={setZoom}
            onCropComplete={handleCropComplete}
          />
        </div>

        {/* Zoom Slider */}
        <div className="px-4 py-3 border-t border-border">
          <label className="flex items-center gap-3">
            <span className="text-sm text-muted-foreground">Zoom</span>
            <input
              type="range"
              min={1}
              max={3}
              step={0.1}
              value={zoom}
              onChange={(e) => setZoom(Number(e.target.value))}
              className={cn(
                "flex-1 h-2 rounded-full appearance-none cursor-pointer",
                "bg-muted",
                "[&::-webkit-slider-thumb]:appearance-none",
                "[&::-webkit-slider-thumb]:w-4",
                "[&::-webkit-slider-thumb]:h-4",
                "[&::-webkit-slider-thumb]:rounded-full",
                "[&::-webkit-slider-thumb]:bg-primary",
                "[&::-webkit-slider-thumb]:cursor-pointer"
              )}
            />
          </label>
        </div>

        {/* Actions */}
        <div className="flex justify-end gap-2 px-4 py-3 border-t border-border">
          <Button variant="outline" onClick={onCancel} disabled={isProcessing}>
            Cancel
          </Button>
          <Button
            onClick={handleSave}
            disabled={isProcessing || !croppedAreaPixels}
          >
            {isProcessing ? "Processing..." : "Save"}
          </Button>
        </div>
      </div>
    </div>
  )
}
