"use client"

/**
 * Auksion real-time WebSocket hook'i.
 *
 * Backend `/api/v1/ws/auctions/{auction_id}?token=<JWT>` kanaliga ulanadi va
 * bid qo'yilganda `bid_service` tarqatgan narx yangilanishlarini oladi.
 * Kelayotgan xabar shakli (bid_service.place_bid):
 *   { type: "BID_PLACED", auction_id, current_price (tiyin string),
 *     highest_bidder_id, end_time (ISO) }
 * Buy-now (auction_service.buy_now) xuddi shu shaklda `type: "BUY_NOW"` yuboradi —
 * auksion yakunlangan; handler turga qaramay auksionni qayta yuklaydi.
 *
 * Real-time QO'SHIMCHA — u boshlang'ich fetch yoki bid oqimini almashtirmaydi.
 * Socket ishlamasa (token yo'q, URL qurib bo'lmadi, server o'chiq) sahifa
 * BUZILMAYDI: hook jimgina no-op qiladi va kichik backoff bilan qayta ulanadi.
 */

import * as React from "react"

import { getAccessToken } from "@/lib/api/token"

/** Kanaldan kelayotgan xabar. Pul maydonlari — TIYIN (string). */
export type AuctionSocketMessage = {
  type?: string
  auction_id?: number
  /** tiyin (string) — joriy narx */
  current_price?: string
  highest_bidder_id?: number | null
  /** ISO datetime — anti-sniping uzaytirishi bo'lsa yangilanadi */
  end_time?: string
  [key: string]: unknown
}

export type SocketStatus = "idle" | "connecting" | "open" | "closed"

const MAX_BACKOFF_MS = 15000

/**
 * WS URL'ni `NEXT_PUBLIC_API_URL` dan quradi (http->ws, https->wss).
 * Token bo'lmasa yoki URL yaroqsiz bo'lsa `null` — anonim ulanish
 * backend'da 4401 bilan yopiladi, shuning uchun umuman urinilmaydi.
 */
function buildWsUrl(auctionId: number): string | null {
  const raw = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"
  let base: URL
  try {
    base = new URL(raw)
  } catch {
    return null
  }

  const token = getAccessToken()
  if (!token) return null

  const proto = base.protocol === "https:" ? "wss:" : "ws:"
  return `${proto}//${base.host}/api/v1/ws/auctions/${auctionId}?token=${encodeURIComponent(token)}`
}

/**
 * Berilgan auksion kanaliga ulanadi va narx/holat yangilanishida `onUpdate`
 * ni chaqiradi. Faqat ulanish holatini (`status`) qaytaradi.
 *
 * `onUpdate` har render'da o'zgarishi mumkin — uni ref'da saqlaymiz, shunda
 * socket har render'da qayta ulanmaydi (faqat `auctionId` o'zgarganda ulanadi).
 */
export function useAuctionSocket(
  auctionId: number,
  onUpdate: (msg: AuctionSocketMessage) => void
): { status: SocketStatus } {
  const [status, setStatus] = React.useState<SocketStatus>("idle")

  const onUpdateRef = React.useRef(onUpdate)
  React.useEffect(() => {
    onUpdateRef.current = onUpdate
  }, [onUpdate])

  React.useEffect(() => {
    // SSR yoki WebSocket yo'q muhitda — no-op.
    if (typeof window === "undefined" || typeof WebSocket === "undefined") {
      return
    }

    let unmounted = false
    let socket: WebSocket | null = null
    let timer: ReturnType<typeof setTimeout> | null = null
    let attempts = 0

    const schedule = (delay: number) => {
      if (unmounted) return
      if (timer) clearTimeout(timer)
      timer = setTimeout(connect, delay)
    }

    const scheduleReconnect = () => {
      if (unmounted) return
      attempts += 1
      // Kichik eksponensial backoff: 1s, 2s, 4s ... maksimal 15s.
      schedule(Math.min(1000 * 2 ** (attempts - 1), MAX_BACKOFF_MS))
    }

    function connect() {
      const url = buildWsUrl(auctionId)
      if (url === null) {
        // Token yo'q / URL yaroqsiz — jimgina to'xtaymiz (reconnect qilmaymiz).
        setStatus("closed")
        return
      }

      setStatus("connecting")
      try {
        socket = new WebSocket(url)
      } catch {
        scheduleReconnect()
        return
      }

      socket.onopen = () => {
        attempts = 0
        setStatus("open")
      }

      socket.onmessage = (event) => {
        try {
          const data = JSON.parse(String(event.data)) as AuctionSocketMessage
          // Faqat narx yangilanishi bor xabarlarni uzatamiz.
          if (data && typeof data === "object" && data.current_price != null) {
            onUpdateRef.current(data)
          }
        } catch {
          // JSON emas yoki buzuq — e'tiborsiz qoldiramiz.
        }
      }

      // onerror'dan keyin onclose ham chaqiriladi — qayta ulanishni o'sha yerda
      // boshqaramiz, shu sababli bu yerda faqat jim turamiz.
      socket.onerror = () => {}

      socket.onclose = () => {
        setStatus("closed")
        if (!unmounted) scheduleReconnect()
      }
    }

    // Boshlang'ich ulanishni ham timer orqali (async) boshlaymiz — effekt
    // tanasida sinxron setState chaqirmaslik uchun.
    schedule(0)

    return () => {
      unmounted = true
      if (timer) clearTimeout(timer)
      if (socket) {
        socket.onopen = null
        socket.onmessage = null
        socket.onerror = null
        socket.onclose = null
        try {
          socket.close()
        } catch {
          // e'tiborsiz
        }
      }
    }
  }, [auctionId])

  return { status }
}
