"use client"

import * as React from "react"

import { endSession } from "@/lib/api/client"
import { onSessionHintChange } from "@/lib/api/token"
import { useAuthStore } from "@/lib/store/auth"

/**
 * Mount'da sessiyani tiklaydi va tablarni sinxronlaydi. Hech narsa render qilmaydi.
 * Boshqa tabda chiqilsa — bu tab ham chiqadi; boshqa tabda kirilsa — bu tab ham tiklanadi.
 * Tarmoq qaytganda (online) tiklanmagan sessiya qayta tekshiriladi.
 */
function AuthProvider() {
  React.useEffect(() => {
    const store = useAuthStore.getState
    void store().loadMe()

    const unsubscribe = onSessionHintChange((active) => {
      if (!active) endSession()
      else if (store().status !== "authenticated") void store().loadMe()
    })
    const onOnline = () => {
      if (store().status === "idle") void store().loadMe()
    }
    window.addEventListener("online", onOnline)
    return () => {
      unsubscribe()
      window.removeEventListener("online", onOnline)
    }
  }, [])
  return null
}

export { AuthProvider }
