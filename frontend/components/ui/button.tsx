import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { Slot } from "radix-ui"
import { LoaderCircleIcon } from "lucide-react"

import { cn } from "@/lib/utils"

const buttonVariants = cva(
  "group/button inline-flex shrink-0 items-center justify-center rounded-md border border-transparent bg-clip-padding font-semibold whitespace-nowrap transition-colors duration-150 outline-none select-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring active:not-aria-[haspopup]:translate-y-px disabled:pointer-events-none disabled:opacity-45 aria-invalid:border-destructive aria-invalid:ring-3 aria-invalid:ring-error-subtle [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4.5",
  {
    variants: {
      variant: {
        // Asosiy harakat — brend. Ekranda BITTA; yonma-yon ikki brend tugma qo'yilmaydi.
        primary: "bg-brand text-brand-foreground hover:bg-brand-hover",
        // shadcn ichki komponentlari uchun alias (primary bilan bir xil).
        default: "bg-brand text-brand-foreground hover:bg-brand-hover",
        // Ikkilamchi — deyarli oq muted, border chizig'i bilan.
        secondary:
          "border-border bg-secondary text-secondary-foreground hover:bg-border aria-expanded:bg-border",
        outline:
          "border-border bg-card text-foreground shadow-xs hover:bg-muted aria-expanded:bg-muted",
        ghost: "text-foreground hover:bg-accent aria-expanded:bg-accent",
        // Xavfli harakat — to'liq qizil.
        destructive: "bg-destructive text-destructive-foreground hover:bg-destructive/90",
        link: "h-auto px-0 text-brand underline-offset-4 hover:underline",
      },
      size: {
        sm: "h-9 gap-1.5 rounded-sm px-3.5 text-sm",
        md: "h-11 gap-2 px-5 text-sm",
        lg: "h-13 gap-2 px-7 text-base [&_svg:not([class*='size-'])]:size-5",
        // Ichki (pagination/menyu) sizlar — o'zgartirilmaydi.
        default:
          "h-8 gap-1.5 px-2.5 text-sm has-data-[icon=inline-end]:pr-2 has-data-[icon=inline-start]:pl-2",
        icon: "size-11",
        "icon-sm": "size-9 rounded-sm",
        "icon-lg": "size-13",
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
