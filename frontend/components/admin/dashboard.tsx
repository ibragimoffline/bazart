"use client"

import * as React from "react"
import {
  UsersIcon,
  GavelIcon,
  CheckCircle2Icon,
  BanknoteIcon,
  type LucideIcon,
} from "lucide-react"

import { tiyinToSoum } from "@/lib/format"
import { adminStatistics } from "@/lib/api/admin"
import { useAdminList, ErrorNotice } from "@/components/admin/table"
import { AnimatedInteger } from "@/components/animate-ui/animated-number"
import { Skeleton } from "@/components/ui/skeleton"

function StatCard({
  icon: Icon,
  label,
  children,
}: {
  icon: LucideIcon
  label: string
  children: React.ReactNode
}) {
  return (
    <div className="grid gap-2 rounded-lg border border-border bg-card p-4">
      <div className="flex items-center gap-2 text-muted-foreground">
        <Icon className="size-4" aria-hidden="true" />
        <span className="text-sm">{label}</span>
      </div>
      <p className="font-heading text-2xl font-semibold text-foreground">{children}</p>
    </div>
  )
}

function AdminDashboard() {
  const { data, loading, error } = useAdminList(() => adminStatistics(), [])

  if (loading) {
    return (
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-24 w-full rounded-lg" />
        ))}
      </div>
    )
  }

  if (error || !data) {
    return <ErrorNotice message={error ?? "Statistikani yuklab bo'lmadi."} />
  }

  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      <StatCard icon={UsersIcon} label="Foydalanuvchilar">
        <AnimatedInteger value={data.total_users} />
      </StatCard>
      <StatCard icon={GavelIcon} label="Faol auksionlar">
        <AnimatedInteger value={data.total_active_auctions} />
      </StatCard>
      <StatCard icon={CheckCircle2Icon} label="Yakunlangan buyurtmalar">
        <AnimatedInteger value={data.total_completed_deals} />
      </StatCard>
      <StatCard icon={BanknoteIcon} label="Umumiy savdo">
        <AnimatedInteger value={tiyinToSoum(data.total_sales_amount)} som />
      </StatCard>
    </div>
  )
}

export { AdminDashboard }
