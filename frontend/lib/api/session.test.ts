/**
 * Jim sessiya yangilash: 401 -> bitta refresh -> bitta qayta urinish; parallel so'rovlar
 * bitta refresh'ni kutadi; tablar Web Lock bilan navbatlashadi; faqat refresh 401
 * sessiyani tugatadi — tarmoq, 500 va 403 foydalanuvchini chiqarmaydi.
 *
 * Soxta server refresh tokenni har safar almashtiradi va eskisini rad etadi (grace'siz) —
 * ya'ni ikkita refresh bir xil cookie bilan ketsa, sessiya o'ladi. Testlar shunga
 * qaramay sessiya saqlanishini ko'rsatadi.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const API = "http://localhost:8000/api/v1"
const HINT_KEY = "bazart-session"
const LEGACY_KEY = "bazart-auth"

type Client = typeof import("@/lib/api/client")
type Token = typeof import("@/lib/api/token")

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  })
}

/** Rotation qiluvchi soxta backend. Cookie — barcha "tab"lar uchun umumiy (brauzer kabi). */
function fakeServer() {
  const state = {
    cookie: "r1",
    version: 1,
    revoked: false,
    refreshCalls: 0,
    refreshBodies: [] as (string | null)[],
    validAccess: new Set<string>(),
    calls: [] as { path: string; auth: string | null; credentials?: RequestCredentials }[],
    /** path -> majburiy javob (masalan 500, 403 yoki tarmoq xatosi). */
    override: new Map<string, () => Response | Promise<Response>>(),
  }

  const fetchMock = vi.fn(async (input: RequestInfo | URL, init: RequestInit = {}) => {
    const path = String(input).replace(API, "")
    const auth = new Headers(init.headers).get("Authorization")
    state.calls.push({ path, auth, credentials: init.credentials })

    const forced = state.override.get(path)
    if (forced) return forced()

    if (path === "/auth/refresh") {
      state.refreshCalls += 1
      state.refreshBodies.push(typeof init.body === "string" ? init.body : null)
      const sent = state.cookie
      await new Promise((r) => setTimeout(r, 5)) // boshqa so'rovlar aralashsin
      if (state.revoked || sent !== state.cookie) {
        state.revoked = true
        return json(401, { detail: "Invalid refresh token" })
      }
      state.version += 1
      state.cookie = `r${state.version}`
      const access = `a${state.version}`
      state.validAccess.add(access)
      return json(200, { access_token: access, token_type: "bearer", expires_in: 1800 })
    }
    if (path === "/auth/logout") return json(200, { message: "Logged out" })

    const token = auth?.replace("Bearer ", "") ?? ""
    if (!state.validAccess.has(token)) return json(401, { detail: "Could not validate credentials" })
    if (path === "/auth/me") return json(200, { id: 7, email: "dilnoza@example.com" })
    return json(200, { ok: true, path })
  })

  return { state, fetchMock }
}

function installWebLocks() {
  let chain: Promise<unknown> = Promise.resolve()
  const locks = {
    request: (_name: string, fn: () => Promise<unknown>) => {
      const run = chain.then(fn)
      chain = run.catch(() => {})
      return run
    },
  }
  Object.defineProperty(navigator, "locks", { value: locks, configurable: true })
}

function removeWebLocks() {
  Object.defineProperty(navigator, "locks", { value: undefined, configurable: true })
}

/** Yangi "tab": modul holati (xotiradagi token, inflight) alohida, localStorage umumiy. */
async function openTab(): Promise<{ client: Client; token: Token }> {
  vi.resetModules()
  const client = await import("@/lib/api/client")
  const token = await import("@/lib/api/token")
  return { client, token }
}

let server: ReturnType<typeof fakeServer>

beforeEach(() => {
  localStorage.clear()
  removeWebLocks()
  server = fakeServer()
  vi.stubGlobal("fetch", server.fetchMock)
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.useRealTimers()
})

/** Kirgan foydalanuvchi: hint bor, access token eskirgan (xotirada bor, lekin server rad etadi). */
function loggedInWithExpiredAccess(token: Token) {
  localStorage.setItem(HINT_KEY, "1")
  token.setAccessToken("a-expired", 1800)
}

describe("apiFetch — jim yangilash", () => {
  it("401 da bitta refresh qiladi va asl so'rovni qayta yuboradi", async () => {
    const { client, token } = await openTab()
    loggedInWithExpiredAccess(token)

    const data = await client.apiFetch<{ path: string }>("/offers/mine")

    expect(data.path).toBe("/offers/mine")
    expect(server.state.refreshCalls).toBe(1)
    const offerCalls = server.state.calls.filter((c) => c.path === "/offers/mine")
    expect(offerCalls.map((c) => c.auth)).toEqual(["Bearer a-expired", "Bearer a2"])
    // Refresh cookie bilan ketadi (HttpOnly — JS ko'rmaydi).
    expect(server.state.calls.find((c) => c.path === "/auth/refresh")?.credentials).toBe("include")
  })

  it("parallel 401'lar faqat BITTA refresh chaqiradi", async () => {
    const { client, token } = await openTab()
    loggedInWithExpiredAccess(token)

    const paths = ["/bids/1", "/offers/mine", "/deals", "/watchlist", "/notifications"]
    const results = await Promise.all(paths.map((p) => client.apiFetch<{ path: string }>(p)))

    expect(results.map((r) => r.path)).toEqual(paths)
    expect(server.state.refreshCalls).toBe(1)
    expect(server.state.revoked).toBe(false)
  })

  it("muddati yaqin access tokenni so'rovdan OLDIN yangilaydi", async () => {
    const { client, token } = await openTab()
    localStorage.setItem(HINT_KEY, "1")
    token.setAccessToken("a-old", 30) // 30 soniya qoldi — 60 soniyalik zaxiradan kam

    await client.apiFetch("/deals")

    expect(server.state.calls.map((c) => c.path)).toEqual(["/auth/refresh", "/deals"])
    expect(server.state.calls[1].auth).toBe("Bearer a2")
  })

  it("qayta urinish ham 401 bo'lsa — cheksiz aylanmaydi", async () => {
    const { client, token } = await openTab()
    loggedInWithExpiredAccess(token)
    server.state.override.set("/admin/stats", () => json(401, { detail: "nope" }))

    await expect(client.apiFetch("/admin/stats")).rejects.toMatchObject({ status: 401 })
    expect(server.state.refreshCalls).toBe(1)
    expect(server.state.calls.filter((c) => c.path === "/admin/stats")).toHaveLength(2)
  })

  it("refresh 401 — sessiya tugaydi, obunachi xabar oladi", async () => {
    const { client, token } = await openTab()
    loggedInWithExpiredAccess(token)
    server.state.revoked = true
    const ended = vi.fn()
    client.onSessionEnded(ended)

    await expect(client.apiFetch("/deals")).rejects.toMatchObject({ status: 401 })
    expect(ended).toHaveBeenCalledTimes(1)
    expect(localStorage.getItem(HINT_KEY)).toBeNull()
    expect(token.getAccessToken()).toBeNull()
  })
})

describe("vaqtinchalik xatolar sessiyani buzmaydi", () => {
  async function setup() {
    const { client, token } = await openTab()
    localStorage.setItem(HINT_KEY, "1")
    token.setAccessToken("a-valid", 1800)
    server.state.validAccess.add("a-valid")
    const ended = vi.fn()
    client.onSessionEnded(ended)
    return { client, token, ended }
  }

  it("tarmoq xatosi — ApiError(0), chiqarilmaydi", async () => {
    const { client, token, ended } = await setup()
    server.state.override.set("/deals", () => Promise.reject(new TypeError("Failed to fetch")))

    await expect(client.apiFetch("/deals")).rejects.toMatchObject({ status: 0 })
    expect(ended).not.toHaveBeenCalled()
    expect(localStorage.getItem(HINT_KEY)).toBe("1")
    expect(token.getAccessToken()).toBe("a-valid")
  })

  it("500 — xato qaytadi, refresh ham, logout ham yo'q", async () => {
    const { client, ended } = await setup()
    server.state.override.set("/deals", () => json(500, { detail: "Internal Server Error" }))

    await expect(client.apiFetch("/deals")).rejects.toMatchObject({ status: 500 })
    expect(server.state.refreshCalls).toBe(0)
    expect(ended).not.toHaveBeenCalled()
  })

  it("403 — ruxsat yo'q, lekin foydalanuvchi kirgan holda qoladi", async () => {
    const { client, ended } = await setup()
    server.state.override.set("/admin/users", () => json(403, { detail: "Not enough permissions" }))

    await expect(client.apiFetch("/admin/users")).rejects.toMatchObject({ status: 403 })
    expect(server.state.refreshCalls).toBe(0)
    expect(ended).not.toHaveBeenCalled()
    expect(localStorage.getItem(HINT_KEY)).toBe("1")
  })

  it("refresh'ning o'zi tarmoqda yiqilsa — chiqarilmaydi", async () => {
    const { client, token } = await openTab()
    loggedInWithExpiredAccess(token)
    server.state.override.set("/auth/refresh", () => Promise.reject(new TypeError("offline")))
    const ended = vi.fn()
    client.onSessionEnded(ended)

    await expect(client.apiFetch("/deals")).rejects.toMatchObject({ status: 0 })
    expect(ended).not.toHaveBeenCalled()
    expect(localStorage.getItem(HINT_KEY)).toBe("1")
  })

  it("refresh 503 — chiqarilmaydi", async () => {
    const { client, token } = await openTab()
    loggedInWithExpiredAccess(token)
    server.state.override.set("/auth/refresh", () => json(503, { detail: "unavailable" }))
    const ended = vi.fn()
    client.onSessionEnded(ended)

    await expect(client.apiFetch("/deals")).rejects.toMatchObject({ status: 503 })
    expect(ended).not.toHaveBeenCalled()
  })
})

describe("bir nechta tab", () => {
  it("Web Lock bilan ikki tab bir vaqtda yangilasa ham sessiya buzilmaydi", async () => {
    installWebLocks()
    localStorage.setItem(HINT_KEY, "1")
    const tabA = await openTab()
    const tabB = await openTab()
    tabA.token.setAccessToken("a-expired", 1800)
    tabB.token.setAccessToken("a-expired", 1800)

    const [a, b] = await Promise.all([
      tabA.client.apiFetch<{ path: string }>("/bids/1"),
      tabB.client.apiFetch<{ path: string }>("/offers/mine"),
    ])

    expect(a.path).toBe("/bids/1")
    expect(b.path).toBe("/offers/mine")
    expect(server.state.revoked).toBe(false)
    expect(server.state.refreshCalls).toBe(2) // navbat bilan, har biri yangi cookie bilan
  })

  it("boshqa tabda chiqilsa storage hodisasi orqali bilinadi", async () => {
    const { token } = await openTab()
    const listener = vi.fn()
    const unsubscribe = token.onSessionHintChange(listener)

    window.dispatchEvent(new StorageEvent("storage", { key: HINT_KEY, newValue: null }))
    window.dispatchEvent(new StorageEvent("storage", { key: HINT_KEY, newValue: "1" }))
    window.dispatchEvent(new StorageEvent("storage", { key: "boshqa", newValue: "x" }))
    unsubscribe()

    expect(listener.mock.calls).toEqual([[false], [true]])
  })
})

describe("eski localStorage tokenlari", () => {
  it("bir marta body orqali cookie'ga ko'chiriladi va o'chiriladi", async () => {
    localStorage.setItem(LEGACY_KEY, JSON.stringify({ access: "old-a", refresh: "old-r" }))
    const { client, token } = await openTab()

    expect(token.hasSessionHint()).toBe(true)
    expect(await client.refreshSession()).toBe("ok")
    expect(server.state.refreshBodies[0]).toBe(JSON.stringify({ refresh_token: "old-r" }))
    expect(localStorage.getItem(LEGACY_KEY)).toBeNull()
    expect(localStorage.getItem(HINT_KEY)).toBe("1")
  })

  it("ko'chirish tarmoqda yiqilsa — eski token qaytarib qo'yiladi", async () => {
    localStorage.setItem(LEGACY_KEY, JSON.stringify({ access: "old-a", refresh: "old-r" }))
    server.state.override.set("/auth/refresh", () => Promise.reject(new TypeError("offline")))
    const { client } = await openTab()

    await expect(client.refreshSession()).rejects.toMatchObject({ status: 0 })
    expect(JSON.parse(localStorage.getItem(LEGACY_KEY) ?? "{}").refresh).toBe("old-r")
  })
})

describe("auth store — sessiyani tiklash", () => {
  async function openStore() {
    vi.resetModules()
    const { useAuthStore } = await import("@/lib/store/auth")
    return useAuthStore
  }

  it("sahifa yangilanganda / brauzer qayta ochilganda cookie bilan tiklanadi", async () => {
    localStorage.setItem(HINT_KEY, "1") // xotirada token yo'q — yangi sahifa
    const store = await openStore()
    expect(store.getState().status).toBe("idle")

    await store.getState().loadMe()

    expect(store.getState().status).toBe("authenticated")
    expect(store.getState().user?.email).toBe("dilnoza@example.com")
    expect(server.state.calls.map((c) => c.path)).toEqual(["/auth/refresh", "/auth/me"])
  })

  it("sessiya belgisi yo'q mehmon — refresh chaqirilmaydi", async () => {
    const store = await openStore()
    await store.getState().loadMe()
    expect(store.getState().status).toBe("anonymous")
    expect(server.fetchMock).not.toHaveBeenCalled()
  })

  it("tiklash paytida tarmoq yo'q — 'idle' qoladi, keyin o'zi tiklanadi", async () => {
    vi.useFakeTimers()
    localStorage.setItem(HINT_KEY, "1")
    server.state.override.set("/auth/refresh", () => Promise.reject(new TypeError("offline")))
    const store = await openStore()

    await store.getState().loadMe()
    expect(store.getState().status).toBe("idle") // login sahifasiga otilmaydi
    expect(localStorage.getItem(HINT_KEY)).toBe("1")

    server.state.override.delete("/auth/refresh")
    await vi.advanceTimersByTimeAsync(1000)
    await vi.waitFor(() => expect(store.getState().status).toBe("authenticated"))
  })

  it("server sessiyani rad etsa — anonim, qayta kirish kerak", async () => {
    localStorage.setItem(HINT_KEY, "1")
    server.state.revoked = true
    const store = await openStore()

    await store.getState().loadMe()

    expect(store.getState().status).toBe("anonymous")
    expect(localStorage.getItem(HINT_KEY)).toBeNull()
  })

  it("kirgan foydalanuvchi: profilni yangilashda 500 — chiqarilmaydi", async () => {
    localStorage.setItem(HINT_KEY, "1")
    const store = await openStore()
    await store.getState().loadMe()
    server.state.override.set("/auth/me", () => json(500, { detail: "boom" }))

    await store.getState().loadMe()

    expect(store.getState().status).toBe("authenticated")
    expect(store.getState().user?.email).toBe("dilnoza@example.com")
  })

  it("logout — server chaqiriladi (cookie bilan), lokal sessiya tozalanadi", async () => {
    localStorage.setItem(HINT_KEY, "1")
    const store = await openStore()
    await store.getState().loadMe()

    await store.getState().logout()

    const call = server.state.calls.find((c) => c.path === "/auth/logout")
    expect(call?.credentials).toBe("include")
    expect(call?.auth).toBe("Bearer a2")
    expect(store.getState().status).toBe("anonymous")
    expect(localStorage.getItem(HINT_KEY)).toBeNull()
  })
})
