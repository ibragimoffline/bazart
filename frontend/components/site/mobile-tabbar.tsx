"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import {
  HouseIcon,
  LayoutGridIcon,
  PlusIcon,
  PackageIcon,
  LogInIcon,
  HandshakeIcon,
  type LucideIcon,
} from "lucide-react"

import { cn } from "@/lib/utils"
import { useAuthStore } from "@/lib/store/auth"

type Tab = { href: string; label: string; icon: LucideIcon; match: string }

const ANON: Tab[] = [
  { href: "/", label: "Bosh sahifa", icon: HouseIcon, match: "/" },
  { href: "/catalog/hammasi", label: "Katalog", icon: LayoutGridIcon, match: "/catalog" },
  { href: "/login", label: "Kirish", icon: LogInIcon, match: "/login" },
]

const AUTHED: Tab[] = [
  { href: "/", label: "Bosh sahifa", icon: HouseIcon, match: "/" },
  { href: "/catalog/hammasi", label: "Katalog", icon: LayoutGridIcon, match: "/catalog" },
  { href: "/sell", label: "Sotish", icon: PlusIcon, match: "/sell" },
  // Narx takliflari — asosiy savdo usuli; kuzatuvlar (auksion) sarlavha menyusida qoladi.
  { href: "/offers", label: "Takliflar", icon: HandshakeIcon, match: "/offers" },
  { href: "/orders", label: "Buyurtmalar", icon: PackageIcon, match: "/orders" },
]

function MobileTabBar() {
  const pathname = usePathname()
  const authed = useAuthStore((s) => s.status) === "authenticated"
  const tabs = authed ? AUTHED : ANON

  return (
    <nav
      aria-label="Asosiy navigatsiya"
      className="fixed inset-x-0 bottom-0 z-30 border-t border-border bg-background md:hidden"
    >
      <ul
        className={cn(
          "mx-auto grid max-w-md",
          tabs.length === 5 ? "grid-cols-5" : tabs.length === 4 ? "grid-cols-4" : "grid-cols-3"
        )}
      >
        {tabs.map((tab) => {
          const active =
            tab.match === "/" ? pathname === "/" : pathname.startsWith(tab.match)
          const Icon = tab.icon
          return (
            <li key={tab.href}>
              <Link
                href={tab.href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "group flex flex-col items-center gap-1 px-1 pt-2 pb-2.5 text-center text-xs outline-none transition-colors duration-150 focus-visible:bg-muted",
                  active ? "font-semibold text-brand" : "text-muted-foreground hover:text-foreground"
                )}
              >
                <span
                  className={cn(
                    "grid h-7 w-12 place-items-center rounded-full transition-colors duration-150",
                    active ? "bg-brand-soft" : "group-hover:bg-muted"
                  )}
                >
                  <Icon className="size-5" aria-hidden="true" />
                </span>
                {tab.label}
              </Link>
            </li>
          )
        })}
      </ul>
    </nav>
  )
}

export { MobileTabBar }
