/**
 * O'zbekiston telefon raqami: kiritish niqobi va server bilan BIR XIL normallashtirish
 * (app/schemas/user.py normalize_phone). Server baribir o'zi tekshiradi — bu yerda faqat
 * qulay kiritish va xatoni oldindan ko'rsatish.
 */

const SEPARATORS = /[\s\-().]/g

/** Kiritilgan raqamni `+998XXXXXXXXX` ga keltiradi; tuzilma noto'g'ri bo'lsa null. */
export function normalizeUzPhone(input: string): string | null {
  let digits = input.trim().replace(SEPARATORS, "").replace(/^\+/, "")
  if (digits.startsWith("00")) digits = digits.slice(2)
  if (!/^\d+$/.test(digits)) return null
  if (digits.length === 9) digits = `998${digits}`
  if (digits.length !== 12 || !digits.startsWith("998")) return null
  return `+${digits}`
}

/** Mahalliy 9 raqam (operator + abonent) — "+998" prefiksidan keyingi qism. */
export function localDigits(input: string): string {
  const digits = input.replace(/\D/g, "")
  return (digits.startsWith("998") && digits.length > 9 ? digits.slice(3) : digits).slice(0, 9)
}

/** "901234567" -> "90 123 45 67" (qisman kiritilganini ham formatlaydi). */
export function formatLocal(digits: string): string {
  const d = digits.slice(0, 9)
  return [d.slice(0, 2), d.slice(2, 5), d.slice(5, 7), d.slice(7, 9)].filter(Boolean).join(" ")
}

/** "+998901234567" -> "+998 90 123 45 67". */
export function formatUzPhone(e164: string | null | undefined): string {
  if (!e164) return ""
  const normalized = normalizeUzPhone(e164)
  return normalized ? `+998 ${formatLocal(normalized.slice(4))}` : e164
}
