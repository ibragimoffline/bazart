"use client"

import * as React from "react"
import { formatTiyin } from "@/lib/format"
import type { Order, OrderStatus } from "@/lib/api/types"
import { listAdminOrders } from "@/lib/api/admin"
import {
  ORDER_STATUS_LABEL,
  ORDER_STATUS_VARIANT,
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

const STATUSES: OrderStatus[] = [
  "agreed",
  "completed",
  "cancelled",
]

const selectClass =
  "h-8 rounded-md border border-input bg-transparent px-2.5 text-sm outline-none transition-colors focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:opacity-50"

function AdminOrdersTable() {
  const [statusFilter, setStatusFilter] = React.useState<OrderStatus | "">("")

  const { data, loading, error, reload } = useAdminList<Order[]>(
    () => listAdminOrders({ status: statusFilter || undefined }),
    [statusFilter]
  )

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as OrderStatus | "")}
          aria-label="Holat bo'yicha filtr"
          className={selectClass}
        >
          <option value="">Barcha holatlar</option>
          {STATUSES.map((s) => (
            <option key={s} value={s}>
              {ORDER_STATUS_LABEL[s]}
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
              <Th>Xaridor / Sotuvchi</Th>
              <Th>Yakuniy narx</Th>
              <Th>Holat</Th>
              <Th>Yaratilgan</Th>
            </Tr>
          </THead>
          <TBody>
            {!data || data.length === 0 ? (
              <EmptyRow colSpan={6} message="Buyurtma topilmadi." />
            ) : (
              data.map((o) => (
                <Tr key={o.id}>
                  <Td className="tabular-nums text-muted-foreground">{o.id}</Td>
                  <Td className="text-foreground">Tovar #{o.item_id}</Td>
                  <Td className="text-muted-foreground">
                    #{o.buyer_id} / #{o.seller_id}
                  </Td>
                  <Td className="tabular-nums text-foreground">
                    {formatTiyin(o.final_price)}
                  </Td>
                  <Td>
                    <Badge variant={ORDER_STATUS_VARIANT[o.status]}>
                      {ORDER_STATUS_LABEL[o.status]}
                    </Badge>
                  </Td>
                  <Td className="text-muted-foreground">{formatDateTime(o.created_at)}</Td>
                </Tr>
              ))
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

export { AdminOrdersTable }
