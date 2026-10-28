"use client"

import * as React from "react"
import Link from "next/link"
import { useRouter, usePathname } from "next/navigation"
import { useForm, Controller } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { StarIcon } from "lucide-react"
import { toast } from "sonner"

import { ApiError } from "@/lib/api/client"
import { useAuthStore } from "@/lib/store/auth"
import { createReview } from "@/lib/api/engagement"
import { Button } from "@/components/ui/button"
import { Field, FieldLabel, FieldError, FieldDescription } from "@/components/ui/field"
import { Skeleton } from "@/components/ui/skeleton"
import { StarRating } from "@/components/review/star-rating"

const schema = z.object({
  stars: z
    .number({ message: "Baho tanlang." })
    .int()
    .min(1, "Baho tanlang.")
    .max(5, "Baho 1 dan 5 gacha boʻlsin."),
  text: z.string().trim().max(1000, "Matn 1000 belgidan oshmasin.").optional(),
})

type FormValues = z.infer<typeof schema>

/**
 * "Sharh qoldirish" formasi. Order COMPLETED bo'lgach ikkinchi tomonni
 * baholaydi — qabul qiluvchi (`to_id`) backend'da order bo'yicha aniqlanadi.
 */
function ReviewForm({ orderId }: { orderId: number }) {
  const status = useAuthStore((s) => s.status)
  const router = useRouter()
  const pathname = usePathname()
  const [serverError, setServerError] = React.useState<string | null>(null)

  const {
    control,
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    mode: "onTouched",
    defaultValues: { stars: 0, text: "" },
  })

  const onSubmit = handleSubmit(async (values) => {
    setServerError(null)
    try {
      await createReview({
        deal_id: orderId,
        stars: values.stars,
        text: values.text?.trim() ? values.text.trim() : undefined,
      })
      toast.success("Sharhingiz uchun rahmat.")
      router.push(`/orders/${orderId}`)
    } catch (e) {
      setServerError(
        e instanceof ApiError ? e.detail : "Sharh yuborib boʻlmadi. Qayta urinib koʻring."
      )
    }
  })

  // --- Auth gate -------------------------------------------------------
  if (status === "idle") {
    return <Skeleton className="h-64 w-full rounded-lg" />
  }

  if (status === "anonymous") {
    return (
      <div className="grid place-items-center gap-3 rounded-lg border border-border bg-card px-6 py-16 text-center">
        <StarIcon className="size-8 text-muted-foreground" aria-hidden="true" />
        <p className="text-base font-medium text-foreground">
          Sharh qoldirish uchun kiring
        </p>
        <Button asChild size="sm">
          <Link href={`/login?next=${encodeURIComponent(pathname)}`}>Kirish</Link>
        </Button>
      </div>
    )
  }

  return (
    <div>
      <h1 className="text-2xl font-semibold text-foreground">Sharh qoldirish</h1>
      <p className="mt-1 mb-6 text-sm text-muted-foreground">
        Buyurtma #{orderId} boʻyicha ikkinchi tomonni baholang.
      </p>

      <form onSubmit={onSubmit} noValidate className="grid gap-6">
        <Field>
          <FieldLabel>Baho</FieldLabel>
          <Controller
            control={control}
            name="stars"
            render={({ field }) => (
              <StarRating
                value={field.value}
                onChange={field.onChange}
                disabled={isSubmitting}
                invalid={!!errors.stars}
              />
            )}
          />
          <FieldError>{errors.stars?.message}</FieldError>
        </Field>

        <Field>
          <FieldLabel htmlFor="text">Izoh (ixtiyoriy)</FieldLabel>
          <textarea
            id="text"
            rows={4}
            aria-invalid={errors.text ? true : undefined}
            placeholder="Muomala, tovar holati va topshirish qanday kechdi?"
            className="w-full resize-y rounded-md border border-input bg-transparent px-3 py-2 text-sm text-foreground outline-none transition-colors placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 aria-invalid:border-destructive aria-invalid:ring-3 aria-invalid:ring-destructive/20"
            {...register("text")}
          />
          <FieldDescription>
            Izoh boshqa foydalanuvchilarga ishonchli qaror qabul qilishda yordam beradi.
          </FieldDescription>
          <FieldError>{errors.text?.message}</FieldError>
        </Field>

        {serverError && (
          <p role="alert" className="text-sm font-medium text-destructive">
            {serverError}
          </p>
        )}

        <div className="flex flex-wrap gap-3">
          <Button type="submit" size="lg" loading={isSubmitting}>
            Sharhni yuborish
          </Button>
          <Button asChild type="button" variant="outline" size="lg">
            <Link href={`/orders/${orderId}`}>Bekor qilish</Link>
          </Button>
        </div>
      </form>
    </div>
  )
}

export { ReviewForm }
