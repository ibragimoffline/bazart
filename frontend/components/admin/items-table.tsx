"use client"

import * as React from "react"
import { SearchIcon, CheckIcon, XIcon } from "lucide-react"
import { toast } from "sonner"

import { formatTiyin } from "@/lib/format"
import type { Item, ItemStatus } from "@/lib/api/types"
import { ApiError } from "@/lib/api/client"
import { listAdminItems, approveItem, rejectItem } from "@/lib/api/admin"
import {
  ITEM_STATUS_LABEL,
  ITEM_STATUS_VARIANT,
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
import { Input } from "@/components/ui/input"

const STATUSES: ItemStatus[] = [
  "draft",
  "scheduled",
  "pending",
  "active",
  "sold",
  "cancelled",
]

const selectClass =
  "h-8 rounded-md border border-input bg-transparent px-2.5 text-sm outline-none transition-colors focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:opacity-50"

function AdminItemsTable() {
  const [search, setSearch] = React.useState("")
  const [query, setQuery] = React.useState("")
  const [statusFilter, setStatusFilter] = React.useState<ItemStatus | "">("")
  const [busyId, setBusyId] = React.useState<number | null>(null)

  const { data, setData, loading, error, reload } = useAdminList<Item[]>(
    () =>
      listAdminItems({
        search: query || undefined,
        status: statusFilter || undefined,
      }),
    [query, statusFilter]
  )

  const rows = data ?? []

  const submitSearch = (e: React.FormEvent) => {
    e.preventDefault()
    setQuery(search.trim())
  }

  const runAction = async (fn: () => Promise<Item>, id: number, ok: string) => {
    setBusyId(id)
    try {
      const updated = await fn()
      setData((prev) => (prev ? prev.map((it) => (it.id === id ? updated : it)) : prev))
      toast.success(ok)
    } catch (e) {
      toast.error(e instanceof ApiError ? e.detail : "Amal bajarilmadi.")
    } finally {
      setBusyId(null)
    }
  }

  return (
    <div>
      <form
        onSubmit={submitSearch}
        className="mb-4 flex flex-wrap items-center gap-2"
        role="search"
      >
        <div className="relative min-w-52 flex-1">
          <SearchIcon
            className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground"
            aria-hidden="true"
          />
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Sarlavha yoki tavsif bo'yicha"
            aria-label="Tovar qidirish"
            className="h-8 pl-8"
          />
        </div>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as ItemStatus | "")}
          aria-label="Holat bo'yicha filtr"
          className={selectClass}
        >
          <option value="">Barcha holatlar</option>
          {STATUSES.map((s) => (
            <option key={s} value={s}>
              {ITEM_STATUS_LABEL[s]}
            </option>
          ))}
        </select>
        <Button type="submit" variant="outline" size="sm">
          Qidirish
        </Button>
      </form>

      {error && <ErrorNotice message={error} />}

      {loading ? (
        <TableSkeleton cols={5} />
      ) : (
        <TableFrame>
          <THead>
            <Tr>
              <Th className="w-12">ID</Th>
              <Th>Tovar</Th>
              <Th>{"Boshlang'ich narx"}</Th>
              <Th>Holat</Th>
              <Th>Yaratilgan</Th>
              <Th className="text-right">Moderatsiya</Th>
            </Tr>
          </THead>
          <TBody>
            {rows.length === 0 ? (
              <EmptyRow colSpan={6} message="Tovar topilmadi." />
            ) : (
              rows.map((it) => {
                const busy = busyId === it.id
                return (
                  <Tr key={it.id}>
                    <Td className="tabular-nums text-muted-foreground">{it.id}</Td>
                    <Td>
                      <span className="font-medium text-foreground">{it.title}</span>
                      <span className="block text-xs text-muted-foreground">
                        Sotuvchi #{it.seller_id}
                      </span>
                    </Td>
                    <Td className="tabular-nums text-foreground">
                      {formatTiyin(it.starting_price)}
                    </Td>
                    <Td>
                      <Badge variant={ITEM_STATUS_VARIANT[it.status]}>
                        {ITEM_STATUS_LABEL[it.status]}
                      </Badge>
                    </Td>
                    <Td className="text-muted-foreground">{formatDateTime(it.created_at)}</Td>
                    <Td>
                      <div className="flex justify-end gap-1.5">
                        <Button
                          variant="outline"
                          size="sm"
                          loading={busy}
                          disabled={it.status === "active"}
                          onClick={() =>
                            runAction(() => approveItem(it.id), it.id, "Tovar tasdiqlandi.")
                          }
                        >
                          <CheckIcon aria-hidden="true" />
                          Tasdiqlash
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          loading={busy}
                          disabled={it.status === "cancelled"}
                          onClick={() =>
                            runAction(() => rejectItem(it.id), it.id, "Tovar rad etildi.")
                          }
                        >
                          <XIcon aria-hidden="true" />
                          Rad etish
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

export { AdminItemsTable }
