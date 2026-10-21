"use client"

import * as React from "react"
import { toast } from "sonner"

import { setPhoneVerificationHandler } from "@/lib/api/client"
import { useAuthStore } from "@/lib/store/auth"
import { PhoneVerifyForm } from "@/components/phone/phone-verify-form"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"

/**
 * Progressiv telefon tasdig'i: ro'yxatdan o'tish va ko'rish tasdiqsiz. Server sezgir amalni
 * (bid, taklif, xarid, e'lon chiqarish) 403 `phone_verification_required` bilan to'xtatsa,
 * apiFetch shu oynani ochadi; tasdiqlangach asl so'rov o'zi takrorlanadi — foydalanuvchi
 * amalini qaytadan boshlamaydi. Yopilsa — amal xatosi odatdagidek ko'rsatiladi.
 */
function PhoneGateProvider() {
  const [open, setOpen] = React.useState(false)
  const resolver = React.useRef<((verified: boolean) => void) | null>(null)

  const finish = React.useCallback((verified: boolean) => {
    resolver.current?.(verified)
    resolver.current = null
    setOpen(false)
  }, [])

  React.useEffect(
    () =>
      setPhoneVerificationHandler(
        () =>
          new Promise<boolean>((resolve) => {
            // Bir vaqtda ikki amal so'rasa — oldingisi bekor deb hisoblanadi.
            resolver.current?.(false)
            resolver.current = resolve
            setOpen(true)
          })
      ),
    []
  )

  return (
    <Dialog open={open} onOpenChange={(next) => !next && finish(false)}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Telefon raqamingizni tasdiqlang</DialogTitle>
          <DialogDescription>
            Bid, taklif va xarid uchun bir marta kerak. Tasdiqlangach amalingiz davom etadi.
          </DialogDescription>
        </DialogHeader>
        {open && (
          <PhoneVerifyForm
            idPrefix="gate-phone"
            onVerified={async () => {
              await useAuthStore.getState().loadMe()
              toast.success("Telefon raqami tasdiqlandi.")
              finish(true)
            }}
          />
        )}
      </DialogContent>
    </Dialog>
  )
}

export { PhoneGateProvider }
