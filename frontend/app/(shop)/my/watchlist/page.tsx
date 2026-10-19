import { WatchlistView } from "@/components/watchlist/watchlist-view"

export const metadata = {
  title: "Kuzatuvlarim — Bazart",
}

export default function WatchlistPage() {
  return (
    <div className="mx-auto max-w-6xl px-4 py-6 sm:px-6">
      <div className="mb-6">
        <h1 className="font-heading text-xl font-bold tracking-tight text-foreground uppercase md:text-2xl">Kuzatuvlarim</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Kuzatayotgan mahsulotlaringiz — tugashiga oz qolganda bildirishnoma olasiz.
        </p>
      </div>
      <WatchlistView />
    </div>
  )
}
