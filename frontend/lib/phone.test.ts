/** Telefon niqobi va normallashtirish — server (normalize_phone) bilan bir xil natija. */
import { describe, expect, it } from "vitest"

import { formatLocal, formatUzPhone, localDigits, normalizeUzPhone } from "@/lib/phone"

describe("normalizeUzPhone", () => {
  it.each([
    "+998901112233",
    "998901112233",
    "+998 90 111-22-33",
    "(90) 111 22 33",
    "00998901112233",
    "90 111 22 33",
  ])("%s -> +998901112233", (raw) => {
    expect(normalizeUzPhone(raw)).toBe("+998901112233")
  })

  it.each(["+1 555 010 0100", "12345", "+99890111223", "9989011122334", "abc", ""])(
    "%s rad etiladi",
    (raw) => {
      expect(normalizeUzPhone(raw)).toBeNull()
    }
  )
})

describe("kiritish niqobi", () => {
  it("+998 prefiksini olib, 9 raqamgacha qisqartiradi", () => {
    expect(localDigits("+998 90 111 22 33")).toBe("901112233")
    expect(localDigits("90-111-22-334455")).toBe("901112233")
  })

  it("qisman kiritilganini ham formatlaydi", () => {
    expect(formatLocal("9")).toBe("9")
    expect(formatLocal("90111")).toBe("90 111")
    expect(formatLocal("901112233")).toBe("90 111 22 33")
  })

  it("to'liq raqamni ko'rsatish uchun formatlaydi", () => {
    expect(formatUzPhone("+998901112233")).toBe("+998 90 111 22 33")
    expect(formatUzPhone(null)).toBe("")
  })
})
