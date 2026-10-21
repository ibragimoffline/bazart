/**
 * Progressiv telefon tasdig'i: server amalni 403 `phone_verification_required` bilan
 * to'xtatsa, apiFetch tasdiqlash oynasini ochadi va tasdiqlangach so'rovni BIR MARTA
 * takrorlaydi. Yopilsa yoki handler bo'lmasa — xato odatdagidek.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  })
}

const gated = () => json(403, { detail: "phone_verification_required" })

let fetchMock: ReturnType<typeof vi.fn>

async function client() {
  vi.resetModules()
  return import("@/lib/api/client")
}

beforeEach(() => {
  localStorage.clear()
  fetchMock = vi.fn()
  vi.stubGlobal("fetch", fetchMock)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe("phone verification gate", () => {
  it("tasdiqlangach asl so'rovni bir marta takrorlaydi", async () => {
    fetchMock.mockResolvedValueOnce(gated()).mockResolvedValueOnce(json(201, { id: 7 }))
    const { apiFetch, setPhoneVerificationHandler } = await client()
    const handler = vi.fn().mockResolvedValue(true)
    setPhoneVerificationHandler(handler)

    const result = await apiFetch<{ id: number }>("/items/3/offers", {
      body: { quantity: 1, unit_price: "320000000" },
      auth: false,
    })

    expect(result).toEqual({ id: 7 })
    expect(handler).toHaveBeenCalledTimes(1)
    expect(fetchMock).toHaveBeenCalledTimes(2)
    const [, second] = fetchMock.mock.calls
    expect(second[1].body).toBe(JSON.stringify({ quantity: 1, unit_price: "320000000" }))
  })

  it("oyna yopilsa — 403 xatosi qaytadi, takror yo'q", async () => {
    fetchMock.mockResolvedValue(gated())
    const { apiFetch, setPhoneVerificationHandler } = await client()
    setPhoneVerificationHandler(vi.fn().mockResolvedValue(false))

    await expect(apiFetch("/bids/1", { body: { amount: "1100" }, auth: false })).rejects.toMatchObject(
      { status: 403, code: "phone_verification_required" }
    )
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it("takror ham 403 bo'lsa — cheksiz aylanmaydi", async () => {
    fetchMock.mockResolvedValue(gated())
    const { apiFetch, setPhoneVerificationHandler } = await client()
    const handler = vi.fn().mockResolvedValue(true)
    setPhoneVerificationHandler(handler)

    await expect(apiFetch("/bids/1", { body: { amount: "1100" }, auth: false })).rejects.toMatchObject(
      { status: 403 }
    )
    expect(handler).toHaveBeenCalledTimes(1)
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it("boshqa 403 lar oynani ochmaydi", async () => {
    fetchMock.mockResolvedValue(json(403, { detail: "Not enough permissions" }))
    const { apiFetch, setPhoneVerificationHandler } = await client()
    const handler = vi.fn().mockResolvedValue(true)
    setPhoneVerificationHandler(handler)

    await expect(apiFetch("/admin/users", { auth: false })).rejects.toMatchObject({ status: 403 })
    expect(handler).not.toHaveBeenCalled()
  })

  it("handler ro'yxatdan chiqarilgach — oyna ochilmaydi", async () => {
    fetchMock.mockResolvedValue(gated())
    const { apiFetch, setPhoneVerificationHandler } = await client()
    const handler = vi.fn().mockResolvedValue(true)
    setPhoneVerificationHandler(handler)()

    await expect(apiFetch("/bids/1", { body: {}, auth: false })).rejects.toMatchObject({ status: 403 })
    expect(handler).not.toHaveBeenCalled()
  })

  it("server xabar kodlari o'zbekcha matnga aylanadi", async () => {
    fetchMock.mockResolvedValue(json(409, { detail: "phone_taken" }))
    const { apiFetch } = await client()
    await expect(apiFetch("/auth/otp/verify", { body: {}, auth: false })).rejects.toMatchObject({
      code: "phone_taken",
      detail: "Bu raqam boshqa akkauntda tasdiqlangan.",
    })
  })
})
