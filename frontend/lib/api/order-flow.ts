/**
 * Buyurtma oqimi uchun API funksiyalari (Faza E oʻtish davri).
 *
 * Bazart toʻlovda ishtirok etmaydi: escrow, topshirish kodi va nizo olib tashlangan.
 * Sotuvchi buyurtmani oʻzi yakunlaydi yoki bekor qiladi (`PATCH /deals/{id}/status`,
 * ruxsat etilgan oʻtishlar serverda — app/services/order_state.py). E2 da buyurtma
 * kelishuv (deal) bilan almashadi (docs/DEALS.md).
 */

import { apiFetch } from "@/lib/api/client";
import type { Order, OrderStatus } from "@/lib/api/types";

/** GET /deals/buyer — joriy foydalanuvchi xaridor boʻlgan buyurtmalar. */
export function buyerOrders(): Promise<Order[]> {
  return apiFetch<Order[]>("/deals/buyer");
}

/** GET /deals/seller — joriy foydalanuvchi sotuvchi boʻlgan buyurtmalar. */
export function sellerOrders(): Promise<Order[]> {
  return apiFetch<Order[]>("/deals/seller");
}

/** GET /deals/{id} — bitta buyurtma (egalik tekshiruvi server tomonda). */
export function getOrder(id: number): Promise<Order> {
  return apiFetch<Order>(`/deals/${id}`);
}

/**
 * PATCH /deals/{id}/status — sotuvchi (yoki admin) holatni oʻzgartiradi.
 * Taqiqlangan oʻtish 409 qaytaradi; bekor qilinganda donalar zaxiraga qaytadi.
 */
export function updateOrderStatus(id: number, status: OrderStatus): Promise<Order> {
  return apiFetch<Order>(`/deals/${id}/status`, {
    method: "PATCH",
    body: { status },
  });
}
