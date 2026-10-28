"use client"

import * as React from "react"
import { SearchIcon, BanIcon, CheckIcon, ShieldAlertIcon } from "lucide-react"
import { toast } from "sonner"

import type { User, UserRole } from "@/lib/api/types"
import { ApiError } from "@/lib/api/client"
import {
  listAdminUsers,
  blockUser,
  unblockUser,
  changeUserRole,
} from "@/lib/api/admin"
import { useAuthStore } from "@/lib/store/auth"
import { ROLE_LABEL, ROLE_VARIANT, formatDateTime } from "@/components/admin/labels"
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
import { FraudSignalsDialog } from "@/components/admin/fraud-signals-dialog"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"

const ROLES: UserRole[] = ["user", "seller", "admin", "superadmin"]

const selectClass =
  "h-8 rounded-md border border-input bg-transparent px-2.5 text-sm outline-none transition-colors focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:opacity-50"

function AdminUsersTable() {
  const actor = useAuthStore((s) => s.user)
  const isSuperadmin = actor?.role === "superadmin"

  const [search, setSearch] = React.useState("")
  const [query, setQuery] = React.useState("")
  const [roleFilter, setRoleFilter] = React.useState<UserRole | "">("")
  const [activeFilter, setActiveFilter] = React.useState<"" | "active" | "blocked">("")
  const [busyId, setBusyId] = React.useState<number | null>(null)
  const [signalsUser, setSignalsUser] = React.useState<User | null>(null)

  const { data, setData, loading, error, reload } = useAdminList<User[]>(
    () =>
      listAdminUsers({
        search: query || undefined,
        role: roleFilter || undefined,
        is_active: activeFilter === "" ? undefined : activeFilter === "active",
      }),
    [query, roleFilter, activeFilter]
  )

  const rows = data ?? []

  const submitSearch = (e: React.FormEvent) => {
    e.preventDefault()
    setQuery(search.trim())
  }

  const patchRow = (updated: User) =>
    setData((prev) => (prev ? prev.map((u) => (u.id === updated.id ? updated : u)) : prev))

  const runAction = async (fn: () => Promise<User>, id: number, ok: string) => {
    setBusyId(id)
    try {
      patchRow(await fn())
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
            placeholder="Email yoki ism bo'yicha qidirish"
            aria-label="Foydalanuvchi qidirish"
            className="h-8 pl-8"
          />
        </div>
        <select
          value={roleFilter}
          onChange={(e) => setRoleFilter(e.target.value as UserRole | "")}
          aria-label="Rol bo'yicha filtr"
          className={selectClass}
        >
          <option value="">Barcha rollar</option>
          {ROLES.map((r) => (
            <option key={r} value={r}>
              {ROLE_LABEL[r]}
            </option>
          ))}
        </select>
        <select
          value={activeFilter}
          onChange={(e) => setActiveFilter(e.target.value as "" | "active" | "blocked")}
          aria-label="Holat bo'yicha filtr"
          className={selectClass}
        >
          <option value="">Barcha holatlar</option>
          <option value="active">Faol</option>
          <option value="blocked">Bloklangan</option>
        </select>
        <Button type="submit" variant="outline" size="sm">
          Qidirish
        </Button>
      </form>

      {error && <ErrorNotice message={error} />}

      {loading ? (
        <TableSkeleton cols={6} />
      ) : (
        <TableFrame>
          <THead>
            <Tr>
              <Th className="w-12">ID</Th>
              <Th>Foydalanuvchi</Th>
              <Th>Rol</Th>
              <Th>Holat</Th>
              <Th>{"Ro'yxatdan o'tgan"}</Th>
              <Th className="text-right">Amallar</Th>
            </Tr>
          </THead>
          <TBody>
            {rows.length === 0 ? (
              <EmptyRow colSpan={6} message="Foydalanuvchi topilmadi." />
            ) : (
              rows.map((u) => {
                const isSelf = u.id === actor?.id
                const busy = busyId === u.id
                // Bloklash himoyasi: superadminni hech kim bloklamaydi; adminni
                // faqat superadmin bloklaydi; o'zini bloklab bo'lmaydi.
                const canBlock =
                  !isSelf &&
                  u.role !== "superadmin" &&
                  (u.role !== "admin" || isSuperadmin)
                return (
                  <Tr key={u.id}>
                    <Td className="tabular-nums text-muted-foreground">{u.id}</Td>
                    <Td>
                      <div className="grid">
                        <span className="font-medium text-foreground">
                          {u.full_name || "—"}
                        </span>
                        <span className="text-xs text-muted-foreground">{u.email}</span>
                      </div>
                    </Td>
                    <Td>
                      {isSuperadmin && !isSelf ? (
                        <select
                          value={u.role}
                          disabled={busy}
                          onChange={(e) =>
                            runAction(
                              () => changeUserRole(u.id, e.target.value as UserRole),
                              u.id,
                              "Rol yangilandi."
                            )
                          }
                          aria-label={`${u.email} roli`}
                          className={selectClass}
                        >
                          {ROLES.map((r) => (
                            <option key={r} value={r}>
                              {ROLE_LABEL[r]}
                            </option>
                          ))}
                        </select>
                      ) : (
                        <Badge variant={ROLE_VARIANT[u.role]}>{ROLE_LABEL[u.role]}</Badge>
                      )}
                    </Td>
                    <Td>
                      {u.is_active ? (
                        <Badge variant="success">Faol</Badge>
                      ) : (
                        <Badge variant="outline">Bloklangan</Badge>
                      )}
                    </Td>
                    <Td className="text-muted-foreground">{formatDateTime(u.created_at)}</Td>
                    <Td>
                      <div className="flex justify-end gap-1.5">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setSignalsUser(u)}
                          aria-label={`${u.email} firibgarlik signallari`}
                        >
                          <ShieldAlertIcon aria-hidden="true" />
                          Signallar
                        </Button>
                        {u.is_active ? (
                          <Button
                            variant="outline"
                            size="sm"
                            loading={busy}
                            disabled={!canBlock}
                            onClick={() =>
                              runAction(() => blockUser(u.id), u.id, "Foydalanuvchi bloklandi.")
                            }
                          >
                            <BanIcon aria-hidden="true" />
                            Bloklash
                          </Button>
                        ) : (
                          <Button
                            variant="outline"
                            size="sm"
                            loading={busy}
                            onClick={() =>
                              runAction(
                                () => unblockUser(u.id),
                                u.id,
                                "Foydalanuvchi blokdan chiqarildi."
                              )
                            }
                          >
                            <CheckIcon aria-hidden="true" />
                            Blokni ochish
                          </Button>
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

      {!isSuperadmin && (
        <p className="mt-3 text-xs text-muted-foreground">
          Rol berish va adminlarni boshqarish faqat superadmin huquqi bilan mumkin.
        </p>
      )}

      <div className="mt-4">
        <Button variant="ghost" size="sm" onClick={reload}>
          Yangilash
        </Button>
      </div>

      <FraudSignalsDialog user={signalsUser} onClose={() => setSignalsUser(null)} />
    </div>
  )
}

export { AdminUsersTable }
