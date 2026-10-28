"use client"

import * as React from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { UserRoundIcon, MailIcon, PhoneIcon, MapPinIcon } from "lucide-react"
import { toast } from "sonner"

import { ApiError } from "@/lib/api/client"
import { useAuthStore } from "@/lib/store/auth"
import type { UserMe } from "@/lib/api/types"
import { getMyProfile, updateMe } from "@/lib/api/profile"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Field, FieldLabel, FieldError, FieldDescription } from "@/components/ui/field"
import { Skeleton } from "@/components/ui/skeleton"
import { RatingStars } from "@/components/profile/rating-stars"
import { PhoneVerification } from "@/components/profile/phone-verification"
import { TelegramLink } from "@/components/profile/telegram-link"
import { LanguagePreference } from "@/components/profile/language-preference"
import { ConsentList } from "@/components/profile/consent-list"

const schema = z.object({
  full_name: z.string().trim().max(255, "Ism 255 belgidan oshmasin.").optional(),
  bio: z.string().trim().max(500, "Bio 500 belgidan oshmasin.").optional(),
  location: z.string().trim().max(160, "Manzil 160 belgidan oshmasin.").optional(),
})

type FormValues = z.infer<typeof schema>

/** Bo'sh/probelli qiymatni null ga aylantiradi (maydonni tozalash uchun). */
function orNull(value: string | undefined): string | null {
  const trimmed = value?.trim() ?? ""
  return trimmed === "" ? null : trimmed
}

function ProfileView() {
  const status = useAuthStore((s) => s.status)
  const user = useAuthStore((s) => s.user)
  const pathname = usePathname()
  const [serverError, setServerError] = React.useState<string | null>(null)
  // Kengaytirilgan (faqat egaga ko'rinadigan) profil: Telegram, til, telefon tasdig'i.
  const [me, setMe] = React.useState<UserMe | null>(null)
  const [meError, setMeError] = React.useState<string | null>(null)

  const refreshMe = React.useCallback(async () => {
    const fresh = await getMyProfile()
    setMe(fresh)
    setMeError(null)
  }, [])

  React.useEffect(() => {
    if (status !== "authenticated") return
    let alive = true
    getMyProfile()
      .then((data) => {
        if (alive) setMe(data)
      })
      .catch((e) => {
        if (!alive) return
        setMeError(e instanceof ApiError ? e.detail : "Sozlamalarni yuklab boʻlmadi.")
      })
    return () => {
      alive = false
    }
  }, [status])

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    mode: "onTouched",
    values: {
      full_name: user?.full_name ?? "",
      bio: user?.bio ?? "",
      location: user?.location ?? "",
    },
  })

  const onSubmit = handleSubmit(async (values) => {
    setServerError(null)
    try {
      await updateMe({
        full_name: orNull(values.full_name),
        bio: orNull(values.bio),
        location: orNull(values.location),
      })
      // Store'ni yangilaymiz — header/boshqa joylar yangi ma'lumotni ko'radi.
      // Telefon bu formada yo'q: u faqat SMS kod bilan yoziladi (Telefon tasdig'i bloki).
      await Promise.all([useAuthStore.getState().loadMe(), refreshMe().catch(() => {})])
      toast.success("Profil yangilandi.")
    } catch (e) {
      setServerError(
        e instanceof ApiError ? e.detail : "Profilni saqlab boʻlmadi. Qayta urinib koʻring."
      )
    }
  })


  // --- Auth gate -------------------------------------------------------
  if (status === "idle") {
    return (
      <div className="grid gap-6">
        <Skeleton className="h-24 w-full rounded-lg" />
        <Skeleton className="h-80 w-full rounded-lg" />
      </div>
    )
  }

  if (status === "anonymous" || !user) {
    return (
      <div className="grid place-items-center gap-3 rounded-lg border border-border bg-card px-6 py-16 text-center">
        <UserRoundIcon className="size-8 text-muted-foreground" aria-hidden="true" />
        <p className="text-base font-medium text-foreground">
          Profilni koʻrish uchun hisobingizga kiring.
        </p>
        <Button asChild size="sm">
          <Link href={`/login?next=${encodeURIComponent(pathname)}`}>Kirish</Link>
        </Button>
      </div>
    )
  }

  return (
    <div className="grid gap-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">Profil</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Hisob maʼlumotlaringiz va sotuvchi reytingi.
        </p>
      </div>

      {/* Xulosa kartasi */}
      <section className="grid gap-4 rounded-lg border border-border bg-card p-5">
        <div className="flex items-start gap-4">
          <div className="grid size-14 shrink-0 place-items-center rounded-full bg-muted text-muted-foreground">
            <UserRoundIcon className="size-7" aria-hidden="true" />
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-lg font-semibold text-foreground">
              {user.full_name?.trim() || "Ism kiritilmagan"}
            </p>
            {user.seller_rating_count > 0 ? (
              <RatingStars
                value={user.seller_rating}
                count={user.seller_rating_count}
                showValue
                className="mt-1"
              />
            ) : (
              <p className="mt-1 text-sm text-muted-foreground">
                Hali sotuvchi sifatida baholanmagan
              </p>
            )}
          </div>
        </div>

        <dl className="grid gap-2 text-sm">
          <ProfileFact icon={MailIcon} label="Email" value={user.email} />
          <ProfileFact icon={PhoneIcon} label="Telefon" value={me?.phone ?? user.phone} />
          <ProfileFact icon={MapPinIcon} label="Manzil" value={user.location} />
        </dl>

        {user.bio?.trim() && (
          <p className="text-sm leading-relaxed text-muted-foreground">{user.bio}</p>
        )}
      </section>

      {/* Tahrirlash formasi */}
      <section>
        <h2 className="mb-4 text-lg font-semibold text-foreground">
          Maʼlumotlarni tahrirlash
        </h2>
        <form onSubmit={onSubmit} noValidate className="grid gap-5">
          <Field>
            <FieldLabel htmlFor="full_name">Ism familiya</FieldLabel>
            <Input
              id="full_name"
              autoComplete="name"
              aria-invalid={errors.full_name ? true : undefined}
              {...register("full_name")}
            />
            <FieldError>{errors.full_name?.message}</FieldError>
          </Field>

          <Field>
            <FieldLabel htmlFor="location">Manzil</FieldLabel>
            <Input
              id="location"
              autoComplete="address-level2"
              placeholder="Toshkent"
              aria-invalid={errors.location ? true : undefined}
              {...register("location")}
            />
            <FieldError>{errors.location?.message}</FieldError>
          </Field>

          <Field>
            <FieldLabel htmlFor="bio">Bio</FieldLabel>
            <textarea
              id="bio"
              rows={4}
              aria-invalid={errors.bio ? true : undefined}
              placeholder="Oʻzingiz va sotadigan mahsulotlaringiz haqida qisqacha."
              className="w-full resize-y rounded-md border border-input bg-transparent px-3 py-2 text-sm text-foreground outline-none transition-colors placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 aria-invalid:border-destructive aria-invalid:ring-3 aria-invalid:ring-destructive/20"
              {...register("bio")}
            />
            <FieldDescription>Ixtiyoriy — profilingizda koʻrinadi.</FieldDescription>
            <FieldError>{errors.bio?.message}</FieldError>
          </Field>

          {serverError && (
            <p role="alert" className="text-sm font-medium text-destructive">
              {serverError}
            </p>
          )}

          <div>
            <Button type="submit" size="lg" loading={isSubmitting}>
              Saqlash
            </Button>
          </div>
        </form>
      </section>

      {/* Hisob sozlamalari */}
      <section className="grid gap-4">
        <h2 className="text-lg font-semibold text-foreground">Sozlamalar</h2>
        {me ? (
          <>
            <PhoneVerification me={me} onRefresh={refreshMe} />
            <TelegramLink me={me} onChange={setMe} />
            <LanguagePreference me={me} onChange={setMe} />
          </>
        ) : meError ? (
          <p role="alert" className="text-sm font-medium text-destructive">
            {meError}
          </p>
        ) : (
          <>
            <Skeleton className="h-36 w-full rounded-lg" />
            <Skeleton className="h-36 w-full rounded-lg" />
            <Skeleton className="h-28 w-full rounded-lg" />
          </>
        )}
        <ConsentList />
      </section>
    </div>
  )
}

function ProfileFact({
  icon: Icon,
  label,
  value,
}: {
  icon: React.ComponentType<{ className?: string; "aria-hidden"?: boolean }>
  label: string
  value: string | null
}) {
  return (
    <div className="flex items-center gap-2">
      <Icon className="size-4 shrink-0 text-muted-foreground" aria-hidden={true} />
      <dt className="sr-only">{label}</dt>
      <dd className="min-w-0 truncate text-foreground">
        {value?.trim() || <span className="text-muted-foreground">Kiritilmagan</span>}
      </dd>
    </div>
  )
}

export { ProfileView }
