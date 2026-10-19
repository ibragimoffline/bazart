import { Suspense } from "react"
import type { Metadata } from "next"

import { OffersView } from "@/components/offer/offers-view"
import { Skeleton } from "@/components/ui/skeleton"

export const metadata: Metadata = {
  title: "Takliflar — Bazart",
}

export default function OffersPage() {
  return (
    <div className="mx-auto max-w-3xl px-4 py-8 sm:px-6">
      <div className="mb-6">
        <h1 className="font-heading text-xl font-bold tracking-tight text-foreground uppercase md:text-2xl">
          Takliflar
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Narx va miqdor boʻyicha muzokaralar: qabul qiling, rad eting yoki qarshi taklif bering.
        </p>
      </div>
      {/* useSearchParams — Suspense chegarasi talab qilinadi (statik prerender). */}
      <Suspense fallback={<Skeleton className="h-64 w-full rounded-xl" />}>
        <OffersView />
      </Suspense>
    </div>
  )
}
