import { useCallback, useState } from 'react'

interface UseConfirmDialogReturn<T> {
  open: boolean
  item: T | null
  openDialog: (item: T) => void
  onOpenChange: (open: boolean) => void
  onConfirm: () => void
  reset: () => void
}

/**
 * Manages open/item/confirm state for confirmation dialogs.
 *
 * @param onConfirm - Called with the current item when the user confirms.
 */
export function useConfirmDialog<T>(onConfirm: (item: T) => void): UseConfirmDialogReturn<T> {
  const [open, setOpen] = useState(false)
  const [item, setItem] = useState<T | null>(null)

  const openDialog = useCallback((target: T) => {
    setItem(target)
    setOpen(true)
  }, [])

  const reset = useCallback(() => {
    setOpen(false)
    setItem(null)
  }, [])

  const handleOpenChange = useCallback(
    (nextOpen: boolean) => {
      if (!nextOpen) {
        reset()
      }
    },
    [reset]
  )

  const handleConfirm = useCallback(() => {
    if (item !== null) {
      onConfirm(item)
    }
  }, [item, onConfirm])

  return {
    open,
    item,
    openDialog,
    onOpenChange: handleOpenChange,
    onConfirm: handleConfirm,
    reset,
  }
}
