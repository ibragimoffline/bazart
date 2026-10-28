import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { Slot } from "radix-ui"

import { cn } from "@/lib/utils"

const badgeVariants = cva(
  "group/badge inline-flex h-6 w-fit shrink-0 items-center justify-center gap-1 overflow-hidden rounded-full border border-transparent px-2.5 text-xs font-semibold whitespace-nowrap transition-colors has-data-[icon=inline-end]:pr-2 has-data-[icon=inline-start]:pl-2 [&>svg]:pointer-events-none [&>svg]:size-3!",
  {
    variants: {
      variant: {
        // Belgilar sukut bo'yicha TONAL (*-subtle fon + *-subtle-foreground matn) —
        // holatlar ro'yxati tinch turadi. Solid — faqat bitta urg'u uchun.
        default: "bg-brand-subtle text-brand-subtle-foreground",
        brand: "bg-brand-subtle text-brand-subtle-foreground",
        secondary: "border-border bg-muted text-foreground",
        success: "bg-success-subtle text-success-subtle-foreground",
        warning: "bg-warning-subtle text-warning-subtle-foreground",
        error: "bg-error-subtle text-error-subtle-foreground",
        // Eski nom (chegirma) — error tonal.
        sale: "bg-error-subtle text-error-subtle-foreground",
        // "Tugagan", "Sotildi" — mavjud emas holati, quyuq neytral.
        neutral: "bg-foreground text-background",
        outline: "border-border bg-transparent text-muted-foreground",
        // Solid — bitta urg'u (G'olib, "Bugun tugaydi"). warning'da doim quyuq matn.
        "brand-solid": "bg-brand text-brand-foreground",
        "success-solid": "bg-success text-success-foreground",
        "warning-solid": "bg-warning text-warning-foreground",
        "error-solid": "bg-error text-error-foreground",
        // Foto ustida ruxsat etilgan yagona belgi (holat: Yangi / Ishlatilgan).
        "on-photo": "bg-card text-foreground shadow-sm",
        ghost: "hover:bg-muted hover:text-muted-foreground",
        link: "text-brand underline-offset-4 hover:underline",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

function Badge({
  className,
  variant = "default",
  asChild = false,
  ...props
}: React.ComponentProps<"span"> &
  VariantProps<typeof badgeVariants> & { asChild?: boolean }) {
  const Comp = asChild ? Slot.Root : "span"

  return (
    <Comp
      data-slot="badge"
      data-variant={variant}
      className={cn(badgeVariants({ variant }), className)}
      {...props}
    />
  )
}

export { Badge, badgeVariants }
