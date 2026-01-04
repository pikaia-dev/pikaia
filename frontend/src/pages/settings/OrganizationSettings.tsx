import { useState } from "react"

import { Button } from "../../components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "../../components/ui/card"
import { ImageUploader } from "../../components/ui/image-uploader"
import { LoadingSpinner } from "../../components/ui/loading-spinner"
import {
  useOrganization,
  useUpdateOrganization,
} from "../../features/organization/queries"

/**
 * Normalize a slug to meet Stytch requirements.
 * Must match backend normalize_slug() in apps/accounts/schemas.py
 *
 * Allowed characters: a-z, 0-9, hyphen, period, underscore, tilde
 */
function normalizeSlug(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9._~-]+/g, "-") // Replace non-allowed chars with hyphen
    .replace(/^-+|-+$/g, "") // Remove leading/trailing hyphens
    .slice(0, 128) // Truncate to max length
}

export default function OrganizationSettings() {
  const { data: organization, isLoading, error } = useOrganization()
  const updateMutation = useUpdateOrganization()

  // Track user edits; null means no edits yet (use server value)
  const [editedName, setEditedName] = useState<string | null>(null)
  const [editedSlug, setEditedSlug] = useState<string | null>(null)
  const [editedLogoUrl, setEditedLogoUrl] = useState<string | null>(null)
  const [slugManuallyEdited, setSlugManuallyEdited] = useState(false)

  // Derive current values: use edited value if present, otherwise server value
  const name = editedName ?? organization?.name ?? ""
  const slug = editedSlug ?? organization?.slug ?? ""
  const logoUrl = editedLogoUrl ?? organization?.logo_url ?? ""

  const handleNameChange = (newName: string) => {
    setEditedName(newName)
    // Auto-update slug if user hasn't manually edited it
    if (!slugManuallyEdited) {
      setEditedSlug(normalizeSlug(newName))
    }
  }

  const handleSlugChange = (newSlug: string) => {
    const normalized = normalizeSlug(newSlug)
    setEditedSlug(normalized)
    // Mark as manually edited if different from auto-derived
    if (normalized !== normalizeSlug(name)) {
      setSlugManuallyEdited(true)
    }
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    updateMutation.mutate(
      { name, slug },
      {
        onSuccess: () => {
          // Reset edit state after successful save
          setEditedName(null)
          setEditedSlug(null)
          setSlugManuallyEdited(false)
        },
      }
    )
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="sm" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-destructive">Failed to load organization data</p>
      </div>
    )
  }

  return (
    <div className="p-6">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold">Organization</h1>
        <p className="text-muted-foreground">
          Manage your organization settings
        </p>
      </div>

      <div className="space-y-6 max-w-lg">
        {/* Logo Card */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Organization Logo</CardTitle>
            <CardDescription>
              Upload a logo for your organization
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ImageUploader
              type="logo"
              value={logoUrl}
              onChange={setEditedLogoUrl}
            />
          </CardContent>
        </Card>

        {/* Organization Details Card */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Organization Details</CardTitle>
            <CardDescription>
              Update your organization information
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label
                  htmlFor="name"
                  className="block text-sm font-medium mb-1"
                >
                  Organization name
                </label>
                <input
                  id="name"
                  type="text"
                  value={name}
                  onChange={(e) => {
                    handleNameChange(e.target.value)
                  }}
                  className="w-full px-3 py-2 border border-border rounded-md bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                  placeholder="Your organization name"
                />
              </div>

              <div>
                <label
                  htmlFor="slug"
                  className="block text-sm font-medium mb-1"
                >
                  Slug
                </label>
                <input
                  id="slug"
                  type="text"
                  value={slug}
                  onChange={(e) => {
                    handleSlugChange(e.target.value)
                  }}
                  className="w-full px-3 py-2 border border-border rounded-md bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                  placeholder="your-organization"
                />
                <p className="text-xs text-muted-foreground mt-1">
                  URL-friendly identifier (lowercase, hyphens, 2-128 chars)
                </p>
              </div>

              <Button type="submit" disabled={updateMutation.isPending}>
                {updateMutation.isPending ? "Saving..." : "Save changes"}
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
