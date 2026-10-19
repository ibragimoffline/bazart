"use client"

import * as React from "react"
import Link from "next/link"
import { EyeIcon, CheckIcon, XIcon, RotateCcwIcon } from "lucide-react"
import { toast } from "sonner"

import { ApiError } from "@/lib/api/client"
import {
  listComplaints,
  updateComplaintStatus,
  type Complaint,
  type ComplaintStatus,
} from "@/lib/api/complaints"
import {
  COMPLAINT_STATUS_LABEL,
  COMPLAINT_STATUS_VARIANT,
  COMPLAINT_TARGET_LABEL,
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
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogFooter,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog"

const STATUSES: ComplaintStatus[] = ["open", "reviewing", "resolved", "rejected"]

const selectClass =
  "h-8 rounded-lg border border-input bg-transparent px-2.5 text-sm outline-none transition-colors focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:opacity-50"

const linkClass =
  "rounded-sm font-medium text-primary underline-offset-4 outline-none transition-colors underline decoration-foreground/30 hover:decoration-foreground focus-visible:ring-3 focus-visible:ring-ring/50"

/** Frontend'da ochiladigan sahifa bo'lsa — havola, aks holda null. */
function targetHref(c: Complaint): string | null {
  if (c.target_type === "auction") return `/lot/${c.target_id}`
  if (c.target_type === "user") return `/users/${c.target_id}`
  return null
}

/** Yakuniy holatlar — ular qaytarib bo'lmaydigan oqibatga ega, shuning uchun tasdiq so'raladi. */
type TerminalStatus = Extract<ComplaintStatus, "resolved" | "rejected">

const CONFIRM_COPY: Record<TerminalStatus, { title: string; body: string; action: string }> = {
  resolved: {
    title: "Shikoyatni hal qilingan deb belgilash",
    body: "Shikoyat yopiladi va hal qilingan vaqt hamda moderator yoziladi. Davom etasizmi?",
    action: "Hal qilindi",
  },
  rejected: {
    title: "Shikoyatni rad etish",
    body: "Shikoyat asossiz deb yopiladi. Kerak boʻlsa keyin qayta ochish mumkin.",
    action: "Rad etish",
  },
}

function DescriptionCell({ text }: { text: string | null }) {
  if (!text) return <span className="text-muted-foreground">—</span>
  if (text.length <= 60) return <span className="text-foreground">{text}</span>
  // <details> — to'liq matn klaviatura va ekran o'quvchi uchun ham ochiladi.
  return (
    <details className="group max-w-64">
      <summary className="cursor-pointer list-none rounded-sm text-foreground outline-none transition-colors hover:text-primary focus-visible:ring-3 focus-visible:ring-ring/50 [&::-webkit-details-marker]:hidden">
        <span className="line-clamp-2 group-open:hidden">{text}</span>
        <span className="hidden text-xs font-medium text-primary group-open:inline">
          Yopish
        </span>
      </summary>
      <p className="mt-1 text-sm break-words whitespace-pre-wrap text-foreground">{text}</p>
    </details>
  )
}

function AdminComplaintsTable() {
  const [statusFilter, setStatusFilter] = React.useState<ComplaintStatus | "">("open")
  const [busyId, setBusyId] = React.useState<number | null>(null)
  const [confirm, setConfirm] = React.useState<{
    complaint: Complaint
    status: TerminalStatus
  } | null>(null)

  const { data, setData, loading, error, reload } = useAdminList<Complaint[]>(
    () => listComplaints(statusFilter || undefined),
    [statusFilter]
  )

  const rows = data ?? []

  const changeStatus = async (id: number, status: ComplaintStatus, ok: string) => {
    setBusyId(id)
    try {
      const updated = await updateComplaintStatus(id, status)
      // Filtrga endi mos kelmasa — qator ro'yxatdan chiqadi.
      setData((prev) =>
        prev
          ? statusFilter && updated.status !== statusFilter
            ? prev.filter((c) => c.id !== id)
            : prev.map((c) => (c.id === id ? updated : c))
          : prev
      )
      toast.success(ok)
      return true
    } catch (e) {
      toast.error(e instanceof ApiError ? e.detail : "Amal bajarilmadi.")
      return false
    } finally {
      setBusyId(null)
    }
  }

  const confirmBusy = confirm !== null && busyId === confirm.complaint.id

  const runConfirm = async () => {
    if (!confirm) return
    const ok = await changeStatus(
      confirm.complaint.id,
      confirm.status,
      confirm.status === "resolved" ? "Shikoyat hal qilindi." : "Shikoyat rad etildi."
    )
    if (ok) setConfirm(null)
  }

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as ComplaintStatus | "")}
          aria-label="Holat boʻyicha filtr"
          className={selectClass}
        >
          <option value="">Barcha holatlar</option>
          {STATUSES.map((s) => (
            <option key={s} value={s}>
              {COMPLAINT_STATUS_LABEL[s]}
            </option>
          ))}
        </select>
      </div>

      {error && <ErrorNotice message={error} />}

      {loading ? (
        <TableSkeleton cols={7} />
      ) : (
        <TableFrame>
          <THead>
            <Tr>
              <Th className="w-12">ID</Th>
              <Th>Obyekt</Th>
              <Th>Sabab</Th>
              <Th>Tavsif</Th>
              <Th>Yuboruvchi</Th>
              <Th>Sana</Th>
              <Th>Holat</Th>
              <Th className="text-right">Amallar</Th>
            </Tr>
          </THead>
          <TBody>
            {rows.length === 0 ? (
              <EmptyRow colSpan={8} message="Shikoyat topilmadi." />
            ) : (
              rows.map((c) => {
                const busy = busyId === c.id
                const href = targetHref(c)
                const label = `${COMPLAINT_TARGET_LABEL[c.target_type]} #${c.target_id}`
                const terminal = c.status === "resolved" || c.status === "rejected"
                return (
                  <Tr key={c.id}>
                    <Td className="tabular-nums text-muted-foreground">{c.id}</Td>
                    <Td className="whitespace-nowrap">
                      {href ? (
                        <Link href={href} className={linkClass}>
                          {label}
                        </Link>
                      ) : (
                        <span className="text-foreground">{label}</span>
                      )}
                    </Td>
                    <Td className="max-w-48 whitespace-normal text-foreground">{c.reason}</Td>
                    <Td className="whitespace-normal">
                      <DescriptionCell text={c.description} />
                    </Td>
                    <Td className="tabular-nums text-muted-foreground">#{c.reporter_id}</Td>
                    <Td className="text-muted-foreground">{formatDateTime(c.created_at)}</Td>
                    <Td>
                      <Badge variant={COMPLAINT_STATUS_VARIANT[c.status]}>
                        {COMPLAINT_STATUS_LABEL[c.status]}
                      </Badge>
                    </Td>
                    <Td>
                      <div className="flex justify-end gap-1.5">
                        {c.status === "open" && (
                          <Button
                            variant="outline"
                            size="sm"
                            loading={busy}
                            onClick={() =>
                              void changeStatus(c.id, "reviewing", "Shikoyat koʻrib chiqilmoqda.")
                            }
                          >
                            <EyeIcon aria-hidden="true" />
                            Koʻrib chiqish
                          </Button>
                        )}
                        {terminal ? (
                          <Button
                            variant="ghost"
                            size="sm"
                            loading={busy}
                            onClick={() =>
                              void changeStatus(c.id, "reviewing", "Shikoyat qayta ochildi.")
                            }
                          >
                            <RotateCcwIcon aria-hidden="true" />
                            Qayta ochish
                          </Button>
                        ) : (
                          <>
                            <Button
                              variant="outline"
                              size="sm"
                              disabled={busy}
                              onClick={() => setConfirm({ complaint: c, status: "resolved" })}
                            >
                              <CheckIcon aria-hidden="true" />
                              Hal qilish
                            </Button>
                            <Button
                              variant="outline"
                              size="sm"
                              disabled={busy}
                              onClick={() => setConfirm({ complaint: c, status: "rejected" })}
                            >
                              <XIcon aria-hidden="true" />
                              Rad etish
                            </Button>
                          </>
                        )}
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

      <Dialog
        open={confirm !== null}
        onOpenChange={(next) => {
          if (!next && !confirmBusy) setConfirm(null)
        }}
      >
        <DialogContent showCloseButton={!confirmBusy}>
          {confirm && (
            <>
              <DialogHeader>
                <DialogTitle>{CONFIRM_COPY[confirm.status].title}</DialogTitle>
                <DialogDescription>
                  Shikoyat #{confirm.complaint.id}:{" "}
                  {COMPLAINT_TARGET_LABEL[confirm.complaint.target_type]} #
                  {confirm.complaint.target_id} — {confirm.complaint.reason}
                </DialogDescription>
              </DialogHeader>
              <p className="text-sm text-foreground">{CONFIRM_COPY[confirm.status].body}</p>
              <DialogFooter>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={confirmBusy}
                  onClick={() => setConfirm(null)}
                >
                  Bekor qilish
                </Button>
                <Button
                  variant={confirm.status === "rejected" ? "destructive" : "default"}
                  size="sm"
                  loading={confirmBusy}
                  onClick={() => void runConfirm()}
                >
                  {CONFIRM_COPY[confirm.status].action}
                </Button>
              </DialogFooter>
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  )
}

export { AdminComplaintsTable }
