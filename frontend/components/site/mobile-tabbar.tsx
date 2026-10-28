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
import { Skeleton } from "@/components/ui/skeleton"

type Tab = { href: string; label: string; icon: LucideIcon; match: string }

// Anonim tashrifchi ham markazda "Sotish"ni ko'radi: u kirishga olib boradi va
// kirgandan keyin sotish sahifasiga qaytaradi (`next`).
const ANON: Tab[] = [
  { href: "/", label: "Bosh sahifa", icon: HouseIcon, match: "/" },
  { href: "/catalog/hammasi", label: "Katalog", icon: LayoutGridIcon, match: "/catalog" },
  { href: "/login?next=%2Fsell", label: "Sotish", icon: PlusIcon, match: "/sell" },
  { href: "/offers", label: "Takliflar", icon: HandshakeIcon, match: "/offers" },
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
  const status = useAuthStore((s) => s.status)
  // Sessiya tiklanayotganda "Kirish" ko'rsatilmaydi — o'rnida joy egallovchi turadi.
  // "Sotish" esa /sell ga boradi: sahifaning o'zi sessiya holatini kutadi.
  const restoring = status === "idle"
  const tabs =
    status === "authenticated" ? AUTHED : restoring ? [...AUTHED.slice(0, 3), AUTHED[3]] : ANON
  const columns = restoring ? 5 : tabs.length

  return (
    <nav
      aria-label="Asosiy navigatsiya"
      className="fixed inset-x-0 bottom-0 z-30 border-t border-border bg-card pb-[env(safe-area-inset-bottom)] md:hidden"
    >
      <ul
        className={cn(
          "mx-auto grid max-w-md px-1 pt-1.5 pb-2.5",
          columns === 5 ? "grid-cols-5" : columns === 4 ? "grid-cols-4" : "grid-cols-3"
        )}
      >
        {tabs.map((tab) => {
          const active =
            tab.match === "/" ? pathname === "/" : pathname.startsWith(tab.match)
          const sell = tab.match === "/sell"
          const Icon = tab.icon
          return (
            <li key={tab.href}>
              <Link
                href={tab.href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "group grid justify-items-center gap-0.5 px-1 py-1 text-center text-xs outline-none transition-colors duration-150 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-ring",
                  active || sell
                    ? "font-semibold text-brand"
                    : "font-medium text-muted-foreground hover:text-foreground"
                )}
              >
                {/* Ikonka 52x30 "pill" ichida; "Sotish" — doim to'ldirilgan brend pill. */}
                <span
                  className={cn(
                    "grid h-7.5 w-13 place-items-center rounded-full transition-colors duration-150",
                    sell
                      ? "bg-brand text-brand-foreground group-hover:bg-brand-hover"
                      : active
                        ? "bg-brand-subtle"
                        : "group-hover:bg-accent"
                  )}
                >
                  <Icon className="size-5.5" aria-hidden="true" />
                </span>
                {tab.label}
              </Link>
            </li>
          )
        })}
        {restoring && (
          <li aria-hidden="true" className="grid justify-items-center gap-0.5 px-1 py-1">
            <Skeleton className="h-7.5 w-13 rounded-full" />
            <Skeleton className="h-3 w-10" />
          </li>
        )}
      </ul>
    </nav>
  )
}

export { MobileTabBar }
