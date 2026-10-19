/**
 * Buyurtma holatlarini oʻzbekcha yorliq va Badge'ga moslaydi. Yagona manba —
 * komponentlarda holat matni takrorlanmaydi.
 */

import type { OrderStatus } from "@/lib/api/types"
import { Badge } from "@/components/ui/badge"

type BadgeVariant =
  | "default"
  | "secondary"
  | "success"
  | "warning"
  | "sale"
  | "neutral"
  | "outline"

const ORDER_LABEL: Record<OrderStatus, string> = {
  pending_payment: "Kelishildi",
  pickup_pending: "Uchrashuv kutilmoqda",
  completed: "Yakunlangan",
  cancelled: "Bekor qilingan",
}

const ORDER_VARIANT: Record<OrderStatus, BadgeVariant> = {
  pending_payment: "warning",
  pickup_pending: "default",
  completed: "success",
  cancelled: "neutral",
}

export function orderStatusLabel(status: OrderStatus): string {
  return ORDER_LABEL[status] ?? status
}

export function OrderStatusBadge({ status }: { status: OrderStatus }) {
  return <Badge variant={ORDER_VARIANT[status] ?? "outline"}>{orderStatusLabel(status)}</Badge>
}
