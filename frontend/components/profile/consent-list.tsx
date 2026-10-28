"use client"

import * as React from "react"
import { FileCheckIcon } from "lucide-react"

import { listMyConsents, type ConsentDocumentType, type LegalConsent } from "@/lib/api/legal"
import { Skeleton } from "@/components/ui/skeleton"

const DOCUMENT_LABEL: Record<ConsentDocumentType, string> = {
  terms: "Foydalanuvchi kelishuvi",
  privacy: "Maxfiylik siyosati",
  auction_rules: "Auksion qoidalari",
  public_offer: "Ommaviy oferta",
}

const dateFormatter = new Intl.DateTimeFormat("uz-UZ", {
  day: "numeric",
  month: "long",
  year: "numeric",
  timeZone: "Asia/Tashkent",
})

function formatDate(iso: string): string {
  const t = Date.parse(iso)
  return Number.isFinite(t) ? dateFormatter.format(new Date(t)) : ""
}

/** Foydalanuvchi qabul qilgan huquqiy hujjatlar (faqat o'qish uchun). */
function ConsentList() {
  const [consents, setConsents] = React.useState<LegalConsent[] | null>(null)
  const [failed, setFailed] = React.useState(false)

  React.useEffect(() => {
    let alive = true
    listMyConsents()
      .then((data) => {
        if (alive) setConsents(data)
      })
      .catch(() => {
        if (alive) setFailed(true)
      })
    return () => {
      alive = false
    }
  }, [])

  return (
    <section className="grid gap-3 rounded-lg border border-border bg-card p-5">
      <h2 className="text-base font-semibold text-foreground">Qabul qilingan hujjatlar</h2>

      {failed ? (
        <p className="text-sm text-muted-foreground">Roʻyxatni yuklab boʻlmadi.</p>
      ) : consents === null ? (
        <div className="grid gap-2">
          <Skeleton className="h-5 w-2/3" />
          <Skeleton className="h-5 w-1/2" />
        </div>
      ) : consents.length === 0 ? (
        <p className="text-sm text-muted-foreground">Hali hech qanday hujjat qabul qilinmagan.</p>
      ) : (
        <ul className="grid gap-2">
          {consents.map((c) => (
            <li key={c.id} className="flex items-start gap-2 text-sm">
              <FileCheckIcon
                className="mt-0.5 size-4 shrink-0 text-muted-foreground"
                aria-hidden="true"
              />
              <div className="min-w-0">
                <p className="text-foreground">
                  {DOCUMENT_LABEL[c.document_type] ?? c.document_type}
                  <span className="text-muted-foreground"> · versiya {c.version}</span>
                </p>
                <time dateTime={c.accepted_at} className="text-xs text-muted-foreground">
                  {formatDate(c.accepted_at)}
                </time>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

export { ConsentList }
