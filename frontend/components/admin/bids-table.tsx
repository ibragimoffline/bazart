"use client"

import * as React from "react"
import Link from "next/link"
import { BanIcon, FilterIcon } from "lucide-react"
import { toast } from "sonner"

import { formatTiyin } from "@/lib/format"
import type { Bid } from "@/lib/api/types"
import { ApiError } from "@/lib/api/client"
import { listAdminBids, invalidateBid } from "@/lib/api/admin"
import {
  BID_STATUS_LABEL,
  BID_STATUS_VARIANT,
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
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogFooter,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog"

const REASON_MAX = 500

const linkClass =
  "rounded-sm font-medium text-primary underline-offset-4 outline-none transition-colors underline decoration-foreground/30 hover:decoration-foreground focus-visible:ring-3 focus-visible:ring-ring/50"

/** Musbat butun son bo'lsa — raqam, aks holda undefined (filtr qo'llanmaydi). */
function parseId(value: string): number | undefined {
  const n = Number(value.trim())
  return Number.isInteger(n) && n > 0 ? n : undefined
}

function InvalidateDialog({
  bid,
  onClose,
  onDone,
}: {
  bid: Bid | null
  onClose: () => void
  onDone: (updated: Bid) => void
}) {
  const [reason, setReason] = React.useState("")
  const [error, setError] = React.useState<string | null>(null)
  const [submitting, setSubmitting] = React.useState(false)

  const close = () => {
    if (submitting) return
    setReason("")
    setError(null)
    onClose()
  }

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!bid) return
    const text = reason.trim()
    if (!text) {
      setError("Bekor qilish sababini yozing.")
      return
    }
    setSubmitting(true)
    setError(null)
    try {
      const updated = await invalidateBid(bid.id, text)
      toast.success(`Taklif #${bid.id} bekor qilindi.`)
      setReason("")
      onDone(updated)
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Taklifni bekor qilib boʻlmadi.")
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Dialog open={bid !== null} onOpenChange={(next) => !next && close()}>
      <DialogContent showCloseButton={!submitting}>
        {bid && (
          <form onSubmit={submit} className="grid gap-4">
            <DialogHeader>
              <DialogTitle>Taklifni bekor qilish</DialogTitle>
              <DialogDescription>
                Taklif #{bid.id} · Auksion #{bid.auction_id} · {formatTiyin(bid.amount)}.
                Joriy narx qolgan amaldagi takliflar boʻyicha qayta hisoblanadi.
              </DialogDescription>
            </DialogHeader>
            <div className="grid gap-2">
              <Label htmlFor={`invalidate-reason-${bid.id}`}>Sabab</Label>
              <Textarea
                id={`invalidate-reason-${bid.id}`}
                value={reason}
                maxLength={REASON_MAX}
                disabled={submitting}
                required
                aria-invalid={error ? true : undefined}
                aria-describedby={`invalidate-hint-${bid.id}`}
                placeholder="Masalan: sotuvchi bilan bir xil qurilmadan qoʻyilgan shill taklif"
                onChange={(e) => {
                  setReason(e.target.value)
                  setError(null)
                }}
              />
              <p
                id={`invalidate-hint-${bid.id}`}
                className="text-xs text-muted-foreground tabular-nums"
              >
                Sabab audit jurnaliga yoziladi. {reason.length}/{REASON_MAX}
              </p>
              {error && (
                <p role="alert" className="text-sm font-medium text-destructive">
                  {error}
                </p>
              )}
            </div>
            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={submitting}
                onClick={close}
              >
                Ortga
              </Button>
              <Button
                type="submit"
                variant="destructive"
                size="sm"
                loading={submitting}
                disabled={!reason.trim()}
              >
                <BanIcon aria-hidden="true" />
                Bekor qilish
              </Button>
            </DialogFooter>
          </form>
        )}
      </DialogContent>
    </Dialog>
  )
}

/** Boshlang'ich filtr URL'dan keladi (masalan, signallar oynasidan `?bidder_id=7`). */
function AdminBidsTable({
  initialAuctionId,
  initialBidderId,
}: {
  initialAuctionId?: number
  initialBidderId?: number
}) {
  const [auctionInput, setAuctionInput] = React.useState(
    initialAuctionId ? String(initialAuctionId) : ""
  )
  const [bidderInput, setBidderInput] = React.useState(
    initialBidderId ? String(initialBidderId) : ""
  )
  const [filter, setFilter] = React.useState<{ auction_id?: number; bidder_id?: number }>({
    auction_id: initialAuctionId,
    bidder_id: initialBidderId,
  })
  const [target, setTarget] = React.useState<Bid | null>(null)

  const { data, loading, error, reload } = useAdminList<Bid[]>(
    () => listAdminBids(filter),
    [filter.auction_id, filter.bidder_id]
  )

  const rows = data ?? []

  const submitFilter = (e: React.FormEvent) => {
    e.preventDefault()
    setFilter({ auction_id: parseId(auctionInput), bidder_id: parseId(bidderInput) })
  }

  const resetFilter = () => {
    setAuctionInput("")
    setBidderInput("")
    setFilter({})
  }

  const hasFilter = filter.auction_id !== undefined || filter.bidder_id !== undefined

  return (
    <div>
      <form
        onSubmit={submitFilter}
        className="mb-4 flex flex-wrap items-end gap-2"
        role="search"
      >
        <div className="grid gap-1">
          <Label htmlFor="bids-auction-id" className="text-xs text-muted-foreground">
            Auksion ID
          </Label>
          <Input
            id="bids-auction-id"
            type="number"
            inputMode="numeric"
            min={1}
            value={auctionInput}
            onChange={(e) => setAuctionInput(e.target.value)}
            placeholder="Masalan: 42"
            className="h-8 w-36"
          />
        </div>
        <div className="grid gap-1">
          <Label htmlFor="bids-bidder-id" className="text-xs text-muted-foreground">
            Ishtirokchi ID
          </Label>
          <Input
            id="bids-bidder-id"
            type="number"
            inputMode="numeric"
            min={1}
            value={bidderInput}
            onChange={(e) => setBidderInput(e.target.value)}
            placeholder="Masalan: 7"
            className="h-8 w-36"
          />
        </div>
        <Button type="submit" variant="outline" size="sm">
          <FilterIcon aria-hidden="true" />
          Filtrlash
        </Button>
        {hasFilter && (
          <Button type="button" variant="ghost" size="sm" onClick={resetFilter}>
            Tozalash
          </Button>
        )}
      </form>

      {error && <ErrorNotice message={error} />}

      {loading ? (
        <TableSkeleton cols={6} />
      ) : (
        <TableFrame>
          <THead>
            <Tr>
              <Th className="w-12">ID</Th>
              <Th>Auksion</Th>
              <Th>Ishtirokchi</Th>
              <Th>Summa</Th>
              <Th>Holat</Th>
              <Th>Vaqt</Th>
              <Th className="text-right">Amallar</Th>
            </Tr>
          </THead>
          <TBody>
            {rows.length === 0 ? (
              <EmptyRow colSpan={7} message="Taklif topilmadi." />
            ) : (
              rows.map((b) => {
                const invalidatable = b.status === "valid" || b.status === "outbid"
                return (
                  <Tr key={b.id}>
                    <Td className="tabular-nums text-muted-foreground">{b.id}</Td>
                    <Td>
                      <Link href={`/lot/${b.auction_id}`} className={linkClass}>
                        Auksion #{b.auction_id}
                      </Link>
                    </Td>
                    <Td>
                      <div className="grid">
                        <span className="font-medium text-foreground">
                          {b.bidder_display || "—"}
                        </span>
                        <span className="text-xs tabular-nums text-muted-foreground">
                          #{b.bidder_id}
                        </span>
                      </div>
                    </Td>
                    <Td className="tabular-nums text-foreground">{formatTiyin(b.amount)}</Td>
                    <Td>
                      <Badge variant={BID_STATUS_VARIANT[b.status]}>
                        {BID_STATUS_LABEL[b.status]}
                      </Badge>
                    </Td>
                    <Td className="text-muted-foreground">{formatDateTime(b.created_at)}</Td>
                    <Td>
                      <div className="flex justify-end">
                        <Button
                          variant="outline"
                          size="sm"
                          disabled={!invalidatable}
                          onClick={() => setTarget(b)}
                        >
                          <BanIcon aria-hidden="true" />
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

      <InvalidateDialog
        bid={target}
        onClose={() => setTarget(null)}
        onDone={() => {
          setTarget(null)
          // Joriy narx va boshqa takliflar holati o'zgargan bo'lishi mumkin — to'liq qayta yuklash.
          reload()
        }}
      />
    </div>
  )
}

export { AdminBidsTable }
