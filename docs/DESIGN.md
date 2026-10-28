# Bazart — Dizayn tizimi (v2)

Frontend (`frontend/`) dizayn qarorlari. Yo'naltiruvchi tamoyil: **fotolar — qahramon,
interfeys — sahna.** Interfeys neytral va orqaga chekinadi; yagona aksent rangi — harakat;
shoshilinchlikni bezak emas, muddat (deadline) aytadi. Har ekranning bitta vazifasi bor.

Auditoriya: telefondan xarid qiluvchi 20–45 yoshli xaridorlar (O'zbekiston, narx so'mda, til o'zbekcha).

To'liq dizayn tizimi (komponent kartalari, sahifa maketlari, holatlar):
<https://claude.ai/artifact/KiK5no39Ky7rR2UnahX3HD>. Kodda yagona manba — `frontend/app/globals.css`.
Dizayn tizimidagi escrow / topshirish kodi / nizo bo'limlari Faza E dan oldingi holatni
tasvirlaydi va **qurilmaydi** (Bazart to'lovda ishtirok etmaydi).

## 1. Palitra

Manba: `frontend/app/globals.css` (`:root` va `.dark`). Kontrastlar WCAG AA bo'yicha tekshirilgan.
**Komponentlarda hardcode rang TAQIQ** — faqat token.

| Rol | Token | Yorug' | Qorong'u | Izoh |
|---|---|---|---|---|
| Sahifa asosi | `--background` | `#FFFFFF` | `#171614` | yorug'da toza oq |
| Karta / sirt | `--card` | `#FFFFFF` | `#1E1D1B` | `border` chizig'i + `shadow-xs` bilan ajraladi |
| Menyu / dialog | `--popover` | `#FFFFFF` | `#24221F` | dark'da card'dan bir pog'ona yuqori |
| Botiq maydon | `--muted` | `#F7F7F5` | `#26241F` | qidiruv, chip, ikkilamchi tugma, jadval sarlavhasi |
| Matn 1-daraja | `--foreground` | `#1B1A18` | `#F4F3F0` | oq ustida 16:1 |
| Matn 2-daraja | `--muted-foreground` | `#6B6863` | `#A8A49D` | oq ustida 5.55:1, muted ustida 5.3:1 |
| Chiziq (dekorativ) | `--border` | `#ECECEA` | `oklch(1 0 0 / 10%)` | boshqaruvning yagona chegarasi EMAS |
| Boshqaruv chegarasi | `--border-strong` = `--input` | `#8F8A82` | `#77736C` | input/checkbox/switch, oq ustida 3:1 |
| Brend (majolika ko'ki) | `--brand` = `--primary` | `#12659E` | `#1F72AD` | asosiy tugma, faol nav, havola, tanlov |
| Brend hover | `--brand-hover` | `#0F5687` | `#1A659B` | oq matn 7.8:1 |
| Brend tonal | `--brand-subtle` / `-foreground` | `#E8F1F8` / `#0D4F7D` | `#142837` / `#8CC3EA` | tanlangan chip, info eslatma, 7.5:1 |
| Fokus halqasi | `--ring` | `#12659E` | `#5AA6DC` | 2px + 2px offset |
| Success | `--success` (+ `-subtle`) | `#0E7A46` | `#0E7A46` | oq matn 5.4:1 |
| Warning | `--warning` (+ `-subtle`) | `#E1900B` | `#F0A420` | **doim quyuq matn**; och fonda amber matn TAQIQ |
| Error | `--error` (+ `-subtle`) | `#C4362C` | `#C4362C` | oq matn 5.37:1 |
| Foto ustidagi qatlam | `--scrim` / `-foreground` | `rgba(23,22,20,.72)` / oq | — | foto ustida oq matn >= 7:1 |
| Foto o'rni | `--photo-1…6` | iliq deyarli oq tonlar | — | rasmsiz mahsulot fonlari |

Belgilar va eslatmalar sukut bo'yicha **tonal** (`*-subtle` fon + `*-subtle-foreground` matn);
solid to'ldirish — faqat bitta urg'u ("Bugun tugaydi", "Gʻolib"). Qorong'u rejimda holat matni
`*-subtle-foreground` bilan yoziladi.

**Nega majolika ko'ki + oq asos (v2, 2026-oktabr):** v1 da lajuvard faqat katta bloklarda, tugmalar
siyoh, fon iliq qog'oz edi. v2 da rang yagona harakat signali bo'ldi: sovuq, o'rtacha to'yingan ko'k
iliq tovar fotolari orqasida chekinadi, lekin CTA sifatida aniq o'qiladi. Fon oq — fotolar toza
ko'rinadi; yorug' rejimda o'rta kulrang fon yo'q.

## 2. Tipografika

**Bitta shrift oilasi — Inter** (400/500/600/700), `next/font` orqali (`frontend/app/layout.tsx`).
`font-heading`, `font-sans` va `font-mono` hammasi Inter'ga boradi: sarlavhalar faqat o'lcham va
qalinlik bilan ajraladi, ozgina manfiy tracking bilan. Serif, display va mono shrift yo'q.

| Uslub | O'lcham / qator | Qalinlik | Qayerda |
|---|---|---|---|
| display | 48 / 52 | 700 | bosh sahifa hero, sahifada bitta |
| heading-1 | 32 / 40 | 700 | sahifa sarlavhasi |
| heading-2 | 24 / 32 | 600 | bo'lim, panel, dialog sarlavhasi |
| title | 18 / 28 | 600 | karta guruhlari, sheet sarlavhasi |
| body | 16 / 24 | 400 | asosiy matn, inputlar (iOS zoom yo'q) |
| body-sm / label | 14 / 20 | 400 / 500 | karta nomi, yordam matni, tugmalar |
| caption | 12 / 16 | 500 | meta qator, belgilar, karta countdown'i |
| price-xl / price | 32 / 18 | 700 | narx, `tabular-nums` |

Type scale yopiq: **12 / 14 / 16 / 18 / 24 / 32 / 48px** (`text-xs`…`text-3xl`). Bosh harf
(uppercase) faqat `overline` uslubida ("JORIY NARX"); sarlavhalar oddiy registrda.

**oʻ/gʻ (U+02BB) qamrovi:** Inter qamraydi. UI matnida ASCII `'` emas, U+02BB ishlatiladi.

## 3. Shakl, soya, layout

- **Radius:** `rounded-xs` 6 · `rounded-sm` 8 (kichik tugma) · `rounded-md` 12 (tugma, input,
  menyu) · `rounded-lg` 16 (karta, foto) · `rounded-xl` 24 (sheet, dialog, hero) · `rounded-full`
  (chip, pill, avatar, deadline chipi).
- **Soya:** tekis. `shadow-xs` tinch karta, `shadow-sm` foto ustidagi chip, `shadow-md` hover /
  menyu / yopishqoq panel, `shadow-lg` faqat dialog va sheet. Glassmorphism, blur, gradient,
  rangli chap-chegarali karta, `01/02/03` markerlar — TAQIQ.
- **Tugma:** balandlik 44px (`sm` 36, `lg` 52), `rounded-md`, qalinlik 600. Ekranda bitta brend
  tugma; qolganlari `secondary` (muted), `outline` (card + border), `ghost`.
- **Input:** 48px, `rounded-md`, `border-input`; hover — `foreground` chegara; fokus — `ring` +
  3px `brand-subtle` halqa; xato — `error` + `error-subtle` halqa.
- **Konteyner:** 1240px (`max-w-page`), chekka 16px (360px'da) / 24px (640px+). Spacing 4px asosida.
- **Mahsulot to'ri:** 2 ustun (360px, 12px oraliq) → 3 (768) → 4 (1024+), bosh sahifa qatorida 5.

## 4. Sahifalar (mobil-birinchi, 360–1440px)

- **Sarlavha:** 72px oq panel + pastki chiziq; logo (32px brend kvadrat + bolg'acha + "Bazart"),
  "Kategoriyalar" pill, eng keng element — qidiruv pill'i (ichida "Qidirish" tugmasi), o'ngda
  "Sotish" outline, ikonka-tugmalar (sanoq nuqtasi bilan), avatar menyusi. Desktop'da ostida 44px
  kategoriya qatori. Telefonda qidiruv alohida qatorda.
- **Pastki tab-bar (< 768px):** 5 band, ikonka 52x30 pill ichida; faol — `brand` matn, `brand-subtle`
  pill; markazda "Sotish" — to'ldirilgan brend pill. Anonim ham "Sotish"ni ko'radi (kirishga, keyin
  sotishga qaytaradi).
- **Bosh sahifa** — *vazifa: tez qidirish + shoshilinchni ko'rsatish.* Bento hero (tekis brend blok
  + eng shoshilinch mahsulot + "kontaktlar kelishuvdan keyin" plitkasi) → kategoriya plitkalari
  (64px) → **"Tez tugaydi"** qatori (muddat bo'yicha, sahifa umurtqasi) → "Nega Bazart" → "Yangi
  mahsulotlar" to'ri kategoriya chiplari bilan.
- **Katalog** — *vazifa: natijalarni skan qilish va toraytirish.* Sarlavha + natijalar soni →
  desktop'da segmentli saralash (default: tugash vaqti) + yopishqoq 248px filtr ustuni; telefonda
  "Saralash" va "Filtrlar" pill'lari pastdan ochiladigan sheet'lar bilan. Faol filtrlar — tonal chip.
- **Mahsulot kartasi:** ramka yo'q — foto kartaning o'zi. Kvadrat foto (`rounded-lg`), chap tepada
  `on-photo` holat belgisi, pastda muddat chizig'i → nom (14/500, 2 qator) → narx (18/700) → meta
  (12px: ikonka + "N ta taklif" / "Narx taklifi" · joy). Hover — foto `shadow-md`. Tugagan:
  foto 55% fon bilan yopiladi, `neutral` belgi.

## 5. Imzo element — "Muddat chizig'i" (DeadlineBar)

Har mahsulot fotosining pastki chetida (10px ichkarida) **countdown chipi + 4px o'lchagich**.
Kartada, hero plitkasida va mahsulot sahifasida bir xil komponent (`ui/deadline-bar.tsx`).

| Qolgan vaqt | Chip | Holat |
|---|---|---|
| > 6 soat | `scrim` fon, oq matn, oq o'lchagich | xotirjam |
| ≤ 6 soat | `warning` fon, `warning-foreground` (quyuq) matn | diqqat |
| ≤ 30 daqiqa | `error` fon, oq matn | shoshilinch |

- Matn rangli fon USTIDA — v1 dagi scrim ustidagi amber matn (2.4:1) muammosi yo'q.
- O'lchagich savdo oynasi (3/5/7 kun) bo'yicha to'ladi. `inline` variant — matn ichidagi tonal chip.
- Motion: faqat raqam yangilanadi; pulsatsiya va rang animatsiyasi yo'q.

## Motion

Faqat 150–250ms funksional o'tishlar (`--duration-fast/base/slow`, `cubic-bezier(0.2, 0, 0, 1)`).
Dekorativ scroll-animatsiya va parallax TAQIQ. `prefers-reduced-motion` globals.css da reset qilingan.

## Terminologiya (UI matni)

Sotiladigan narsa foydalanuvchiga **"mahsulot"** deb ataladi — **"lot" EMAS** (mahsulotlarim,
mahsulotingiz sotildi, Mahsulot joylash). Bu faqat foydalanuvchiga ko'rinadigan matnga tegishli:
kod nomlari (`Lot` turi, `components/lot/*`, `/lot/[id]` marshruti) o'zgarmaydi. Tugma = fe'l +
obyekt, oddiy registrda ("Taklif berish", "Mahsulot joylash"). Emoji — hech qayerda.
