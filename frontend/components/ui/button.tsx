import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { Slot } from "radix-ui"
import { LoaderCircleIcon } from "lucide-react"

import { cn } from "@/lib/utils"

const buttonVariants = cva(
  "group/button inline-flex shrink-0 items-center justify-center rounded-full border border-transparent bg-clip-padding font-medium whitespace-nowrap transition-all outline-none select-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 active:not-aria-[haspopup]:translate-y-px disabled:pointer-events-none disabled:opacity-50 aria-invalid:border-destructive aria-invalid:ring-3 aria-invalid:ring-destructive/20 [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
  {
    variants: {
      variant: {
        // Asosiy harakat — siyoh (brend).
        primary:
          "bg-primary text-primary-foreground hover:bg-primary/90 focus-visible:ring-primary/40",
        // shadcn ichki komponentlari uchun alias (primary bilan bir xil).
        default:
          "bg-primary text-primary-foreground hover:bg-primary/90 focus-visible:ring-primary/40",
        // Ikkilamchi — neytral to'ldirilgan.
        secondary:
          "border-border bg-secondary text-secondary-foreground hover:bg-[color-mix(in_oklab,var(--secondary),var(--foreground)_6%)]",
        outline:
          "border-border bg-background hover:bg-muted hover:text-foreground aria-expanded:bg-muted dark:border-input dark:bg-input/30 dark:hover:bg-input/50",
        ghost:
          "hover:bg-muted hover:text-foreground aria-expanded:bg-muted dark:hover:bg-muted/50",
        // Xavfli harakat — to'liq qizil.
        destructive:
          "bg-destructive text-destructive-foreground hover:bg-destructive/90 focus-visible:ring-destructive/40",
        link: "text-primary underline-offset-4 underline decoration-foreground/30 hover:decoration-foreground",
      },
      size: {
        sm: "h-9 gap-1.5 px-3 text-sm",
        md: "h-10 gap-2 px-4 text-sm",
        lg: "h-11 gap-2 px-6 text-base [&_svg:not([class*='size-'])]:size-5",
        // Ichki (pagination/menyu) sizlar — o'zgartirilmaydi.
        default:
          "h-8 gap-1.5 px-2.5 text-sm has-data-[icon=inline-end]:pr-2 has-data-[icon=inline-start]:pl-2",
        icon: "size-10",
        "icon-sm": "size-9",
        "icon-lg": "size-11",
      },
    },
    defaultVariants: {
      variant: "primary",
      size: "md",
    },
  }
)

function Button({
  className,
  variant,
  size,
  asChild = false,
  loading = false,
  disabled,
  children,
  ...props
}: React.ComponentProps<"button"> &
  VariantProps<typeof buttonVariants> & {
    asChild?: boolean
    /** Yuklanish holati: spinner ko'rsatiladi va tugma o'chiriladi. */
    loading?: boolean
  }) {
  const Comp = asChild ? Slot.Root : "button"

  // asChild (Slot) yagona farzand talab qiladi — u holda spinner qo'shilmaydi.
  return (
    <Comp
      data-slot="button"
      data-variant={variant}
      data-size={size}
      data-loading={loading || undefined}
      aria-busy={loading || undefined}
      className={cn(buttonVariants({ variant, size, className }))}
      {...(asChild ? {} : { disabled: disabled || loading })}
      {...props}
    >
      {asChild ? (
        children
      ) : (
        <>
          {loading && (
            <>
              <LoaderCircleIcon className="animate-spin" aria-hidden="true" />
              <span className="sr-only">Yuklanmoqda</span>
            </>
          )}
          {children}
        </>
      )}
    </Comp>
  )
}

export { Button, buttonVariants }
