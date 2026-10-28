"use client"

import * as React from "react"
import Link from "next/link"
import { XIcon, ExternalLinkIcon } from "lucide-react"
import { toast } from "sonner"

import { formatTiyin } from "@/lib/format"
import type { Auction, AuctionStatus } from "@/lib/api/types"
import { ApiError } from "@/lib/api/client"
import { listAdminAuctions, cancelAuction } from "@/lib/api/admin"
import {
  AUCTION_STATUS_LABEL,
  AUCTION_STATUS_VARIANT,
  formatDateTime,
} from "@/components/admin/labels"
import {
  useAdminList,
  TableFrame,
  THead,
  TBody,
  Tr,
  Th,
  Td,
  TableSkeleton,
  EmptyRow,
  ErrorNotice,
} from "@/components/admin/table"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"

const STATUSES: AuctionStatus[] = [
  "scheduled",
  "active",
  "ended",
  "cancelled",
  "reserve_not_met",
]

const selectClass =
  "h-8 rounded-md border border-input bg-transparent px-2.5 text-sm outline-none transition-colors focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:opacity-50"

function AdminAuctionsTable() {
  const [statusFilter, setStatusFilter] = React.useState<AuctionStatus | "">("")
  const [busyId, setBusyId] = React.useState<number | null>(null)

  const { data, setData, loading, error, reload } = useAdminList<Auction[]>(
    () => listAdminAuctions({ status: statusFilter || undefined }),
    [statusFilter]
  )

  const rows = data ?? []

  const doCancel = async (id: number) => {
    setBusyId(id)
    try {
      const updated = await cancelAuction(id)
      setData((prev) => (prev ? prev.map((a) => (a.id === id ? updated : a)) : prev))
      toast.success("Auksion bekor qilindi.")
    } catch (e) {
      toast.error(e instanceof ApiError ? e.detail : "Amal bajarilmadi.")
    } finally {
      setBusyId(null)
    }
  }

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as AuctionStatus | "")}
          aria-label="Holat bo'yicha filtr"
          className={selectClass}
        >
          <option value="">Barcha holatlar</option>
          {STATUSES.map((s) => (
            <option key={s} value={s}>
              {AUCTION_STATUS_LABEL[s]}
            </option>
          ))}
        </select>
      </div>

      {error && <ErrorNotice message={error} />}

      {loading ? (
        <TableSkeleton cols={6} />
      ) : (
        <TableFrame>
          <THead>
            <Tr>
              <Th className="w-12">ID</Th>
              <Th>Tovar</Th>
              <Th>Joriy narx</Th>
              <Th>Holat</Th>
              <Th>Tugash vaqti</Th>
              <Th className="text-right">Amallar</Th>
            </Tr>
          </THead>
          <TBody>
            {rows.length === 0 ? (
              <EmptyRow colSpan={6} message="Auksion topilmadi." />
            ) : (
              rows.map((a) => {
                const busy = busyId === a.id
                const cancellable = a.status === "scheduled" || a.status === "active"
                return (
                  <Tr key={a.id}>
                    <Td className="tabular-nums text-muted-foreground">{a.id}</Td>
                    <Td>
                      <span className="text-foreground">Tovar #{a.item_id}</span>
                      <span className="block text-xs text-muted-foreground">
                        Sotuvchi #{a.seller_id}
                      </span>
                    </Td>
                    <Td className="tabular-nums text-foreground">
                      {formatTiyin(a.current_price)}
                    </Td>
                    <Td>
                      <Badge variant={AUCTION_STATUS_VARIANT[a.status]}>
                        {AUCTION_STATUS_LABEL[a.status]}
                      </Badge>
                    </Td>
                    <Td className="text-muted-foreground">{formatDateTime(a.end_time)}</Td>
                    <Td>
                      <div className="flex justify-end gap-1.5">
                        <Button asChild variant="ghost" size="sm">
                          <Link href={`/lot/${a.id}`}>
                            <ExternalLinkIcon aria-hidden="true" />
                            {"Ko'rish"}
                          </Link>
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          loading={busy}
                          disabled={!cancellable}
                          onClick={() => doCancel(a.id)}
                        >
                          <XIcon aria-hidden="true" />
                          Bekor qilish
                        </Button>
                      </div>
                    </Td>
                  </Tr>
                )
              })
            )}
          </TBody>
        </TableFrame>
      )}

      <div className="mt-4">
        <Button variant="ghost" size="sm" onClick={reload}>
          Yangilash
        </Button>
      </div>
    </div>
  )
}

export { AdminAuctionsTable }
