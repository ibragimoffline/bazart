"use client"

import Link from "next/link"
import { PlusIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import { MyListings } from "@/components/seller/my-listings"

export default function MyListingsPage() {
  return (
    <div className="mx-auto max-w-3xl px-4 py-8 sm:px-6">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <h1 className="font-heading text-xl font-bold tracking-tight text-foreground uppercase md:text-2xl">Mening mahsulotlarim</h1>
        <Button asChild size="sm">
          <Link href="/sell">
            <PlusIcon aria-hidden="true" />
            Mahsulot joylash
          </Link>
        </Button>
      </div>
      <MyListings />
    </div>
  )
}
