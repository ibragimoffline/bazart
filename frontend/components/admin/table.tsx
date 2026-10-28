"use client"

import * as React from "react"
import { InboxIcon } from "lucide-react"

import { cn } from "@/lib/utils"
import { ApiError } from "@/lib/api/client"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from "@/components/ui/table"
import {
  Empty,
  EmptyHeader,
  EmptyMedia,
  EmptyDescription,
} from "@/components/ui/empty"

type AdminListState<T> = {
  data: T | null
  setData: React.Dispatch<React.SetStateAction<T | null>>
  loading: boolean
  error: string | null
  reload: () => void
}

/**
 * Ro'yxat yuklovchi async hook. Holat faqat promise callback'larida yangilanadi
 * (effekt tanasida sinxron setState yo'q — cascading render'siz). `setData` —
 * optimistik yangilash uchun (block/rol o'zgarganda qatorni almashtirish).
 */
export function useAdminList<T>(
  loader: () => Promise<T>,
  deps: React.DependencyList
): AdminListState<T> {
  const [data, setData] = React.useState<T | null>(null)
  const [loading, setLoading] = React.useState(true)
  const [error, setError] = React.useState<string | null>(null)
  const [nonce, setNonce] = React.useState(0)

  React.useEffect(() => {
    let alive = true
    // Qayta yuklashda skeleton uchun — mikrotaskda (effekt tanasida sinxron emas).
    Promise.resolve().then(() => {
      if (!alive) return
      setLoading(true)
      setError(null)
    })
    loader()
      .then((result) => {
        if (alive) setData(result)
      })
      .catch((e) => {
        if (!alive) return
        setError(e instanceof ApiError ? e.detail : "Ma'lumotni yuklab bo'lmadi.")
      })
      .finally(() => {
        if (alive) setLoading(false)
      })
    return () => {
      alive = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, nonce])

  return { data, setData, loading, error, reload: () => setNonce((n) => n + 1) }
}

/**
 * Jadval primitivlari — `components/ui/table` ustiga qurilgan (vengeanceui).
 * Bu yerda faqat admin konteksti uchun qobiq va o'lchamlar belgilanadi:
 * karta ramkasi va mobil (360px) uchun gorizontal scroll.
 */
export function TableFrame({ children }: { children: React.ReactNode }) {
  return (
    <div className="overflow-hidden rounded-lg border border-border bg-card">
      <Table className="min-w-[640px]">{children}</Table>
    </div>
  )
}

/** Sarlavha qatorlari guruhi. */
export const THead = TableHeader
/** Ma'lumot qatorlari guruhi. */
export const TBody = TableBody
/** Qator — hover holati `ui/table` dan keladi. */
export const Tr = TableRow

export function Th({
  children,
  className,
}: {
  children?: React.ReactNode
  className?: string
}) {
  return (
    <TableHead
      className={cn(
        "px-3 py-2.5 text-xs font-medium tracking-wide text-muted-foreground",
        className
      )}
    >
      {children}
    </TableHead>
  )
}

export function Td({
  children,
  className,
}: {
  children?: React.ReactNode
  className?: string
}) {
  return <TableCell className={cn("px-3 py-2.5", className)}>{children}</TableCell>
}

export function TableSkeleton({ rows = 6, cols = 5 }: { rows?: number; cols?: number }) {
  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <div className="grid gap-3">
        {Array.from({ length: rows }).map((_, r) => (
          <div key={r} className="flex items-center gap-4">
            {Array.from({ length: cols }).map((_, c) => (
              <Skeleton key={c} className={cn("h-5", c === 0 ? "w-10" : "flex-1")} />
            ))}
          </div>
        ))}
      </div>
    </div>
  )
}

export function EmptyRow({ colSpan, message }: { colSpan: number; message: string }) {
  return (
    <TableRow className="hover:bg-transparent">
      <TableCell colSpan={colSpan} className="p-0">
        <Empty className="border-0">
          <EmptyHeader>
            <EmptyMedia variant="icon">
              <InboxIcon aria-hidden="true" />
            </EmptyMedia>
            <EmptyDescription>{message}</EmptyDescription>
          </EmptyHeader>
        </Empty>
      </TableCell>
    </TableRow>
  )
}

export function ErrorNotice({ message }: { message: string }) {
  return (
    <p role="alert" className="mb-3 text-sm font-medium text-destructive">
      {message}
    </p>
  )
}
