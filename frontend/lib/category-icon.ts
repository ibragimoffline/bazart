import {
  BabyIcon,
  BikeIcon,
  BookOpenIcon,
  CarIcon,
  GemIcon,
  LaptopIcon,
  LayersIcon,
  ShirtIcon,
  SmartphoneIcon,
  SofaIcon,
  type LucideIcon,
} from "lucide-react"

/**
 * Kategoriya slug'i -> ikonka. Slug'lar admin tomonidan yaratiladi va farq qilishi
 * mumkin ("kiyim" / "kiyim-kechak"), shu sabab so'z boshi bo'yicha moslanadi.
 * Topilmasa — umumiy ikonka.
 */
const RULES: [prefix: string, icon: LucideIcon][] = [
  ["telefon", SmartphoneIcon],
  ["elektron", LaptopIcon],
  ["kiyim", ShirtIcon],
  ["avto", CarIcon],
  ["uy", SofaIcon],
  ["kolleksiya", GemIcon],
  ["antik", GemIcon],
  ["sport", BikeIcon],
  ["bola", BabyIcon],
  ["kitob", BookOpenIcon],
]

export function categoryIcon(slug: string): LucideIcon {
  const s = slug.toLowerCase()
  return RULES.find(([prefix]) => s.startsWith(prefix))?.[1] ?? LayersIcon
}
