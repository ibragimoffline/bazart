/**
 * Narx va son formatlash — O'zbekiston (uz-UZ) lokali.
 *
 * Backend pulni tiyinda (butun son) saqlaydi; UI so'mda ko'rsatadi.
 * Formatlash mantig'i bir joyda — komponentlarda takrorlanmaydi.
 */

/**
 * Butun sonni bo'shliq bilan guruhlaydi: 4250000 -> "4 250 000".
 *
 * Ajratgich ATAYLAB qo'lda qo'yiladi, `Intl.NumberFormat` orqali emas: "uz-UZ"
 * ajratgichi muhit ICU'siga qarab vergul (","), uzilmas bo'shliq yoki apostrof
 * bo'lib qolardi — ya'ni narx brauzerga qarab har xil ko'rinardi. Bu yerda u
 * har doim oddiy bo'shliq (animatsiyali narxda — ko'rinishi bir xil uzilmas bo'shliq).
 */
export function formatNumber(value: number): string {
  const rounded = Number.isFinite(value) ? Math.round(value) : 0;
  const sign = rounded < 0 ? "-" : "";
  return sign + Math.abs(rounded).toString().replace(/\B(?=(\d{3})+(?!\d))/g, " ");
}

/** So'mdagi narx: 4250000 -> "4 250 000 soʻm". */
export function formatSom(soum: number): string {
  return `${formatNumber(soum)} soʻm`;
}

/** Tiyindagi narxni so'mda ko'rsatish: 425000000 (tiyin) -> "4 250 000 soʻm". */
export function formatSomFromTiyin(tiyin: number): string {
  return formatSom(tiyin / 100);
}

/** Backend tiyin (string) -> "4 250 000 soʻm". Asosiy API formatlovchi. */
export function formatTiyin(tiyin: string | number): string {
  const n = typeof tiyin === "string" ? Number(tiyin) : tiyin;
  return formatSom((Number.isFinite(n) ? n : 0) / 100);
}

/** Tiyin (string) -> butun so'm (number). Input maydonlari uchun. */
export function tiyinToSoum(tiyin: string | number): number {
  const n = typeof tiyin === "string" ? Number(tiyin) : tiyin;
  return Math.round((Number.isFinite(n) ? n : 0) / 100);
}

/** So'm (number) -> tiyin (string). Bid yuborishda: user so'm kiritadi. */
export function soumToTiyin(soum: number): string {
  return String(Math.round(soum) * 100);
}

/**
 * Chegirma foizi eski va yangi narxdan. 1..99 oralig'ida butun son;
 * chegirma bo'lmasa (yoki noto'g'ri qiymatda) 0 qaytaradi.
 */
export function discountPercent(oldPrice: number, newPrice: number): number {
  if (oldPrice <= 0 || newPrice <= 0 || newPrice >= oldPrice) return 0;
  return Math.round((1 - newPrice / oldPrice) * 100);
}
