"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"

import { useAuthStore } from "@/lib/store/auth"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { SellForm } from "@/components/seller/sell-form"

export default function SellPage() {
  const status = useAuthStore((s) => s.status)
  const pathname = usePathname()

  return (
    <div className="mx-auto max-w-2xl px-4 py-8 sm:px-6">
      <div className="mb-6">
        <h1 className="font-heading text-xl font-bold tracking-tight text-foreground uppercase md:text-2xl">Mahsulot joylash</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Tovaringizni majburiy deadline bilan auksionga qoʻying. Gʻolib chiqqan xaridor
          toʻlovi escrow orqali himoyalanadi.
        </p>
      </div>

      {status === "idle" ? (
        <div className="grid gap-4">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-40" />
        </div>
      ) : status !== "authenticated" ? (
        <div className="grid place-items-center gap-3 rounded-xl border border-border bg-card px-6 py-16 text-center">
          <p className="text-base font-medium text-foreground">
            Mahsulot joylash uchun hisobingizga kiring
          </p>
          <p className="max-w-sm text-sm text-muted-foreground">
            Sotuvchi boʻlish uchun avval tizimga kirishingiz kerak.
          </p>
          <Button asChild size="lg">
            <Link href={`/login?next=${encodeURIComponent(pathname)}`}>Kirish</Link>
          </Button>
        </div>
      ) : (
        <SellForm />
      )}
    </div>
  )
}
