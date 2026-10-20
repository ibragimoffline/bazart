"use client"

/**
 * Backend feature flag'lari (GET /features). UI va API bitta manbadan o'qiydi:
 * bayroq faqat backend'da (FEATURE_ASCENDING_AUCTION), frontend qayta build qilinmaydi.
 * API baribir o'zi tekshiradi — bu yerdagi qiymat faqat nimani ko'rsatishni hal qiladi.
 */

import * as React from "react"

import { apiFetch } from "@/lib/api/client"

export type Features = {
  /** O'suvchi (ingliz) auksion yangi e'lonlar uchun yoqilganmi. */
  ascending_auction: boolean
}

/** Yuklab bo'lmasa — xavfsiz tomon: o'chirilgan imkoniyat ko'rsatilmaydi. */
const FALLBACK: Features = { ascending_auction: false }

let cached: Features | null = null
let inflight: Promise<Features> | null = null

export function loadFeatures(): Promise<Features> {
  if (cached) return Promise.resolve(cached)
  if (!inflight) {
    inflight = apiFetch<Features>("/features", { auth: false })
      .then((f) => (cached = f))
      .catch(() => FALLBACK)
      .finally(() => {
        inflight = null
      })
  }
  return inflight
}

/** null — hali yuklanmoqda. */
export function useFeatures(): Features | null {
  const [features, setFeatures] = React.useState<Features | null>(cached)
  React.useEffect(() => {
    let alive = true
    void loadFeatures().then((f) => alive && setFeatures(f))
    return () => {
      alive = false
    }
  }, [])
  return features
}
