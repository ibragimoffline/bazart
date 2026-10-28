import { cn } from "@/lib/utils"

function Skeleton({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="skeleton"
      className={cn("animate-pulse rounded-md bg-muted", className)}
      {...props}
    />
  )
}

/** Matn skeleti — bir nechta qator; oxirgi qator kalta. */
function SkeletonText({
  lines = 3,
  className,
}: {
  lines?: number
  className?: string
}) {
  return (
    <div
      data-slot="skeleton-text"
      className={cn("grid gap-2", className)}
      aria-hidden="true"
    >
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton
          key={i}
          className={cn("h-4", i === lines - 1 ? "w-2/3" : "w-full")}
        />
      ))}
    </div>
  )
}

/** ProductCard shakli uchun yuklanish skeleti. */
function ProductCardSkeleton({ className }: { className?: string }) {
  return (
    <div
      data-slot="product-card-skeleton"
      className={cn("grid content-start gap-3", className)}
      aria-hidden="true"
    >
      {/* Shakli foto-karta bilan bir xil (kvadrat + 2 qator nom + narx + meta) —
          ma'lumot kelganda sahifa siljimaydi. */}
      <Skeleton className="aspect-square w-full rounded-lg" />
      <div className="grid gap-1.5 px-0.5">
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-3/4" />
        <Skeleton className="mt-1 h-6 w-1/2" />
        <Skeleton className="h-3 w-2/3" />
      </div>
    </div>
  )
}

export { Skeleton, SkeletonText, ProductCardSkeleton }
