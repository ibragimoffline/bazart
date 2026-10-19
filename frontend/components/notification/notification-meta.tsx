import {
  BellIcon,
  ClockAlertIcon,
  HandCoinsIcon,
  HandshakeIcon,
  MessageSquareReplyIcon,
  TagIcon,
  XCircleIcon,
  GavelIcon,
  PackageCheckIcon,
  ShieldAlertIcon,
  TrendingDownIcon,
  TrophyIcon,
  WalletIcon,
  type LucideIcon,
} from "lucide-react"

import type { NotificationType } from "@/lib/api/engagement"

/**
 * Bildirishnoma turining UI ko'rinishi — o'zbekcha yorliq va lucide ikonka.
 * Palitra semantik tokenlar orqali (hardcode rang yo'q).
 */
type NotificationMeta = {
  label: string
  Icon: LucideIcon
  /** Ikonka rang tokeni (semantik). */
  tone: string
}

const META: Record<NotificationType, NotificationMeta> = {
  outbid: { label: "Sizni ortda qoldirishdi", Icon: TrendingDownIcon, tone: "text-warning" },
  won: { label: "Auksionda gʻalaba", Icon: TrophyIcon, tone: "text-success" },
  sold: { label: "Mahsulotingiz sotildi", Icon: GavelIcon, tone: "text-success" },
  payment: { label: "Toʻlov holati", Icon: WalletIcon, tone: "text-primary" },
  handover: { label: "Topshirish", Icon: PackageCheckIcon, tone: "text-primary" },
  dispute: { label: "Nizo", Icon: ShieldAlertIcon, tone: "text-destructive" },
  second_chance: { label: "Ikkinchi imkoniyat", Icon: HandCoinsIcon, tone: "text-primary" },
  ending_soon: { label: "Tugashiga oz qoldi", Icon: ClockAlertIcon, tone: "text-warning" },
  offer_received: { label: "Yangi taklif", Icon: TagIcon, tone: "text-primary" },
  offer_countered: { label: "Qarshi taklif", Icon: MessageSquareReplyIcon, tone: "text-warning" },
  offer_accepted: { label: "Bitim tuzildi", Icon: HandshakeIcon, tone: "text-success" },
  offer_closed: { label: "Taklif yopildi", Icon: XCircleIcon, tone: "text-muted-foreground" },
  dutch_started: { label: "Narx pasaymoqda", Icon: TrendingDownIcon, tone: "text-primary" },
  price_dropped: { label: "Narx tushdi", Icon: TrendingDownIcon, tone: "text-success" },
}

const FALLBACK: NotificationMeta = {
  label: "Bildirishnoma",
  Icon: BellIcon,
  tone: "text-muted-foreground",
}

export function notificationMeta(type: NotificationType): NotificationMeta {
  return META[type] ?? FALLBACK
}

const dateFormatter = new Intl.DateTimeFormat("uz-UZ", {
  day: "numeric",
  month: "long",
  hour: "2-digit",
  minute: "2-digit",
})

/** Absolyut sana — "now" talab qilmaydi (render vaqtida xavfsiz). */
export function formatAbsolute(iso: string): string {
  const t = Date.parse(iso)
  if (!Number.isFinite(t)) return ""
  return dateFormatter.format(new Date(t))
}

/**
 * Nisbiy sana ("5 daqiqa oldin"). `nowMs` — chaqiruvchidan (effektda
 * o'rnatilgan holat), shu bilan render ichida Date.now ishlatilmaydi.
 */
export function formatRelative(iso: string, nowMs: number): string {
  const t = Date.parse(iso)
  if (!Number.isFinite(t)) return ""
  const diffSec = Math.round((nowMs - t) / 1000)
  if (diffSec < 45) return "hozirgina"
  const mins = Math.round(diffSec / 60)
  if (mins < 60) return `${mins} daqiqa oldin`
  const hours = Math.round(mins / 60)
  if (hours < 24) return `${hours} soat oldin`
  const days = Math.round(hours / 24)
  if (days < 30) return `${days} kun oldin`
  return formatAbsolute(iso)
}
