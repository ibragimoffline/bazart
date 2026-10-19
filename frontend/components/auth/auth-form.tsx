"use client"

import * as React from "react"
import Link from "next/link"
import { useRouter, useSearchParams } from "next/navigation"
import { Controller, useForm, useWatch } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { toast } from "sonner"

import { useAuthStore } from "@/lib/store/auth"
import { ApiError } from "@/lib/api/client"
import { recordConsent } from "@/lib/api/legal"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Field, FieldLabel, FieldError } from "@/components/ui/field"
import { Checkbox } from "@/components/ui/checkbox"
import { GoogleSignInButton } from "@/components/auth/google-sign-in-button"

const passwordRule = z
  .string()
  .min(8, "Parol kamida 8 belgidan iborat boʻlsin.")
  .refine((v) => /[a-zA-Z]/.test(v) && /\d/.test(v), {
    message: "Parolda kamida bitta harf va bitta raqam boʻlsin.",
  })

const loginSchema = z.object({
  email: z.string().email("Yaroqli email kiriting."),
  password: z.string().min(1, "Parolni kiriting."),
})

const registerSchema = z.object({
  full_name: z.string().trim().min(2, "Ismni kiriting."),
  email: z.string().email("Yaroqli email kiriting."),
  password: passwordRule,
  accept_terms: z.boolean().refine((v) => v === true, {
    message: "Davom etish uchun kelishuv va siyosatni qabul qiling.",
  }),
})

type AuthValues = {
  full_name?: string
  email: string
  password: string
  accept_terms?: boolean
}

/**
 * Ro'yxatdan o'tgach rozilikni serverga yozadi. Best-effort: hisob allaqachon
 * yaratilgan, shu sabab xato foydalanuvchini to'xtatmaydi — faqat ogohlantiradi.
 */
async function recordSignupConsents() {
  const results = await Promise.allSettled([recordConsent("terms"), recordConsent("privacy")])
  const failed = results.filter((r) => r.status === "rejected")
  if (failed.length > 0) {
    console.warn("Rozilikni yozib boʻlmadi", failed)
    toast.warning("Hisob yaratildi, lekin rozilik qaydini saqlab boʻlmadi.")
  }
}

function AuthForm({ mode }: { mode: "login" | "register" }) {
  const router = useRouter()
  const params = useSearchParams()
  const next = params.get("next") || "/"
  const isLogin = mode === "login"

  const login = useAuthStore((s) => s.login)
  const registerUser = useAuthStore((s) => s.register)
  const loginWithGoogle = useAuthStore((s) => s.loginWithGoogle)
  const [serverError, setServerError] = React.useState<string | null>(null)
  const [googlePending, setGooglePending] = React.useState(false)
  const googleEnabled = Boolean(process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID)

  const {
    register,
    handleSubmit,
    control,
    trigger,
    formState: { errors, isSubmitting },
  } = useForm<AuthValues>({
    resolver: zodResolver(isLogin ? loginSchema : registerSchema),
    mode: "onTouched",
    defaultValues: { accept_terms: false },
  })
  const termsAccepted = useWatch({ control, name: "accept_terms" }) === true

  const onSubmit = handleSubmit(async (values) => {
    setServerError(null)
    try {
      if (isLogin) {
        await login(values.email, values.password)
      } else {
        await registerUser(values.email, values.password, values.full_name)
        await recordSignupConsents()
      }
      router.push(next)
    } catch (e) {
      setServerError(
        e instanceof ApiError ? e.detail : "Kutilmagan xatolik. Qayta urinib koʻring."
      )
    }
  })

  const onGoogleCredential = async (credential: string) => {
    setServerError(null)
    setGooglePending(true)
    try {
      await loginWithGoogle(credential)
      // Register sahifasida tugma faqat rozilikdan keyin faol — qaydni yozamiz.
      if (!isLogin) await recordSignupConsents()
      router.push(next)
    } catch (e) {
      setServerError(
        e instanceof ApiError ? e.detail : "Google orqali kirib boʻlmadi. Qayta urinib koʻring."
      )
    } finally {
      setGooglePending(false)
    }
  }

  return (
    <div className="mx-auto max-w-sm px-4 py-12 sm:px-6">
      <h1 className="mb-1 text-2xl font-semibold text-foreground">
        {isLogin ? "Kirish" : "Roʻyxatdan oʻtish"}
      </h1>
      <p className="mb-6 text-sm text-muted-foreground">
        {isLogin
          ? "Taklif berish uchun hisobingizga kiring."
          : "Bir daqiqada hisob yarating va auksionlarda qatnashing."}
      </p>

      {googleEnabled && (
        <>
          <GoogleSignInButton
            mode={mode}
            disabled={googlePending || isSubmitting || (!isLogin && !termsAccepted)}
            onCredential={onGoogleCredential}
          />
          {!isLogin && !termsAccepted && (
            <p className="mt-2 text-xs text-muted-foreground">
              Google orqali roʻyxatdan oʻtish uchun avval quyidagi kelishuvni qabul qiling.
            </p>
          )}
          <div className="my-6 flex items-center gap-3 text-xs text-muted-foreground">
            <span className="h-px flex-1 bg-border" />
            yoki email orqali
            <span className="h-px flex-1 bg-border" />
          </div>
        </>
      )}

      <form onSubmit={onSubmit} noValidate className="grid gap-4">
        {!isLogin && (
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
        )}

        <Field>
          <FieldLabel htmlFor="email">Email</FieldLabel>
          <Input
            id="email"
            type="email"
            autoComplete="email"
            aria-invalid={errors.email ? true : undefined}
            {...register("email")}
          />
          <FieldError>{errors.email?.message}</FieldError>
        </Field>

        <Field>
          <FieldLabel htmlFor="password">Parol</FieldLabel>
          <Input
            id="password"
            type="password"
            autoComplete={isLogin ? "current-password" : "new-password"}
            aria-invalid={errors.password ? true : undefined}
            {...register("password")}
          />
          <FieldError>{errors.password?.message}</FieldError>
        </Field>

        {!isLogin && (
          <Field>
            <div className="flex items-start gap-2">
              <Controller
                control={control}
                name="accept_terms"
                render={({ field }) => (
                  <Checkbox
                    id="accept_terms"
                    ref={field.ref}
                    name={field.name}
                    checked={field.value === true}
                    onCheckedChange={(checked) => {
                      field.onChange(checked === true)
                      void trigger("accept_terms")
                    }}
                    onBlur={field.onBlur}
                    disabled={isSubmitting}
                    aria-invalid={errors.accept_terms ? true : undefined}
                    aria-describedby={errors.accept_terms ? "accept_terms_error" : undefined}
                    className="mt-0.5 data-[state=checked]:border-primary data-[state=checked]:bg-primary data-[state=checked]:text-primary-foreground"
                  />
                )}
              />
              <FieldLabel
                htmlFor="accept_terms"
                className="cursor-pointer text-sm leading-snug font-normal text-foreground"
              >
                Foydalanuvchi kelishuvi va maxfiylik siyosatini qabul qilaman
              </FieldLabel>
            </div>
            <FieldError id="accept_terms_error">{errors.accept_terms?.message}</FieldError>
          </Field>
        )}

        {serverError && (
          <p role="alert" className="text-sm font-medium text-destructive">
            {serverError}
          </p>
        )}

        <Button type="submit" size="lg" loading={isSubmitting} className="w-full">
          {isLogin ? "Kirish" : "Roʻyxatdan oʻtish"}
        </Button>
      </form>

      <p className="mt-6 text-sm text-muted-foreground">
        {isLogin ? "Hisobingiz yoʻqmi? " : "Hisobingiz bormi? "}
        <Link
          href={isLogin ? "/register" : "/login"}
          className="rounded-sm font-medium text-primary outline-none underline decoration-foreground/30 hover:decoration-foreground focus-visible:ring-3 focus-visible:ring-ring/50 underline-offset-4"
        >
          {isLogin ? "Roʻyxatdan oʻtish" : "Kirish"}
        </Link>
      </p>
    </div>
  )
}

export { AuthForm }
