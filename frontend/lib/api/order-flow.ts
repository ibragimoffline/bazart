/**
 * Buyurtma oqimi uchun API funksiyalari (Faza E oʻtish davri).
 *
 * Bazart toʻlovda ishtirok etmaydi: escrow, topshirish kodi va nizo olib tashlangan.
 * Kelishuv: sotuvchi "Sotildi" belgilaydi, xaridor tasdiqlaydi, istalgan tomon sabab bilan
 * bekor qiladi (docs/DEALS.md). Holat oʻtishlari serverda (app/services/deal_state.py).
 */

import { apiFetch } from "@/lib/api/client";
import type { DealCancelReason, Order } from "@/lib/api/types";

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

/** POST /deals/{id}/complete — sotuvchi: "Sotildi". */
export function markDealSold(id: number): Promise<Order> {
  return apiFetch<Order>(`/deals/${id}/complete`, { method: "POST" });
}

/** POST /deals/{id}/confirm — xaridor: "Tasdiqlayman". */
export function confirmDeal(id: number): Promise<Order> {
  return apiFetch<Order>(`/deals/${id}/confirm`, { method: "POST" });
}

/**
 * POST /deals/{id}/cancel — istalgan tomon, sabab bilan. "no_response" faqat 48 soatlik
 * bogʻlanish oynasidan keyin (aks holda 409). Taklif kelishuvida donalar zaxiraga qaytadi.
 */
export function cancelDeal(id: number, reason: DealCancelReason): Promise<Order> {
  return apiFetch<Order>(`/deals/${id}/cancel`, { method: "POST", body: { reason } });
}
