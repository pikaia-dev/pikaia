import { zodResolver } from "@hookform/resolvers/zod"
import { useEffect, useState } from "react"
import { useForm } from "react-hook-form"

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
  normalizeSlug,
  type OrganizationFormData,
  organizationSchema,
} from "../../features/organization/forms/schema"
import {
  useOrganization,
  useUpdateOrganization,
} from "../../features/organization/queries"

export default function OrganizationSettings() {
  const { data: organization, isLoading, error } = useOrganization()
  const updateMutation = useUpdateOrganization()
  const [editedLogoUrl, setEditedLogoUrl] = useState<string | null>(null)
  const [slugManuallyEdited, setSlugManuallyEdited] = useState(false)

  const logoUrl = editedLogoUrl ?? organization?.logo_url ?? ""

  const {
    register,
    handleSubmit,
    setValue,
    watch,
    reset,
    formState: { errors },
  } = useForm<OrganizationFormData>({
    resolver: zodResolver(organizationSchema),
    defaultValues: {
      name: "",
      slug: "",
    },
  })

  const name = watch("name")

  // Sync form with server data when it loads
  useEffect(() => {
    if (organization) {
      reset({
        name: organization.name,
        slug: organization.slug,
      })
    }
  }, [organization, reset])

  const handleNameChange = (newName: string) => {
    setValue("name", newName, { shouldValidate: true })
    // Auto-update slug if user hasn't manually edited it
    if (!slugManuallyEdited) {
      setValue("slug", normalizeSlug(newName), { shouldValidate: true })
    }
  }

  const handleSlugChange = (newSlug: string) => {
    const normalized = normalizeSlug(newSlug)
    setValue("slug", normalized, { shouldValidate: true })
    // Mark as manually edited if different from auto-derived
    if (normalized !== normalizeSlug(name)) {
      setSlugManuallyEdited(true)
    }
  }

  const onSubmit = (data: OrganizationFormData) => {
    updateMutation.mutate(data, {
      onSuccess: () => {
        setSlugManuallyEdited(false)
      },
    })
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
            <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
              <div>
                <label
                  htmlFor="name"
                  className="block text-sm font-medium mb-1"
                >
                  Organization name
                </label>
                <input
                  {...register("name")}
                  id="name"
                  type="text"
                  onChange={(e) => {
                    handleNameChange(e.target.value)
                  }}
                  className="w-full px-3 py-2 border border-border rounded-md bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                  placeholder="Your organization name"
                />
                {errors.name && (
                  <p className="text-xs text-destructive mt-1">
                    {errors.name.message}
                  </p>
                )}
              </div>

              <div>
                <label
                  htmlFor="slug"
                  className="block text-sm font-medium mb-1"
                >
                  Slug
                </label>
                <input
                  {...register("slug")}
                  id="slug"
                  type="text"
                  onChange={(e) => {
                    handleSlugChange(e.target.value)
                  }}
                  className="w-full px-3 py-2 border border-border rounded-md bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                  placeholder="your-organization"
                />
                {errors.slug ? (
                  <p className="text-xs text-destructive mt-1">
                    {errors.slug.message}
                  </p>
                ) : (
                  <p className="text-xs text-muted-foreground mt-1">
                    URL-friendly identifier (lowercase, hyphens, 2-128 chars)
                  </p>
                )}
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
