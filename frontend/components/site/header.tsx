"use client"

import * as React from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import {
  SearchIcon,
  UserIcon,
  MenuIcon,
  ChevronDownIcon,
  LogOutIcon,
  PlusIcon,
  PackageIcon,
  TagIcon,
  HandshakeIcon,
  MessageCircleIcon,
  CircleUserIcon,
  ScaleIcon,
  ShieldIcon,
  HeartIcon,
} from "lucide-react"

import { cn } from "@/lib/utils"
import type { Category } from "@/lib/api/types"
import { listCategories } from "@/lib/api/endpoints"
import { useAuthStore } from "@/lib/store/auth"
import { Button } from "@/components/ui/button"
import { Logo } from "@/components/site/logo"
import { NotificationBell } from "@/components/notification/notification-bell"

function SearchForm({ className }: { className?: string }) {
  const router = useRouter()
  const [query, setQuery] = React.useState("")

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    router.push(`/catalog/hammasi?q=${encodeURIComponent(query.trim())}`)
  }

  return (
    <form role="search" onSubmit={submit} className={cn("relative", className)}>
      <SearchIcon
        className="pointer-events-none absolute top-1/2 left-3.5 size-4 -translate-y-1/2 text-muted-foreground"
        aria-hidden="true"
      />
      <input
        type="search"
        name="q"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Mahsulot yoki kategoriya qidiring"
        aria-label="Qidiruv"
        className="h-10 w-full rounded-full border border-border bg-card pr-4 pl-10 text-sm outline-none transition-colors placeholder:text-muted-foreground hover:border-foreground/20 focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
      />
    </form>
  )
}

function CategoriesMenu() {
  const [open, setOpen] = React.useState(false)
  const [categories, setCategories] = React.useState<Category[]>([])

  React.useEffect(() => {
    listCategories()
      .then(setCategories)
      .catch(() => setCategories([]))
  }, [])

  return (
    <div className="relative">
      <Button
        variant="ghost"
        size="md"
        aria-expanded={open}
        aria-haspopup="menu"
        onClick={() => setOpen((v) => !v)}
      >
        <MenuIcon aria-hidden="true" />
        Kategoriyalar
        <ChevronDownIcon
          className={cn("transition-transform duration-200", open && "rotate-180")}
          aria-hidden="true"
        />
      </Button>

      {open && (
        <>
          <button
            type="button"
            aria-hidden="true"
            tabIndex={-1}
            className="fixed inset-0 z-40 cursor-default"
            onClick={() => setOpen(false)}
          />
          <div
            role="menu"
            className="absolute top-full left-0 z-50 mt-1 grid max-h-80 w-56 gap-0.5 overflow-y-auto rounded-lg border border-border bg-popover p-1 shadow-md"
          >
            <Link
              role="menuitem"
              href="/catalog/hammasi"
              onClick={() => setOpen(false)}
              className="rounded-md px-2.5 py-1.5 text-sm font-medium text-popover-foreground outline-none transition-colors hover:bg-muted focus-visible:bg-muted"
            >
              Barcha mahsulotlar
            </Link>
            {categories.map((c) => (
              <Link
                key={c.id}
                role="menuitem"
                href={`/catalog/${c.slug}`}
                onClick={() => setOpen(false)}
                className="rounded-md px-2.5 py-1.5 text-sm text-popover-foreground outline-none transition-colors hover:bg-muted focus-visible:bg-muted"
              >
                {c.name}
              </Link>
            ))}
          </div>
        </>
      )}
    </div>
  )
}

function AuthArea() {
  const status = useAuthStore((s) => s.status)
  const user = useAuthStore((s) => s.user)
  const logout = useAuthStore((s) => s.logout)
  const [open, setOpen] = React.useState(false)

  if (status !== "authenticated" || !user) {
    return (
      <Button asChild variant="outline" size="sm">
        <Link href="/login">Kirish</Link>
      </Button>
    )
  }

  const name = user.full_name || user.email

  return (
    <div className="flex items-center gap-1">
      <Button asChild variant="outline" size="sm" className="hidden sm:inline-flex">
        <Link href="/sell">
          <PlusIcon aria-hidden="true" />
          Sotish
        </Link>
      </Button>
      <Button asChild variant="ghost" size="icon" aria-label="Xabarlar">
        <Link href="/messages">
          <MessageCircleIcon aria-hidden="true" />
        </Link>
      </Button>
      <NotificationBell />
      <div className="relative">
        <Button
          variant="ghost"
          size="sm"
          aria-expanded={open}
          aria-haspopup="menu"
          onClick={() => setOpen((v) => !v)}
        >
          <UserIcon aria-hidden="true" />
          <span className="hidden max-w-32 truncate sm:inline">{name}</span>
        </Button>
        {open && (
          <>
            <button
              type="button"
              aria-hidden="true"
              tabIndex={-1}
              className="fixed inset-0 z-40 cursor-default"
              onClick={() => setOpen(false)}
            />
            <div
              role="menu"
              className="absolute top-full right-0 z-50 mt-1 grid w-52 gap-0.5 rounded-lg border border-border bg-popover p-1 shadow-md"
            >
              <span className="truncate px-2.5 py-1.5 text-xs text-muted-foreground">
                {user.email}
              </span>
              <Link
                role="menuitem"
                href="/sell"
                onClick={() => setOpen(false)}
                className="flex items-center gap-2 rounded-md px-2.5 py-1.5 text-sm text-popover-foreground outline-none transition-colors hover:bg-muted focus-visible:bg-muted sm:hidden"
              >
                <PlusIcon className="size-4" aria-hidden="true" />
                Mahsulot joylash
              </Link>
              <Link
                role="menuitem"
                href="/my/listings"
                onClick={() => setOpen(false)}
                className="flex items-center gap-2 rounded-md px-2.5 py-1.5 text-sm text-popover-foreground outline-none transition-colors hover:bg-muted focus-visible:bg-muted"
              >
                <TagIcon className="size-4" aria-hidden="true" />
                Mening mahsulotlarim
              </Link>
              <Link
                role="menuitem"
                href="/offers"
                onClick={() => setOpen(false)}
                className="flex items-center gap-2 rounded-md px-2.5 py-1.5 text-sm text-popover-foreground outline-none transition-colors hover:bg-muted focus-visible:bg-muted"
              >
                <HandshakeIcon className="size-4" aria-hidden="true" />
                Takliflar
              </Link>
              <Link
                role="menuitem"
                href="/my/watchlist"
                onClick={() => setOpen(false)}
                className="flex items-center gap-2 rounded-md px-2.5 py-1.5 text-sm text-popover-foreground outline-none transition-colors hover:bg-muted focus-visible:bg-muted"
              >
                <HeartIcon className="size-4" aria-hidden="true" />
                Kuzatuvlarim
              </Link>
              <Link
                role="menuitem"
                href="/orders"
                onClick={() => setOpen(false)}
                className="flex items-center gap-2 rounded-md px-2.5 py-1.5 text-sm text-popover-foreground outline-none transition-colors hover:bg-muted focus-visible:bg-muted"
              >
                <PackageIcon className="size-4" aria-hidden="true" />
                Buyurtmalarim
              </Link>
              <Link
                role="menuitem"
                href="/messages"
                onClick={() => setOpen(false)}
                className="flex items-center gap-2 rounded-md px-2.5 py-1.5 text-sm text-popover-foreground outline-none transition-colors hover:bg-muted focus-visible:bg-muted"
              >
                <MessageCircleIcon className="size-4" aria-hidden="true" />
                Xabarlar
              </Link>
              <Link
                role="menuitem"
                href="/disputes"
                onClick={() => setOpen(false)}
                className="flex items-center gap-2 rounded-md px-2.5 py-1.5 text-sm text-popover-foreground outline-none transition-colors hover:bg-muted focus-visible:bg-muted"
              >
                <ScaleIcon className="size-4" aria-hidden="true" />
                Nizolarim
              </Link>
              <Link
                role="menuitem"
                href="/profile"
                onClick={() => setOpen(false)}
                className="flex items-center gap-2 rounded-md px-2.5 py-1.5 text-sm text-popover-foreground outline-none transition-colors hover:bg-muted focus-visible:bg-muted"
              >
                <CircleUserIcon className="size-4" aria-hidden="true" />
                Profil
              </Link>
              {(user.role === "admin" || user.role === "superadmin") && (
                <Link
                  role="menuitem"
                  href="/admin"
                  onClick={() => setOpen(false)}
                  className="flex items-center gap-2 rounded-md px-2.5 py-1.5 text-sm text-popover-foreground outline-none transition-colors hover:bg-muted focus-visible:bg-muted"
                >
                  <ShieldIcon className="size-4" aria-hidden="true" />
                  Admin panel
                </Link>
              )}
              <button
                type="button"
                role="menuitem"
                onClick={() => {
                  setOpen(false)
                  void logout()
                }}
                className="flex items-center gap-2 rounded-md px-2.5 py-1.5 text-left text-sm text-popover-foreground outline-none transition-colors hover:bg-muted focus-visible:bg-muted"
              >
                <LogOutIcon className="size-4" aria-hidden="true" />
                Chiqish
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

function SiteHeader() {
  return (
    <header className="sticky top-0 z-30 border-b border-border bg-background">
      <div className="mx-auto flex max-w-6xl items-center gap-3 px-4 py-2.5 sm:px-6">
        <Logo />

        <div className="hidden items-center gap-1 md:flex">
          <CategoriesMenu />
        </div>

        <SearchForm className="hidden flex-1 md:block" />

        <div className="ml-auto flex items-center gap-1 md:ml-0">
          <AuthArea />
        </div>
      </div>

      <div className="px-4 pb-2.5 md:hidden">
        <SearchForm />
      </div>
    </header>
  )
}

export { SiteHeader }
