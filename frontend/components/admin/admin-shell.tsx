"use client"

import * as React from "react"
import Link from "next/link"
import { usePathname, useRouter } from "next/navigation"
import {
  LayoutDashboardIcon,
  UsersIcon,
  PackageIcon,
  GavelIcon,
  ReceiptTextIcon,
  LogOutIcon,
  ExternalLinkIcon,
  ShieldAlertIcon,
  FlagIcon,
  HandCoinsIcon,
} from "lucide-react"

import { cn } from "@/lib/utils"
import { useAuthStore } from "@/lib/store/auth"
import { ROLE_LABEL, ROLE_VARIANT } from "@/components/admin/labels"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"

const NAV = [
  { href: "/admin", label: "Boshqaruv", icon: LayoutDashboardIcon, exact: true },
  { href: "/admin/users", label: "Foydalanuvchilar", icon: UsersIcon, exact: false },
  { href: "/admin/items", label: "Tovarlar", icon: PackageIcon, exact: false },
  { href: "/admin/auctions", label: "Auksionlar", icon: GavelIcon, exact: false },
  { href: "/admin/bids", label: "Takliflar", icon: HandCoinsIcon, exact: false },
  { href: "/admin/orders", label: "Buyurtmalar", icon: ReceiptTextIcon, exact: false },
  { href: "/admin/complaints", label: "Shikoyatlar", icon: FlagIcon, exact: false },
] as const

function NavTabs() {
  const pathname = usePathname()
  return (
    <nav
      aria-label="Admin bo'limlari"
      className="-mb-px flex gap-1 overflow-x-auto border-b border-border"
    >
      {NAV.map(({ href, label, icon: Icon, exact }) => {
        const active = exact ? pathname === href : pathname.startsWith(href)
        return (
          <Link
            key={href}
            href={href}
            aria-current={active ? "page" : undefined}
            className={cn(
              "inline-flex shrink-0 items-center gap-2 border-b-2 px-3 py-2.5 text-sm font-medium whitespace-nowrap outline-none transition-colors focus-visible:bg-muted",
              active
                ? "border-primary text-foreground"
                : "border-transparent text-muted-foreground hover:border-border hover:text-foreground"
            )}
          >
            <Icon className="size-4" aria-hidden="true" />
            {label}
          </Link>
        )
      })}
    </nav>
  )
}

function FullScreenMessage({
  icon: Icon,
  title,
  children,
}: {
  icon: React.ComponentType<{ className?: string; "aria-hidden"?: boolean }>
  title: string
  children?: React.ReactNode
}) {
  return (
    <div className="grid min-h-[60vh] place-items-center px-4">
      <div className="grid max-w-sm place-items-center gap-3 text-center">
        <Icon className="size-9 text-muted-foreground" aria-hidden={true} />
        <h1 className="text-xl font-semibold text-foreground">{title}</h1>
        {children}
      </div>
    </div>
  )
}

/**
 * Admin panel qobig'i: kirishni himoyalaydi (faqat admin/superadmin) va
 * navigatsiyani beradi. Anonim -> /login; ruxsatsiz rol -> rad javobi.
 */
function AdminShell({ children }: { children: React.ReactNode }) {
  const status = useAuthStore((s) => s.status)
  const user = useAuthStore((s) => s.user)
  const logout = useAuthStore((s) => s.logout)
  const router = useRouter()

  React.useEffect(() => {
    if (status === "idle") void useAuthStore.getState().loadMe()
  }, [status])

  React.useEffect(() => {
    if (status === "anonymous") router.replace("/login?next=/admin")
  }, [status, router])

  if (status === "idle" || status === "anonymous") {
    return (
      <div className="mx-auto max-w-page px-4 py-8 sm:px-6">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="mt-4 h-10 w-full" />
        <Skeleton className="mt-6 h-64 w-full" />
      </div>
    )
  }

  const role = user?.role
  const allowed = role === "admin" || role === "superadmin"

  if (!allowed) {
    return (
      <FullScreenMessage icon={ShieldAlertIcon} title="Ruxsat yo'q">
        <p className="text-sm text-muted-foreground">
          {"Bu bo'lim faqat administratorlar uchun. Sizning hisobingizda bunday huquq yo'q."}
        </p>
        <Button asChild variant="outline" size="sm">
          <Link href="/">Bosh sahifaga</Link>
        </Button>
      </FullScreenMessage>
    )
  }

  return (
    <div className="min-h-full">
      <header className="sticky top-0 z-30 border-b border-border bg-background">
        <div className="mx-auto flex max-w-page items-center gap-3 px-4 py-2.5 sm:px-6">
          <Link
            href="/admin"
            className="flex items-center gap-2 rounded-md font-heading text-lg font-semibold tracking-tight text-foreground outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
          >
            Bazart
            <Badge variant="default">Admin</Badge>
          </Link>
          <div className="ml-auto flex items-center gap-2">
            {role && (
              <Badge variant={ROLE_VARIANT[role]} className="hidden sm:inline-flex">
                {ROLE_LABEL[role]}
              </Badge>
            )}
            <span className="hidden max-w-40 truncate text-sm text-muted-foreground md:inline">
              {user?.email}
            </span>
            <Button asChild variant="ghost" size="icon-sm" aria-label="Saytga qaytish">
              <Link href="/">
                <ExternalLinkIcon aria-hidden="true" />
              </Link>
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => void logout()}
              aria-label="Chiqish"
            >
              <LogOutIcon aria-hidden="true" />
              <span className="hidden sm:inline">Chiqish</span>
            </Button>
          </div>
        </div>
        <div className="mx-auto max-w-page px-4 sm:px-6">
          <NavTabs />
        </div>
      </header>
      <main className="mx-auto max-w-page px-4 py-6 sm:px-6">{children}</main>
    </div>
  )
}

export { AdminShell }
