"use client"

/**
 * Ichki komponent showcase — /dev/components.
 * Barcha bazaviy komponentlar barcha holatlari bilan vizual tekshiruv uchun.
 * Bu ishlab chiqarish sahifasi EMAS.
 */

import * as React from "react"
import { toast } from "sonner"
import { SunIcon, MoonIcon, SearchIcon, ShoppingCartIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Checkbox } from "@/components/ui/checkbox"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { Label } from "@/components/ui/label"
import { Field, FieldLabel, FieldDescription, FieldError } from "@/components/ui/field"
import { ProductCard } from "@/components/ui/product-card"
import { Skeleton, SkeletonText, ProductCardSkeleton } from "@/components/ui/skeleton"
import {
  Breadcrumb,
  BreadcrumbList,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb"
import { Pager } from "@/components/ui/pager"
import { Toaster } from "@/components/ui/sonner"

const PRODUCTS = [
  {
    title: "Apple iPhone 13 128GB, Midnight rangi",
    price: 8_900_000,
    oldPrice: 10_200_000,
    rating: 4.8,
    ratingCount: 37,
    seed: "iphone13",
  },
  {
    title: "Samsung Galaxy A55 5G, 8/256GB",
    price: 4_250_000,
    rating: 4.6,
    ratingCount: 52,
    seed: "galaxya55",
    isNew: true,
  },
  {
    title: "Yogʻoch yozuv stoli, eman shpon",
    price: 1_350_000,
    oldPrice: 1_600_000,
    rating: 4.9,
    ratingCount: 14,
    seed: "desk",
  },
  {
    title: "Divan-krovat «Milano», bej mato",
    price: 3_100_000,
    rating: 4.7,
    ratingCount: 23,
    seed: "sofa",
    sold: true,
  },
]

function Section({
  title,
  children,
}: {
  title: string
  children: React.ReactNode
}) {
  return (
    <section className="grid gap-4 border-t border-border pt-8">
      <h2 className="text-xl font-semibold text-foreground">{title}</h2>
      {children}
    </section>
  )
}

function Swatch({ label, className }: { label: string; className: string }) {
  return (
    <div className="grid gap-1.5 text-xs">
      <div className={`h-14 rounded-md border border-border ${className}`} />
      <span className="text-muted-foreground">{label}</span>
    </div>
  )
}

export default function ComponentsShowcase() {
  const [dark, setDark] = React.useState(false)
  const [checked, setChecked] = React.useState(true)
  const [loadingDemo, setLoadingDemo] = React.useState(false)
  const [page, setPage] = React.useState(3)

  const toggleTheme = () => {
    const next = !dark
    setDark(next)
    document.documentElement.classList.toggle("dark", next)
  }

  const runLoading = () => {
    setLoadingDemo(true)
    window.setTimeout(() => setLoadingDemo(false), 1600)
  }

  return (
    <div className="min-h-full bg-background">
      <Toaster />
      <div className="mx-auto grid max-w-5xl gap-8 px-4 py-10 sm:px-6">
        {/* Sarlavha */}
        <header className="flex items-center justify-between gap-4">
          <div className="grid gap-1">
            <p className="text-sm font-medium uppercase tracking-wide text-muted-foreground">
              Bazart · UI kutubxona
            </p>
            <h1 className="text-2xl font-semibold text-foreground sm:text-2xl">
              Komponentlar showcase
            </h1>
          </div>
          <Button variant="outline" size="sm" onClick={toggleTheme}>
            {dark ? <SunIcon aria-hidden="true" /> : <MoonIcon aria-hidden="true" />}
            {dark ? "Yorugʻ" : "Qorongʻu"}
          </Button>
        </header>

        {/* Palitra */}
        <Section title="Palitra">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 md:grid-cols-6">
            <Swatch label="background" className="bg-background" />
            <Swatch label="card" className="bg-card" />
            <Swatch label="muted" className="bg-muted" />
            <Swatch label="primary (brend)" className="bg-primary" />
            <Swatch label="success" className="bg-success" />
            <Swatch label="warning" className="bg-warning" />
            <Swatch label="error" className="bg-destructive" />
            <Swatch label="foreground" className="bg-foreground" />
          </div>
        </Section>

        {/* Button */}
        <Section title="Button">
          <div className="grid gap-4">
            <div className="flex flex-wrap items-center gap-3">
              <Button variant="primary">Asosiy</Button>
              <Button variant="secondary">Ikkilamchi</Button>
              <Button variant="ghost">Ghost</Button>
              <Button variant="outline">Outline</Button>
              <Button variant="destructive">Oʻchirish</Button>
              <Button variant="link">Havola</Button>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <Button size="sm">Kichik (sm)</Button>
              <Button size="md">Oʻrta (md)</Button>
              <Button size="lg">Katta (lg)</Button>
              <Button>
                <SearchIcon aria-hidden="true" />
                Ikonka bilan
              </Button>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <Button disabled>Oʻchirilgan</Button>
              <Button loading>Yuklanmoqda</Button>
              <Button variant="secondary" loading>
                Saqlanmoqda
              </Button>
              <Button onClick={runLoading} loading={loadingDemo}>
                Bosib sinang
              </Button>
            </div>
            <p className="text-sm text-muted-foreground">
              Fokusni tekshirish uchun <kbd>Tab</kbd> bosing — koʻrinadigan ring
              chiqadi.
            </p>
          </div>
        </Section>

        {/* Forma boshqaruvlari */}
        <Section title="Forma boshqaruvlari">
          <div className="grid gap-6 sm:grid-cols-2">
            <Field>
              <FieldLabel htmlFor="f-name">Ismingiz</FieldLabel>
              <Input id="f-name" placeholder="Masalan, Alisher" />
              <FieldDescription>Ism va familiyangizni kiriting.</FieldDescription>
            </Field>

            <Field>
              <FieldLabel htmlFor="f-email">Email (xato holati)</FieldLabel>
              <Input
                id="f-email"
                defaultValue="alisher@"
                aria-invalid
                aria-describedby="f-email-err"
              />
              <FieldError id="f-email-err">
                Email manzil notoʻgʻri formatda.
              </FieldError>
            </Field>

            <Field>
              <FieldLabel htmlFor="f-city">Shahar</FieldLabel>
              <Select>
                <SelectTrigger id="f-city" className="w-full">
                  <SelectValue placeholder="Shaharni tanlang" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="tashkent">Toshkent</SelectItem>
                  <SelectItem value="samarkand">Samarqand</SelectItem>
                  <SelectItem value="bukhara">Buxoro</SelectItem>
                  <SelectItem value="andijan">Andijon</SelectItem>
                </SelectContent>
              </Select>
            </Field>

            <Field>
              <FieldLabel htmlFor="f-disabled">Oʻchirilgan maydon</FieldLabel>
              <Input id="f-disabled" defaultValue="Tahrirlab boʻlmaydi" disabled />
            </Field>

            <Field>
              <div className="flex items-center gap-2">
                <Checkbox
                  id="f-terms"
                  checked={checked}
                  onCheckedChange={(v) => setChecked(v === true)}
                />
                <Label htmlFor="f-terms">Shartlarga roziman</Label>
              </div>
              <div className="flex items-center gap-2">
                <Checkbox id="f-terms-err" aria-invalid />
                <Label htmlFor="f-terms-err">Xatolik holati (aria-invalid)</Label>
              </div>
              <div className="flex items-center gap-2">
                <Checkbox id="f-terms-dis" disabled />
                <Label htmlFor="f-terms-dis">Oʻchirilgan</Label>
              </div>
            </Field>

            <Field>
              <FieldLabel>Yetkazib berish usuli</FieldLabel>
              <RadioGroup defaultValue="pickup">
                <div className="flex items-center gap-2">
                  <RadioGroupItem id="d-pickup" value="pickup" />
                  <Label htmlFor="d-pickup">Oʻzim olib ketaman</Label>
                </div>
                <div className="flex items-center gap-2">
                  <RadioGroupItem id="d-courier" value="courier" />
                  <Label htmlFor="d-courier">Kuryer orqali</Label>
                </div>
                <div className="flex items-center gap-2">
                  <RadioGroupItem id="d-post" value="post" disabled />
                  <Label htmlFor="d-post">Pochta (vaqtincha yoʻq)</Label>
                </div>
              </RadioGroup>
            </Field>
          </div>
        </Section>

        {/* Badge */}
        <Section title="Badge">
          <div className="flex flex-wrap items-center gap-2">
            <Badge>Yangi</Badge>
            <Badge variant="success">Tasdiqlangan</Badge>
            <Badge variant="warning">Kam qoldi</Badge>
            <Badge variant="sale">−30%</Badge>
            <Badge variant="neutral">Sotildi</Badge>
            <Badge variant="secondary">Bepul yetkazish</Badge>
            <Badge variant="outline">Kategoriya</Badge>
          </div>
        </Section>

        {/* ProductCard */}
        <Section title="ProductCard">
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
            {PRODUCTS.map((p) => (
              <ProductCard
                key={p.seed}
                title={p.title}
                price={p.price}
                oldPrice={p.oldPrice}
                rating={p.rating}
                ratingCount={p.ratingCount}
                isNew={p.isNew}
                sold={p.sold}
                image={`https://picsum.photos/seed/${p.seed}/600/600`}
                onAddToCart={() =>
                  toast.success("Savatga qoʻshildi", { description: p.title })
                }
              />
            ))}
          </div>
        </Section>

        {/* Skeleton */}
        <Section title="Skeleton">
          <div className="grid gap-6 sm:grid-cols-2">
            <div className="grid gap-3">
              <p className="text-sm text-muted-foreground">Matn varianti</p>
              <SkeletonText lines={4} />
            </div>
            <div className="grid gap-3">
              <p className="text-sm text-muted-foreground">Karta varianti</p>
              <div className="grid grid-cols-2 gap-4">
                <ProductCardSkeleton />
                <ProductCardSkeleton />
              </div>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <Skeleton className="size-12 rounded-full" />
            <div className="grid flex-1 gap-2">
              <Skeleton className="h-4 w-1/3" />
              <Skeleton className="h-4 w-1/2" />
            </div>
          </div>
        </Section>

        {/* Breadcrumb */}
        <Section title="Breadcrumb">
          <Breadcrumb>
            <BreadcrumbList>
              <BreadcrumbItem>
                <BreadcrumbLink href="#">Bosh sahifa</BreadcrumbLink>
              </BreadcrumbItem>
              <BreadcrumbSeparator />
              <BreadcrumbItem>
                <BreadcrumbLink href="#">Elektronika</BreadcrumbLink>
              </BreadcrumbItem>
              <BreadcrumbSeparator />
              <BreadcrumbItem>
                <BreadcrumbLink href="#">Telefonlar</BreadcrumbLink>
              </BreadcrumbItem>
              <BreadcrumbSeparator />
              <BreadcrumbItem>
                <BreadcrumbPage>iPhone 13</BreadcrumbPage>
              </BreadcrumbItem>
            </BreadcrumbList>
          </Breadcrumb>
        </Section>

        {/* Pagination */}
        <Section title="Pagination">
          <Pager page={page} totalPages={12} onPageChange={setPage} />
          <p className="text-sm text-muted-foreground">Joriy sahifa: {page}</p>
        </Section>

        {/* Toast */}
        <Section title="Toast">
          <div className="flex flex-wrap items-center gap-3">
            <Button
              variant="secondary"
              onClick={() =>
                toast.success("Savatga qoʻshildi", {
                  description: "Apple iPhone 13 128GB",
                })
              }
            >
              <ShoppingCartIcon aria-hidden="true" />
              Muvaffaqiyat
            </Button>
            <Button
              variant="secondary"
              onClick={() =>
                toast.error("Xatolik yuz berdi", {
                  description: "Ulanishni tekshirib, qayta urinib koʻring.",
                })
              }
            >
              Xatolik
            </Button>
          </div>
        </Section>
      </div>
    </div>
  )
}
