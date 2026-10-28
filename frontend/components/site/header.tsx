"use client"

import * as React from "react"
import Link from "next/link"
import { usePathname, useRouter, useSearchParams } from "next/navigation"
import {
  SearchIcon,
  LayoutGridIcon,
  ChevronDownIcon,
  LogOutIcon,
  PlusIcon,
  PackageIcon,
  TagIcon,
  HandshakeIcon,
  MessageCircleIcon,
  CircleUserIcon,
  ShieldIcon,
  HeartIcon,
  type LucideIcon,
} from "lucide-react"

import { cn } from "@/lib/utils"
import type { Category } from "@/lib/api/types"
import { listCategories } from "@/lib/api/endpoints"
import { useAuthStore } from "@/lib/store/auth"
import { categoryIcon } from "@/lib/category-icon"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { Logo } from "@/components/site/logo"
import { NotificationBell } from "@/components/notification/notification-bell"

/** Kategoriyalar bir marta yuklanadi va menyu hamda pastki qator o'rtasida ulashiladi. */
function useCategories(): Category[] {
  const [categories, setCategories] = React.useState<Category[]>([])
  React.useEffect(() => {
    let alive = true
    listCategories()
      .then((c) => alive && setCategories(c))
      .catch(() => alive && setCategories([]))
    return () => {
      alive = false
    }
  }, [])
  return categories
}

/**
 * Qidiruv — sarlavhaning eng keng elementi: muted "pill", chapda ikonka, ichida
 * "Qidirish" tugmasi. Fokusda card foniga o'tadi va ring halqasi chiqadi.
 */
function SearchForm({ className }: { className?: string }) {
  const router = useRouter()
  const [query, setQuery] = React.useState("")

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    router.push(`/catalog/hammasi?q=${encodeURIComponent(query.trim())}`)
  }

  return (
    <form
      role="search"
      onSubmit={submit}
      className={cn(
        "flex h-12 items-center gap-2.5 rounded-full border border-border bg-muted pr-1.5 pl-4 transition-[background-color,border-color,box-shadow] duration-150 focus-within:border-ring focus-within:bg-card focus-within:ring-3 focus-within:ring-brand-subtle",
        className
      )}
    >
      <SearchIcon className="size-5 shrink-0 text-muted-foreground" aria-hidden="true" />
      <input
        type="search"
        name="q"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Mahsulot yoki kategoriya qidiring"
        aria-label="Qidiruv"
        className="h-full min-w-0 flex-1 bg-transparent text-base text-foreground outline-none placeholder:text-muted-foreground"
      />
      <Button type="submit" size="sm" className="h-9 rounded-full">
        Qidirish
      </Button>
    </form>
  )
}

const menuItemClass =
  "flex h-10 items-center gap-2.5 rounded-sm px-2.5 text-sm text-popover-foreground outline-none transition-colors duration-150 hover:bg-accent focus-visible:bg-accent"

/** Ochiladigan panel (kategoriyalar, hisob menyusi): popover, border, shadow-md. */
function MenuPanel({
  align,
  className,
  children,
  onClose,
}: {
  align: "left" | "right"
  className?: string
  children: React.ReactNode
  onClose: () => void
}) {
  return (
    <>
      <button
        type="button"
        aria-hidden="true"
        tabIndex={-1}
        className="fixed inset-0 z-40 cursor-default"
        onClick={onClose}
      />
      <div
        role="menu"
        className={cn(
          "absolute top-full z-50 mt-2 grid w-62 gap-0.5 rounded-md border border-border bg-popover p-1.5 shadow-md",
          align === "left" ? "left-0" : "right-0",
          className
        )}
      >
        {children}
      </div>
    </>
  )
}

function CategoriesMenu({ categories }: { categories: Category[] }) {
  const [open, setOpen] = React.useState(false)

  return (
    <div className="relative">
      <Button
        variant="secondary"
        aria-expanded={open}
        aria-haspopup="menu"
        aria-label="Kategoriyalar"
        className="h-12 rounded-full"
        onClick={() => setOpen((v) => !v)}
      >
        <LayoutGridIcon aria-hidden="true" />
        {/* Planshetda faqat ikonka — qidiruv va "Sotish"ga joy qolsin. */}
        <span className="hidden lg:inline">Kategoriyalar</span>
        <ChevronDownIcon
          className={cn("size-4 transition-transform duration-200", open && "rotate-180")}
          aria-hidden="true"
        />
      </Button>

      {open && (
        <MenuPanel align="left" className="max-h-96 overflow-y-auto" onClose={() => setOpen(false)}>
          <Link
            role="menuitem"
            href="/catalog/hammasi"
            onClick={() => setOpen(false)}
            className={cn(menuItemClass, "font-medium")}
          >
            <LayoutGridIcon className="size-4.5 text-muted-foreground" aria-hidden="true" />
            Barcha mahsulotlar
          </Link>
          {categories.map((c) => {
            const Icon = categoryIcon(c.slug)
            return (
              <Link
                key={c.id}
                role="menuitem"
                href={`/catalog/${c.slug}`}
                onClick={() => setOpen(false)}
                className={menuItemClass}
              >
                <Icon className="size-4.5 text-muted-foreground" aria-hidden="true" />
                {c.name}
              </Link>
            )
          })}
        </MenuPanel>
      )}
    </div>
  )
}

/** Dumaloq 44px ikonka-tugma (Kuzatuvlar, Xabarlar, Takliflar). */
function IconLink({
  href,
  label,
  Icon,
  className,
}: {
  href: string
  label: string
  Icon: LucideIcon
  className?: string
}) {
  return (
    <Link
      href={href}
      aria-label={label}
      className={cn(
        "grid size-11 shrink-0 place-items-center rounded-full text-foreground outline-none transition-colors duration-150 hover:bg-accent focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring",
        className
      )}
    >
      <Icon className="size-5.5" aria-hidden="true" />
    </Link>
  )
}

/** Foydalanuvchi bosh harflari (avatar o'rnida). */
function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean)
  const letters = parts.length > 1 ? parts[0][0] + parts[1][0] : name.slice(0, 2)
  return letters.toUpperCase()
}

function AuthArea() {
  const status = useAuthStore((s) => s.status)
  const user = useAuthStore((s) => s.user)
  const logout = useAuthStore((s) => s.logout)
  const [open, setOpen] = React.useState(false)

  // Sessiya tiklanmoqda (refresh cookie tekshirilmoqda) — "Kirish" ko'rsatilmaydi, aks holda
  // kirgan foydalanuvchi har sahifa yangilanishida bir lahza "chiqib ketgan"dek ko'rinadi.
  if (status === "idle") {
    return <Skeleton aria-label="Yuklanmoqda" className="h-9 w-32 rounded-full" />
  }

  if (status !== "authenticated" || !user) {
    return (
      <div className="flex items-center gap-2">
        {/* Anonim ham "Sotish"ni ko'radi: kirishga, keyin sotish sahifasiga qaytaradi. */}
        <SellButton href="/login?next=%2Fsell" />
        <Button asChild variant="ghost" size="sm">
          <Link href="/login">Kirish</Link>
        </Button>
        <Button asChild size="sm" className="hidden lg:inline-flex">
          <Link href="/register">Roʻyxatdan oʻtish</Link>
        </Button>
      </div>
    )
  }

  const name = user.full_name || user.email
  const close = () => setOpen(false)

  return (
    <div className="flex items-center gap-1">
      <SellButton className="mr-1" />
      <IconLink href="/my/watchlist" label="Kuzatuvlar" Icon={HeartIcon} className="max-md:hidden" />
      <IconLink href="/offers" label="Takliflar" Icon={HandshakeIcon} className="max-lg:hidden" />
      <IconLink href="/messages" label="Xabarlar" Icon={MessageCircleIcon} />
      <NotificationBell />
      <div className="relative ml-1">
        <button
          type="button"
          aria-expanded={open}
          aria-haspopup="menu"
          aria-label={`Hisob menyusi: ${name}`}
          onClick={() => setOpen((v) => !v)}
          className="grid size-9 place-items-center rounded-full bg-brand-subtle text-sm font-semibold text-brand-subtle-foreground outline-none transition-shadow duration-150 hover:ring-2 hover:ring-border focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
        >
          {initials(name)}
        </button>
        {open && (
          <MenuPanel align="right" onClose={close}>
            <div className="flex items-center gap-2.5 p-2.5">
              <span className="grid size-9 shrink-0 place-items-center rounded-full bg-brand-subtle text-sm font-semibold text-brand-subtle-foreground">
                {initials(name)}
              </span>
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold text-foreground">{name}</p>
                <p className="truncate text-xs text-muted-foreground">{user.email}</p>
              </div>
            </div>
            <div className="my-1 h-px bg-border" />
            <Link role="menuitem" href="/sell" onClick={close} className={cn(menuItemClass, "md:hidden")}>
              <PlusIcon className="size-4.5 text-muted-foreground" aria-hidden="true" />
              Mahsulot joylash
            </Link>
            <Link role="menuitem" href="/my/listings" onClick={close} className={menuItemClass}>
              <TagIcon className="size-4.5 text-muted-foreground" aria-hidden="true" />
              Mening mahsulotlarim
            </Link>
            <Link role="menuitem" href="/offers" onClick={close} className={menuItemClass}>
              <HandshakeIcon className="size-4.5 text-muted-foreground" aria-hidden="true" />
              Takliflar
            </Link>
            <Link role="menuitem" href="/my/watchlist" onClick={close} className={menuItemClass}>
              <HeartIcon className="size-4.5 text-muted-foreground" aria-hidden="true" />
              Kuzatuvlarim
            </Link>
            <Link role="menuitem" href="/orders" onClick={close} className={menuItemClass}>
              <PackageIcon className="size-4.5 text-muted-foreground" aria-hidden="true" />
              Buyurtmalarim
            </Link>
            <Link role="menuitem" href="/messages" onClick={close} className={menuItemClass}>
              <MessageCircleIcon className="size-4.5 text-muted-foreground" aria-hidden="true" />
              Xabarlar
            </Link>
            <Link role="menuitem" href="/profile" onClick={close} className={menuItemClass}>
              <CircleUserIcon className="size-4.5 text-muted-foreground" aria-hidden="true" />
              Profil
            </Link>
            {(user.role === "admin" || user.role === "superadmin") && (
              <Link role="menuitem" href="/admin" onClick={close} className={menuItemClass}>
                <ShieldIcon className="size-4.5 text-muted-foreground" aria-hidden="true" />
                Admin panel
              </Link>
            )}
            <div className="my-1 h-px bg-border" />
            <button
              type="button"
              role="menuitem"
              onClick={() => {
                close()
                void logout()
              }}
              className={cn(menuItemClass, "text-left")}
            >
              <LogOutIcon className="size-4.5 text-muted-foreground" aria-hidden="true" />
              Chiqish
            </button>
          </MenuPanel>
        )}
      </div>
    </div>
  )
}

/**
 * "Sotish" — sarlavhada outline tugma (sahifadagi brend tugma bitta bo'lishi uchun).
 * Telefonda tab-bar markazida. Anonim uchun `href` kirishga, keyin sotishga qaytaradi.
 */
function SellButton({ href = "/sell", className }: { href?: string; className?: string }) {
  return (
    <Button asChild variant="outline" size="sm" className={cn("hidden md:inline-flex", className)}>
      <Link href={href}>
        <PlusIcon aria-hidden="true" />
        Sotish
      </Link>
    </Button>
  )
}

/**
 * Kategoriya qatori (desktop): sarlavha ostida 44px, faol band — siyoh matn.
 * Katalog sahifasida joriy kategoriya belgilanadi.
 */
function SubNav({ categories }: { categories: Category[] }) {
  const pathname = usePathname()
  const sp = useSearchParams()
  const onAll = pathname === "/catalog/hammasi" && !sp.get("sort")
  const onEnding = pathname === "/catalog/hammasi" && sp.get("sort") === "ending"
  const links = [
    { key: "all", href: "/catalog/hammasi", label: "Barcha mahsulotlar", on: onAll },
    { key: "ending", href: "/catalog/hammasi?sort=ending", label: "Tez tugaydi", on: onEnding },
    ...categories.slice(0, 8).map((c) => ({
      key: String(c.id),
      href: `/catalog/${c.slug}`,
      label: c.name,
      on: pathname === `/catalog/${c.slug}`,
    })),
  ]
  return (
    <nav aria-label="Kategoriyalar qatori" className="hidden md:block">
      <ul className="flex h-11 items-center gap-6 overflow-x-auto [scrollbar-width:none]">
        {links.map((l) => (
          <li key={l.key} className="shrink-0">
            <Link
              href={l.href}
              aria-current={l.on ? "page" : undefined}
              className={cn(
                "rounded-xs text-sm font-medium outline-none transition-colors duration-150 hover:text-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring",
                l.on ? "text-foreground" : "text-muted-foreground"
              )}
            >
              {l.label}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  )
}

function SiteHeader() {
  const categories = useCategories()
  return (
    <header className="sticky top-0 z-30 border-b border-border bg-card">
      <div className="mx-auto max-w-page px-4 sm:px-6">
        <div className="flex h-16 items-center gap-4 md:h-18">
          <Logo />

          <div className="hidden md:block">
            <CategoriesMenu categories={categories} />
          </div>

          <SearchForm className="hidden max-w-160 min-w-48 flex-1 md:flex" />

          <div className="ml-auto flex items-center">
            <AuthArea />
          </div>
        </div>

        <SearchForm className="mb-3 md:hidden" />

        <React.Suspense>
          <SubNav categories={categories} />
        </React.Suspense>
      </div>
    </header>
  )
}

export { SiteHeader }
