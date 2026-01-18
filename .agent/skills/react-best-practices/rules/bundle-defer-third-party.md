---
title: Defer Non-Critical Third-Party Libraries
impact: MEDIUM
impactDescription: loads after initial render
tags: bundle, third-party, analytics, defer
---

## Defer Non-Critical Third-Party Libraries

Analytics, logging, and error tracking don't block user interaction. Load them after initial render.

**Incorrect (blocks initial bundle):**

```tsx
import { PostHogProvider } from 'posthog-js/react'

export default function App() {
  return (
    <PostHogProvider>
      <MainContent />
    </PostHogProvider>
  )
}
```

**Correct (loads after initial render):**

```tsx
import { lazy, Suspense, useEffect, useState } from 'react'

const PostHogProvider = lazy(() =>
  import('posthog-js/react').then(m => ({ default: m.PostHogProvider }))
)

export default function App() {
  const [mounted, setMounted] = useState(false)

  useEffect(() => {
    setMounted(true)
  }, [])

  return (
    <Suspense fallback={null}>
      {mounted ? (
        <PostHogProvider>
          <MainContent />
        </PostHogProvider>
      ) : (
        <MainContent />
      )}
    </Suspense>
  )
}
```
