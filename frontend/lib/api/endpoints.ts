import { API_BASE, apiFetch } from "@/lib/api/client";
import { getAccessToken } from "@/lib/api/token";
import type {
  AuthToken,
  User,
  Category,
  Item,
  ItemStatus,
  ListingType,
  Auction,
  AuctionStatus,
  Bid,
  Order,
  Lot,
} from "@/lib/api/types";

// --- Auth --------------------------------------------------------------
export function register(data: {
  email: string;
  password: string;
  full_name?: string;
}): Promise<User> {
  return apiFetch<User>("/auth/register", { body: data, auth: false });
}

export function login(email: string, password: string): Promise<AuthToken> {
  const form = new URLSearchParams();
  form.set("username", email);
  form.set("password", password);
  return apiFetch<AuthToken>("/auth/login", { body: form, auth: false, withCookies: true });
}

/** Google Identity Services bergan ID token (`credential`) bilan kirish/ro'yxatdan o'tish. */
export function googleLogin(credential: string): Promise<AuthToken> {
  return apiFetch<AuthToken>("/auth/google", {
    body: { credential },
    auth: false,
    withCookies: true,
  });
}

export function me(): Promise<User> {
  return apiFetch<User>("/auth/me");
}

/**
 * Server sessiyasini yopadi: refresh cookie (HttpOnly) va joriy access token bekor bo'ladi.
 * Access token eskirgan bo'lsa ham ishlaydi — shuning uchun refresh/qayta urinishsiz.
 */
export async function logout(): Promise<void> {
  const token = getAccessToken();
  await fetch(`${API_BASE}/auth/logout`, {
    method: "POST",
    credentials: "include",
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  });
}

// --- Categories --------------------------------------------------------
export function listCategories(): Promise<Category[]> {
  return apiFetch<Category[]>("/categories", { auth: false });
}

// --- Items -------------------------------------------------------------
export function listItems(params: {
  /** Qidiruv matni — backend lotin/kirill translitini o'zi hisobga oladi. */
  q?: string;
  category_id?: number;
  status?: ItemStatus;
  seller_id?: number;
  region_id?: number;
  district_id?: number;
  listing_type?: ListingType;
  limit?: number;
} = {}): Promise<Item[]> {
  const q = new URLSearchParams();
  if (params.q?.trim()) q.set("q", params.q.trim());
  if (params.region_id != null) q.set("region_id", String(params.region_id));
  if (params.district_id != null) q.set("district_id", String(params.district_id));
  if (params.category_id != null) q.set("category_id", String(params.category_id));
  if (params.status) q.set("status", params.status);
  if (params.seller_id != null) q.set("seller_id", String(params.seller_id));
  if (params.listing_type) q.set("listing_type", params.listing_type);
  q.set("limit", String(params.limit ?? 100));
  return apiFetch<Item[]>(`/items?${q.toString()}`, { auth: false });
}

export function getItem(id: number): Promise<Item> {
  return apiFetch<Item>(`/items/${id}`, { auth: false });
}

// --- Auctions ----------------------------------------------------------
export function listAuctions(
  status: AuctionStatus = "active",
  limit = 100
): Promise<Auction[]> {
  return apiFetch<Auction[]>(`/auctions?status=${status}&limit=${limit}`, {
    auth: false,
  });
}

export function getAuction(id: number): Promise<Auction> {
  return apiFetch<Auction>(`/auctions/${id}`, { auth: false });
}

/** Taklif berish. amount/max — TIYIN (string). max ixtiyoriy (proxy bidding). */
export function placeBid(
  auctionId: number,
  amount: string,
  maxAmount?: string
): Promise<Bid> {
  return apiFetch<Bid>(`/auctions/${auctionId}/bids`, {
    body: { amount, ...(maxAmount ? { max_amount: maxAmount } : {}) },
  });
}

/** Ochiq bid tarixi (yangi -> eski). Ism maskalangan, proxy max hech qachon kelmaydi. */
export function listAuctionBids(auctionId: number, limit = 50): Promise<Bid[]> {
  return apiFetch<Bid[]>(`/auctions/${auctionId}/bids?limit=${limit}`, { auth: false });
}

/**
 * O'z taklifini qaytarib olish. Server rad etadi (409): joriy yetakchi bo'lsangiz,
 * auksion tugashiga 2 daqiqadan kam qolgan bo'lsa yoki taklif allaqachon bekor bo'lsa.
 */
export function retractBid(bidId: number): Promise<Bid> {
  return apiFetch<Bid>(`/bids/${bidId}/retract`, { method: "POST" });
}

/**
 * Lotni "hoziroq sotib olish" narxida sotib olish. Zaxira narx bo'lsa — takliflar unga
 * yetguncha, zaxirasiz — birinchi taklifgacha ochiq; aks holda server 409 qaytaradi.
 */
export function buyNow(auctionId: number): Promise<Auction> {
  return apiFetch<Auction>(`/auctions/${auctionId}/buy-now`, { method: "POST" });
}

/** Sotuvchi: rezervga yetmagan auksionni eng yuqori taklifga sotish (24 soat ichida). */
export function acceptSecondChance(auctionId: number): Promise<Auction> {
  return apiFetch<Auction>(`/auctions/${auctionId}/second-chance/accept`, { method: "POST" });
}

// --- Orders ------------------------------------------------------------
export function buyerOrders(): Promise<Order[]> {
  return apiFetch<Order[]>("/deals/buyer");
}

// --- Lots (auksion + item join) ---------------------------------------
// Backend'da birlashtirilgan "lot" endpointi yo'q — client tomonda birlashtiramiz.

/** Bitta lot: auksion id bo'yicha auksion + uning tovarini olib keladi. */
export async function getLot(auctionId: number): Promise<Lot> {
  const auction = await getAuction(auctionId);
  const item = await getItem(auction.item_id);
  return { auction, item };
}

/** Aktiv lotlar ro'yxati: aktiv auksionlar + har biriga tovar (parallel). */
export async function listLots(limit = 100): Promise<Lot[]> {
  const auctions = await listAuctions("active", limit);
  const items = await Promise.all(
    auctions.map((a) => getItem(a.item_id).catch(() => null))
  );
  return auctions
    .map((auction, i) => ({ auction, item: items[i] }))
    .filter((l): l is Lot => l.item !== null);
}
