"use client"

import * as React from "react"
import { useReducedMotion } from "motion/react"

import { cn } from "@/lib/utils"
import { formatNumber, tiyinToSoum } from "@/lib/format"
import { SlidingNumber } from "@/components/animate-ui/primitives/texts/sliding-number"

// Funksional, qisqa spring — jonli o'zgarishni bildiradi, dekorativ emas.
const SPRING = { stiffness: 260, damping: 34, mass: 0.4 } as const

/**
 * Jonli narx (tiyin -> so'm). Raqamlar almashganda odometer effekti bilan
 * suriladi — WS orqali yangi taklif kelganda o'zgarish ko'zga tashlanadi.
 * Sahifa yuklanganda statik (`initiallyStable`); faqat keyingi o'zgarishda animatsiya.
 * `prefers-reduced-motion` da oddiy matn ko'rsatiladi.
 */
/**
 * Ming ajratgichi — UZILMAS bo'shliq (U+00A0). SlidingNumber har guruhni flex
 * ichida alohida <span> qilib chizadi; faqat oddiy bo'shliqdan iborat span brauzerda
 * siqilib, narx "3200000" bo'lib ko'rinardi. NBSP siqilmaydi, ko'rinishi bir xil.
 */
const THOUSAND_SEP = "\u00A0"

function AnimatedSom({ tiyin, className }: { tiyin: string; className?: string }) {
  const reduce = useReducedMotion()
  const som = tiyinToSoum(tiyin)

  if (reduce) {
    return <span className={cn("tabular-nums", className)}>{formatNumber(som)} soʻm</span>
  }

  return (
    <span className={cn("inline-flex items-baseline gap-1 tabular-nums", className)}>
      <SlidingNumber
        number={som}
        thousandSeparator={THOUSAND_SEP}
        transition={SPRING}
        initiallyStable
      />
      <span>soʻm</span>
    </span>
  )
}

/**
 * Butun son (statistika). Ko'rinishga kelganda 0 dan sanaladi (bir marta).
 * `som` — pul bo'lsa oxiriga "soʻm" qo'shiladi. Reduced-motion da statik.
 */
function AnimatedInteger({
  value,
  som = false,
  className,
}: {
  value: number
  som?: boolean
  className?: string
}) {
  const reduce = useReducedMotion()
  const suffix = som ? " soʻm" : ""

  if (reduce) {
    return (
      <span className={cn("tabular-nums", className)}>
        {formatNumber(value)}
        {suffix}
      </span>
    )
  }

  return (
    <span className={cn("inline-flex items-baseline gap-1 tabular-nums", className)}>
      <SlidingNumber number={value} thousandSeparator={THOUSAND_SEP} transition={SPRING} inView inViewOnce />
      {som && <span>soʻm</span>}
    </span>
  )
}

export { AnimatedSom, AnimatedInteger }
