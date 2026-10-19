/**
 * Admin API — faqat admin/superadmin rollari uchun (`/api/v1/admin/*`).
 * Rol berish (changeUserRole) backend'da FAQAT superadminga ochiq — oddiy admin
 * 403 oladi. UI ham shu holatni hurmat qiladi (tugma faqat superadminga).
 */
import { apiFetch } from "@/lib/api/client";
import type {
  AdminStats,
  Auction,
  AuctionStatus,
  Bid,
  Item,
  ItemStatus,
  Order,
  OrderStatus,
  User,
  UserRole,
} from "@/lib/api/types";

/** Bo'sh/undefined qiymatlarni tashlab, query string quradi ("" yoki "?a=b"). */
function qs(params: Record<string, string | number | boolean | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") search.set(key, String(value));
  }
  const text = search.toString();
  return text ? `?${text}` : "";
}

// --- Foydalanuvchilar --------------------------------------------------------

export interface AdminUserFilter {
  search?: string;
  role?: UserRole;
  is_active?: boolean;
  skip?: number;
  limit?: number;
}

export function listAdminUsers(filter: AdminUserFilter = {}): Promise<User[]> {
  return apiFetch<User[]>(`/admin/users${qs({ ...filter })}`);
}

export function blockUser(userId: number): Promise<User> {
  return apiFetch<User>(`/admin/users/${userId}/block`, { method: "POST" });
}

export function unblockUser(userId: number): Promise<User> {
  return apiFetch<User>(`/admin/users/${userId}/unblock`, { method: "POST" });
}

/** Rol berish — faqat superadmin (backend 403 bilan himoyalaydi). */
export function changeUserRole(userId: number, role: UserRole): Promise<User> {
  return apiFetch<User>(`/admin/users/${userId}/role`, {
    method: "PATCH",
    body: { role },
  });
}

// --- Tovarlar (moderatsiya) --------------------------------------------------

export interface AdminItemFilter {
  search?: string;
  status?: ItemStatus;
  seller_id?: number;
  category_id?: number;
  skip?: number;
  limit?: number;
}

export function listAdminItems(filter: AdminItemFilter = {}): Promise<Item[]> {
  return apiFetch<Item[]>(`/admin/items${qs({ ...filter })}`);
}

export function approveItem(itemId: number): Promise<Item> {
  return apiFetch<Item>(`/admin/items/${itemId}/approve`, { method: "POST" });
}

export function rejectItem(itemId: number): Promise<Item> {
  return apiFetch<Item>(`/admin/items/${itemId}/reject`, { method: "POST" });
}

// --- Auksionlar --------------------------------------------------------------

export interface AdminAuctionFilter {
  status?: AuctionStatus;
  seller_id?: number;
  item_id?: number;
  skip?: number;
  limit?: number;
}

export function listAdminAuctions(filter: AdminAuctionFilter = {}): Promise<Auction[]> {
  return apiFetch<Auction[]>(`/admin/auctions${qs({ ...filter })}`);
}

export function cancelAuction(auctionId: number): Promise<Auction> {
  return apiFetch<Auction>(`/admin/auctions/${auctionId}/cancel`, { method: "POST" });
}

// --- Bidlar ------------------------------------------------------------------

export interface AdminBidFilter {
  auction_id?: number;
  bidder_id?: number;
  skip?: number;
  limit?: number;
}

export function listAdminBids(filter: AdminBidFilter = {}): Promise<Bid[]> {
  return apiFetch<Bid[]>(`/admin/bids${qs({ ...filter })}`);
}

// --- Buyurtmalar -------------------------------------------------------------

export interface AdminOrderFilter {
  status?: OrderStatus;
  buyer_id?: number;
  seller_id?: number;
  skip?: number;
  limit?: number;
}

export function listAdminOrders(filter: AdminOrderFilter = {}): Promise<Order[]> {
  return apiFetch<Order[]>(`/admin/deals${qs({ ...filter })}`);
}

// --- Statistika --------------------------------------------------------------

export function adminStatistics(): Promise<AdminStats> {
  return apiFetch<AdminStats>("/admin/statistics");
}

// --- Takliflarni bekor qilish va firibgarlik signallari ---------------------

/** Admin bidni bekor qiladi (shill/firibgarlik). Sabab majburiy — audit izi. */
export function invalidateBid(bidId: number, reason: string): Promise<Bid> {
  return apiFetch<Bid>(`/bids/${bidId}/invalidate`, { body: { reason } });
}

/** FraudSignals sxemasi — signal hukm emas, qo'lda tekshiruvga yo'naltiradi. */
export interface FraudSignals {
  user_id: number;
  shared_device_user_ids: number[];
  shared_ip_user_ids: number[];
  self_auction_ip_overlap: number;
  bid_count: number;
  distinct_auctions: number;
  rapid_bid_max_per_10s: number;
  risk_flags: string[];
}

export function fraudSignals(userId: number): Promise<FraudSignals> {
  return apiFetch<FraudSignals>(`/fraud/signals/${userId}`);
}
