"use client"

import * as React from "react"
import Link from "next/link"
import { UserRoundIcon, MessageSquareIcon } from "lucide-react"

import { ApiError } from "@/lib/api/client"
import type { User } from "@/lib/api/types"
import { getUser } from "@/lib/api/profile"
import { listUserReviews, type Review } from "@/lib/api/engagement"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { RatingStars } from "@/components/profile/rating-stars"
import { formatProfileDate } from "@/components/profile/profile-meta"
import { ReportDialog } from "@/components/complaint/report-dialog"
import { useAuthStore } from "@/lib/store/auth"

type Data = { user: User | null; reviews: Review[] }

/**
 * Ochiq sotuvchi profili.
 *
 * Backend'da ochiq `GET /users/{id}` yo'q — shu sabab reyting/sharhlar ochiq
 * `GET /reviews/user/{id}` orqali olinadi. `getUser` faqat self uchun User
 * qaytaradi (aks holda null), shuning uchun ism/reyting mavjud bo'lmasa
 * sharhlardan hisoblanadi.
 */
function PublicProfile({ userId }: { userId: number }) {
  const viewer = useAuthStore((s) => s.user)
  const [data, setData] = React.useState<Data | null>(null)
  const [error, setError] = React.useState<string | null>(null)

  // userId o'zgarsa — render vaqtida qayta yuklash holatiga qaytamiz.
  const [loadedId, setLoadedId] = React.useState(userId)
  if (loadedId !== userId) {
    setLoadedId(userId)
    setData(null)
    setError(null)
  }

  React.useEffect(() => {
    let alive = true
    Promise.all([getUser(userId), listUserReviews(userId)])
      .then(([user, reviews]) => {
        if (alive) setData({ user, reviews })
      })
      .catch((e) => {
        if (alive) {
          setError(e instanceof ApiError ? e.detail : "Profilni yuklab boʻlmadi.")
        }
      })
    return () => {
      alive = false
    }
  }, [userId])

  if (error) {
    return (
      <div className="grid place-items-center gap-3 rounded-lg border border-border bg-card px-6 py-16 text-center">
        <UserRoundIcon className="size-8 text-muted-foreground" aria-hidden="true" />
        <p className="text-base font-medium text-destructive">{error}</p>
        <Button asChild variant="outline" size="sm">
          <Link href="/catalog/hammasi">Katalogga oʻtish</Link>
        </Button>
      </div>
    )
  }

  if (!data) {
    return (
      <div className="grid gap-6">
        <Skeleton className="h-24 w-full rounded-lg" />
        <Skeleton className="h-40 w-full rounded-lg" />
      </div>
    )
  }

  const { user, reviews } = data
  const displayName = user?.full_name?.trim() || `Sotuvchi #${userId}`
  // Reyting: user mavjud bo'lsa agregat, aks holda sharhlardan hisoblab.
  const avgFromReviews =
    reviews.length > 0
      ? reviews.reduce((sum, r) => sum + r.stars, 0) / reviews.length
      : 0
  const ratingValue = user ? user.seller_rating : avgFromReviews
  const ratingCount = user ? user.seller_rating_count : reviews.length

  return (
    <div className="grid gap-8">
      <section className="flex items-start gap-4 rounded-lg border border-border bg-card p-5">
        <div className="grid size-14 shrink-0 place-items-center rounded-full bg-muted text-muted-foreground">
          <UserRoundIcon className="size-7" aria-hidden="true" />
        </div>
        <div className="min-w-0 flex-1">
          <h1 className="truncate text-xl font-semibold text-foreground">{displayName}</h1>
          <RatingStars
            value={ratingValue}
            count={ratingCount}
            showValue={ratingCount > 0}
            className="mt-1.5"
          />
          {user?.location?.trim() && (
            <p className="mt-1 text-sm text-muted-foreground">{user.location}</p>
          )}
          {user?.bio?.trim() && (
            <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{user.bio}</p>
          )}
          {viewer?.id !== userId && (
            <ReportDialog targetType="user" targetId={userId} className="mt-2 -ml-3" />
          )}
        </div>
      </section>

      <section>
        <h2 className="mb-4 text-lg font-semibold text-foreground">
          Sharhlar
          {reviews.length > 0 && (
            <span className="ml-2 text-sm font-normal text-muted-foreground">
              {reviews.length} ta
            </span>
          )}
        </h2>

        {reviews.length === 0 ? (
          <div className="grid place-items-center gap-2 rounded-lg border border-dashed border-border bg-card px-6 py-12 text-center">
            <MessageSquareIcon className="size-7 text-muted-foreground" aria-hidden="true" />
            <p className="text-sm font-medium text-foreground">Hali sharhlar yoʻq.</p>
            <p className="text-sm text-muted-foreground">
              Bu sotuvchi bilan bitim yakunlangach sharhlar shu yerda koʻrinadi.
            </p>
          </div>
        ) : (
          <ul className="grid gap-3">
            {reviews.map((review) => (
              <li
                key={review.id}
                className="grid gap-2 rounded-lg border border-border bg-card p-4"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <RatingStars value={review.stars} />
                  <span className="text-xs text-muted-foreground">
                    {formatProfileDate(review.created_at)}
                  </span>
                </div>
                {review.text?.trim() ? (
                  <p className="text-sm leading-relaxed text-foreground">{review.text}</p>
                ) : (
                  <p className="text-sm text-muted-foreground">Izohsiz baho.</p>
                )}
                <p className="text-xs text-muted-foreground">
                  Foydalanuvchi #{review.from_id}
                </p>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}

export { PublicProfile }
