/** GET /features: bayroq qiymati, bitta so'rov (kesh) va xatoda xavfsiz zaxira (o'chiq). */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  })
}

async function freshModule() {
  vi.resetModules()
  return import("@/lib/features")
}

let fetchMock: ReturnType<typeof vi.fn>

beforeEach(() => {
  fetchMock = vi.fn()
  vi.stubGlobal("fetch", fetchMock)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe("loadFeatures", () => {
  it.each([true, false])("serverdagi qiymatni qaytaradi (ascending_auction=%s)", async (on) => {
    fetchMock.mockResolvedValue(json(200, { ascending_auction: on }))
    const { loadFeatures } = await freshModule()
    expect(await loadFeatures()).toEqual({ ascending_auction: on })
    expect(String(fetchMock.mock.calls[0][0])).toMatch(/\/api\/v1\/features$/)
  })

  it("parallel va keyingi chaqiruvlar bitta so'rov bilan", async () => {
    fetchMock.mockResolvedValue(json(200, { ascending_auction: true }))
    const { loadFeatures } = await freshModule()
    await Promise.all([loadFeatures(), loadFeatures(), loadFeatures()])
    await loadFeatures()
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it("server javob bermasa — o'suvchi auksion ko'rsatilmaydi", async () => {
    fetchMock.mockRejectedValue(new TypeError("offline"))
    const { loadFeatures } = await freshModule()
    expect(await loadFeatures()).toEqual({ ascending_auction: false })
  })

  it("500 da ham xavfsiz zaxira", async () => {
    fetchMock.mockResolvedValue(json(500, { detail: "boom" }))
    const { loadFeatures } = await freshModule()
    expect(await loadFeatures()).toEqual({ ascending_auction: false })
  })
})
