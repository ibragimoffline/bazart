# Bazart — Dizayn tizimi

Frontend (`frontend/`) dizayn qarorlari. Yo'naltiruvchi tamoyil: **fotolar — qahramon,
interfeys — sahna**. Uslub (Behance do'kon loyihalari tahlilidan: VORS, pole, Drip Riot):
**bitta kuchli rang katta bloklarda** (lajuvard), **qalin bosh harfli sarlavhalar**, mahsulotlar
yumshoq plitkalarda chegarali teg bilan, tugmalar neytral siyoh. Telefon — asosiy qurilma:
chetdan-chetga banner, gorizontal suriladigan qatorlar, ilova uslubidagi pastki tab-bar.
Har sahifaning bitta vazifasi bor.

Auditoriya: telefondan xarid qiluvchi 20–45 yoshli xaridorlar (O'zbekiston, narx so'mda, til o'zbekcha).

## 1. Palitra

Manba: `frontend/app/globals.css` (`:root` va `.dark`). Kontrastlar WCAG AA bo'yicha hisoblab
tekshirilgan. **Komponentlarda hardcode rang TAQIQ** — faqat token.

| Rol | Token | Yorug' | Qorong'u | Kontrast (AA) |
|---|---|---|---|---|
| Asos (qog'oz) | `--background` | `#F4F2EE` | `#171614` | siyoh matn 15.5:1 / 16.3:1 |
| Sirt (karta/maydon) | `--card` `--popover` | `#FFFFFF` | `#1E1D1B` | — |
| Foto o'rni / chip | `--muted` | `#EBE8E3` | `#26241F` | — |
| Matn 1-daraja (siyoh) | `--foreground` | `#1B1A18` | `#F4F3F0` | 15.5:1 |
| Matn 2-daraja | `--muted-foreground` | `#66625C` | `#A8A49D` | 5.4:1 (oq ustida 6.1:1) / 7.29:1 |
| Brend (lajuvard) | `--brand` | `#1F4E9D` | `#2D5AAB` | oq matn 8.0:1 / 6.6:1; qog'oz ustida matn 7.1:1 |
| Brend och fon | `--brand-soft` | `#E6EBF5` | `#1C2436` | siyoh 14.6:1, 2-daraja matn 5.1:1 |
| Asosiy tugma (siyoh) | `--primary` | `#1B1A18` | `#F4F3F0` | qog'oz matn 15.5:1 / 16.3:1 |
| Success | `--success` | `#0E7A46` | `#0E7A46` | oq matn 5.4:1 |
| Warning | `--warning` | `#E1900B` | `#F0A420` | **quyuq matn** 6.79:1 / 8.64:1 |
| Error | `--error` | `#C4362C` | `#C4362C` | oq matn 5.37:1 |

Chegara: `--border #E3DFD8` (dark: `oklch(1 0 0 / 10%)`).

**Nega lajuvard bloklar + siyoh tugmalar (2026-oktabr):** avval brend majolika ko'ki `#12659E`
kichik tugmalarda edi — oq qutilar bilan birga sayt Fongabi kabi oddiy savdo platformalariga
o'xshardi. Keyin to'liq rangsiz "siyoh va qog'oz" sinab ko'rildi — juda sodda chiqdi. Yechim:
rang **katta, ishonchli bloklarda** (banner, plitkalar), harakat tugmalari esa neytral siyoh —
rang va tugma raqobatlashmaydi. Lajuvard — Samarqand/Registon koshinlari ko'ki (mahalliy ildiz).

**Shakllar:** `--radius` 14px (kartalar 18px). Tugma, chip, qidiruv, belgilar — `rounded-full`.
Mahsulot kartasi — quti emas: 4:5 plitka (rasm yo'q bo'lsa `brand-soft`), chap tepada chegarali
bosh harfli teg ("ISHLATILGAN"), pastda muddat "pill"i va 2px o'lchagich; ostida qalin nom,
narx (Inter, tabular) va bir qator tafsilot ("Auksion · 3 ta taklif").
Bo'lim sarlavhasi — `SectionHeading`: qalin bosh harf + ingichka chiziq + "BARCHASI →" pill.
Bosh sahifa ritmi: lajuvard banner -> kategoriya plitkalari -> qatorlar -> siyoh "Nega Bazart"
bloki (qog'oz -> rang -> qog'oz -> siyoh).
Havola — siyoh rangida, doimiy yumshoq tagchiziq (`decoration-foreground/30`).

## 2. Tipografika

Ikki rol, ikkalasi Google Fonts, `next/font` orqali (`frontend/app/layout.tsx`).

- **Sarlavha:** Space Grotesk (600/700) — `font-heading`. O'ziga xos `a`/`g` shakllari.
- **Matn/UI:** Inter (400/500/600) — `font-sans`. 360px'da tiniq; `tabular-nums` bilan narxlar tekis.
- Narx/countdown raqamlari Inter `tabular-nums` — alohida uchinchi shrift yo'q.

**oʻ/gʻ (U+02BB) qamrovi tekshirilgan** — bu tanlovni belgiladi. Ko'p zamonaviy shriftlar bu
belgini qamramaydi va tofu ko'rsatadi:

| Shrift | U+02BB (oʻ/gʻ) | Holat |
|---|---|---|
| Space Grotesk, Inter | ✓ | **Tanlandi** |
| IBM Plex Sans, Work Sans | ✓ | zaxira |
| Manrope, Plus Jakarta Sans, Sora, Figtree, Onest | ✗ | **rad** (tofu) |

Type scale: **12 / 14 / 16 / 18 / 24 / 32 / 48px** (`text-xs`…`text-3xl`). Boshqa o'lcham yo'q.
Spacing 4px asosida. Sarlavha faqat 24/32/48, matn 14/16/18.

## 3. Layout kontseptsiyasi (mobil-birinchi, 360–1440px)

- **Asosiy sahifa** — *vazifa: tez qidirish + shoshilinchni ko'rsatish.* Katta qidiruv →
  kategoriya chip'lari → **"Bugun tugaydi"** rail (deadline bo'yicha saralangan, sahifaning
  umurtqasi) → yangi e'lonlar grid. Pastda tab-bar.
- **Katalog** — *vazifa: natijalarni saralab skan qilish.* Sticky filtr/sort bar (default sort:
  tugash vaqti) → 2 ustunli grid (desktop 3–4 + yon filtr). Har kartada muddat chizig'i + narx +
  taklif soni.
- **Mahsulot** — *vazifa: ishonch bilan taklif berish.* Hero foto + muddat chizig'i → sarlavha →
  katta joriy narx (tabular) + keyingi qadam → sotuvchi reytingi + escrow himoyasi → tavsif →
  sticky asosiy CTA (accent). Desktop: foto chapda, narx/CTA o'ngda yopishqoq ustun.

## 4. Imzo element — "Muddat chizig'i" (Deadline bar)

Platformani ajratib turadigan yagona detal: **har tovar rasmining pastki chetiga o'rnatilgan
ingichka vaqt-o'lchagich + tabular countdown**. Kartada ham, hero'da ham bir xil komponent.
Deadline yaqinlashgani sari kuchayadi:

| Qolgan vaqt | Rang | Holat |
|---|---|---|
| > 24 soat | `--muted-foreground` (neytral) | xotirjam |
| ≤ 6 soat | `--warning` (amber) | diqqat |
| ≤ 30 daqiqa | `--error` (qizil) | shoshilinch |

- Bazart'ning yagona farqi — majburiy deadline. Imzo shu farqni ko'zga aylantiradi.
- Rasm **burchagida** ixcham "pill" + pastki chetda 2px chiziq — fotoni yopmaydi.
- Motion: faqat raqam jonli yangilanadi (dekorativ sikl yo'q); `prefers-reduced-motion` mos.
- CLAUDE.md dagi taqiqlangan shablonlarning hech biri emas. Egalik — izchillik + eskalatsiya orqali.

## Motion

Faqat 150–250ms funksional o'tishlar (`--duration-fast/base/slow`, `--ease-standard`).
Dekorativ scroll-animatsiya va parallax TAQIQ. `prefers-reduced-motion` globals.css da reset qilingan.

## Terminologiya (UI matni)

Sotiladigan narsa foydalanuvchiga **"mahsulot"** deb ataladi — **"lot" EMAS** (mahsulotlarim,
mahsulotingiz sotildi, Mahsulot joylash). Bu faqat foydalanuvchiga ko'rinadigan matnga tegishli:
kod nomlari (`Lot` turi, `components/lot/*`, `/lot/[id]` marshruti) hozircha o'zgarmaydi.
