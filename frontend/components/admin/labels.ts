/**
 * Admin panel uchun o'zbekcha yorliqlar va badge variantlari — bir joyda,
 * jadvallar bo'ylab takrorlanmaydi.
 */
import type {
  AuctionStatus,
  BidStatus,
  ItemStatus,
  OrderStatus,
  UserRole,
} from "@/lib/api/types";
import type { ComplaintStatus, ComplaintTargetType } from "@/lib/api/complaints";

export type BadgeVariant =
  | "default"
  | "secondary"
  | "success"
  | "warning"
  | "sale"
  | "neutral"
  | "outline";

export const ROLE_LABEL: Record<UserRole, string> = {
  user: "Foydalanuvchi",
  seller: "Sotuvchi",
  admin: "Admin",
  superadmin: "Superadmin",
};

export const ROLE_VARIANT: Record<UserRole, BadgeVariant> = {
  user: "outline",
  seller: "secondary",
  admin: "warning",
  superadmin: "default",
};

export const ITEM_STATUS_LABEL: Record<ItemStatus, string> = {
  draft: "Qoralama",
  scheduled: "Rejalashtirilgan",
  pending: "Kutilmoqda",
  active: "Faol",
  sold: "Sotilgan",
  cancelled: "Bekor qilingan",
  expired: "Muddati tugagan",
};

export const ITEM_STATUS_VARIANT: Record<ItemStatus, BadgeVariant> = {
  draft: "secondary",
  scheduled: "secondary",
  pending: "warning",
  active: "success",
  sold: "neutral",
  cancelled: "outline",
  expired: "outline",
};

export const AUCTION_STATUS_LABEL: Record<AuctionStatus, string> = {
  scheduled: "Rejalashtirilgan",
  active: "Faol",
  ended: "Yakunlangan",
  cancelled: "Bekor qilingan",
  reserve_not_met: "Rezerv yetmadi",
};

export const AUCTION_STATUS_VARIANT: Record<AuctionStatus, BadgeVariant> = {
  scheduled: "secondary",
  active: "success",
  ended: "neutral",
  cancelled: "outline",
  reserve_not_met: "warning",
};

export const ORDER_STATUS_LABEL: Record<OrderStatus, string> = {
  agreed: "Kelishildi",
  completed: "Yakunlangan",
  cancelled: "Bekor qilingan",
};

export const ORDER_STATUS_VARIANT: Record<OrderStatus, BadgeVariant> = {
  agreed: "warning",
  completed: "neutral",
  cancelled: "outline",
};

export const BID_STATUS_LABEL: Record<BidStatus, string> = {
  valid: "Amal qiladi",
  outbid: "Ortda qoldi",
  cancelled: "Bekor qilingan",
  retracted: "Qaytarib olingan",
  invalidated: "Admin bekor qilgan",
};

export const BID_STATUS_VARIANT: Record<BidStatus, BadgeVariant> = {
  valid: "success",
  outbid: "secondary",
  cancelled: "outline",
  retracted: "outline",
  invalidated: "sale",
};

export const COMPLAINT_STATUS_LABEL: Record<ComplaintStatus, string> = {
  open: "Ochiq",
  reviewing: "Koʻrib chiqilmoqda",
  resolved: "Hal qilindi",
  rejected: "Rad etildi",
};

export const COMPLAINT_STATUS_VARIANT: Record<ComplaintStatus, BadgeVariant> = {
  open: "warning",
  reviewing: "secondary",
  resolved: "success",
  rejected: "outline",
};

export const COMPLAINT_TARGET_LABEL: Record<ComplaintTargetType, string> = {
  item: "Tovar",
  user: "Foydalanuvchi",
  auction: "Auksion",
  message: "Xabar",
  order: "Buyurtma",
};

/** ISO vaqtni qisqa uz-UZ formatga: "21.07.2026, 14:30". */
export function formatDateTime(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat("uz-UZ", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}
