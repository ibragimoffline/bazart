"use client"

import * as React from "react"
import { useRouter } from "next/navigation"
import { useForm, useWatch, Controller } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { toast } from "sonner"
import { SparklesIcon } from "lucide-react"

import { formatSom, soumToTiyin } from "@/lib/format"
import type { Category } from "@/lib/api/types"
import { listCategories } from "@/lib/api/endpoints"
import { ApiError } from "@/lib/api/client"
import {
  createItem,
  uploadItemImage,
  createAuction,
  listSellerItems,
  updateItem,
} from "@/lib/api/seller"
import { publishItem } from "@/lib/api/offers"
import { useAuthStore } from "@/lib/store/auth"
import {
  DESCRIPTION_MAX,
  NO_DEFECTS_TEXT,
  autoIncrementSoum,
  suggestBuyNowSoum,
  suggestDutchFloorSoum,
  suggestDutchStepSoum,
  buyNowError,
  categoryProfile,
  formatEndsAt,
  suggestCategorySlug,
} from "@/lib/listing"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Checkbox } from "@/components/ui/checkbox"
import { Field, FieldLabel, FieldError, FieldDescription } from "@/components/ui/field"
import { Label } from "@/components/ui/label"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  RegionSelect,
  DistrictSelect,
  useRegions,
  useDistricts,
} from "@/components/region/region-select"
import { ImageDropzone, type PickedImage } from "@/components/seller/sell/image-dropzone"
import { PriceInput } from "@/components/seller/sell/price-input"
import { EquipmentChips } from "@/components/seller/sell/equipment-chips"
import { CollapsibleSection } from "@/components/seller/sell/collapsible-section"
import { ListingPreview, type PreviewData } from "@/components/seller/sell/listing-preview"
import { useSellDraft, loadSellDraft } from "@/components/seller/sell/use-sell-draft"

const CONDITIONS = [
  { value: "new", label: "Yangi" },
  { value: "used", label: "Ishlatilgan" },
  { value: "refurbished", label: "Tiklangan" },
] as const

const DURATIONS = ["3", "5", "7"] as const
/** Pasayuvchi auksion oralig'i (daqiqa) — server 5..1440 qabul qiladi. */
const DROP_INTERVALS = ["15", "30", "60", "180", "360", "720", "1440"] as const
const DROP_INTERVAL_LABEL: Record<(typeof DROP_INTERVALS)[number], string> = {
  "15": "15 daqiqa",
  "30": "30 daqiqa",
  "60": "1 soat",
  "180": "3 soat",
  "360": "6 soat",
  "720": "12 soat",
  "1440": "1 kun",
}

const MAX_YEAR = new Date().getFullYear() + 1

function isHttpUrl(v: string): boolean {
  try {
    const u = new URL(v)
    return u.protocol === "http:" || u.protocol === "https:"
  } catch {
    return false
  }
}

const schema = z
  .object({
    title: z.string().trim().min(3, "Nom kamida 3 belgidan iborat boʻlsin.").max(160, "Nom juda uzun."),
    category_id: z.string({ error: "Kategoriyani tanlang." }).min(1, "Kategoriyani tanlang."),
    condition: z.enum(["new", "used", "refurbished"]),
    year: z
      .string()
      .trim()
      .refine(
        (v) => !v || (/^\d{4}$/.test(v) && Number(v) >= 1900 && Number(v) <= MAX_YEAR),
        `Yil 1900 va ${MAX_YEAR} oraligʻida boʻlsin.`
      ),
    description: z
      .string()
      .trim()
      .max(DESCRIPTION_MAX, `Tavsif juda uzun (koʻpi ${DESCRIPTION_MAX} belgi).`),
    no_defects: z.boolean(),
    defects: z.string().trim().max(2000, "Nuqsonlar tavsifi juda uzun (koʻpi 2000 belgi)."),
    /** Sotish usuli: "offer" (asosiy) — xaridorlar narx va miqdor taklif qiladi; "auction" — ixtiyoriy. */
    mode: z.enum(["offer", "auction"]),
    /** Auksion narx yo'nalishi: o'suvchi (bidlar) yoki pasayuvchi (golland). */
    pricing: z.enum(["ascending", "descending"]),
    /** Pasayuvchi: har oraliqdagi pasayish, so'm (0 — kiritilmagan). */
    price_decrement: z.number().int().nonnegative(),
    /** Pasayuvchi: oraliq, daqiqa. */
    drop_interval: z.enum(DROP_INTERVALS),
    /** Pasayuvchi: eng past narx (pastki chegara), so'm. */
    floor_price: z.number().int().nonnegative(),
    /** Auksionni keyinroq boshlash (boshlanguncha narx rejimini o'zgartirish mumkin). */
    start_later: z.boolean(),
    /** datetime-local qiymati (mahalliy vaqt), start_later bo'lsa. */
    start_at: z.string(),
    /** Rozilik: taklifsiz tugasa 3 kunlik pasayuvchi auksionga o'tsin. */
    dutch_fallback: z.boolean(),
    /** O'sha bosqichning eng past narxi, so'm. */
    dutch_floor: z.number().int().nonnegative(),
    /** Necha dona (faqat "offer" rejimida; auksion har doim 1 dona). */
    quantity: z
      .number({ error: "Miqdorni kiriting." })
      .int("Butun son kiriting.")
      .min(1, "Kamida 1 dona.")
      .max(10_000, "Koʻpi bilan 10 000 dona."),
    starting_price: z.number().int().positive("Narxni kiriting."),
    duration_days: z.enum(DURATIONS),
    region_id: z.string({ error: "Viloyatni tanlang." }).min(1, "Viloyatni tanlang."),
    district_id: z.string().optional(),
    equipment: z.array(z.string()),
    location: z.string().trim().max(160, "Manzil juda uzun."),
    video_url: z
      .string()
      .trim()
      .max(500, "Havola juda uzun (koʻpi 500 belgi).")
      .refine((v) => !v || isHttpUrl(v), "Toʻliq havola kiriting: https:// bilan boshlansin."),
    /** 0 — avtomatik (narxning 5%). */
    minimum_bid_increment: z.number().int().nonnegative(),
    /** 0 — zaxira narx yo'q. */
    reserve_price: z.number().int().nonnegative(),
    /** 0 — "hoziroq sotib olish" o'chiq. */
    buy_now_price: z.number().int().nonnegative(),
  })
  .superRefine((v, ctx) => {
    // Yangi tovarda nuqson bo'lmaydi; boshqa holatda — yo belgi, yo tavsif.
    if (v.condition !== "new" && !v.no_defects && v.defects.length < 3) {
      ctx.addIssue({
        code: "custom",
        path: ["defects"],
        message: "Nuqsonlarni qisqacha yozing yoki «Nuqsonlari yoʻq» belgisini qoʻying.",
      })
    }
    const descending = v.mode === "auction" && v.pricing === "descending"
    if (descending) {
      if (!(v.price_decrement > 0)) {
        ctx.addIssue({ code: "custom", path: ["price_decrement"], message: "Pasayish qadamini kiriting." })
      }
      if (!(v.floor_price > 0)) {
        ctx.addIssue({ code: "custom", path: ["floor_price"], message: "Eng past narxni kiriting." })
      } else if (v.starting_price > 0 && v.floor_price >= v.starting_price) {
        ctx.addIssue({
          code: "custom",
          path: ["floor_price"],
          message: "Eng past narx boshlangʻich narxdan past boʻlishi kerak.",
        })
      }
    }
    if (v.mode === "auction" && v.start_later) {
      const at = Date.parse(v.start_at)
      const now = Date.now()
      if (!Number.isFinite(at) || at < now + 5 * 60_000) {
        ctx.addIssue({
          code: "custom",
          path: ["start_at"],
          message: "Kamida 5 daqiqadan keyingi vaqtni tanlang.",
        })
      } else if (at > now + 14 * 24 * 3_600_000) {
        ctx.addIssue({ code: "custom", path: ["start_at"], message: "Koʻpi bilan 14 kun oldindan." })
      }
    }
    if (v.mode === "auction" && !descending && v.dutch_fallback) {
      if (!(v.dutch_floor > 0)) {
        ctx.addIssue({ code: "custom", path: ["dutch_floor"], message: "Eng past narxni kiriting." })
      } else if (v.starting_price > 0 && v.dutch_floor >= v.starting_price) {
        ctx.addIssue({
          code: "custom",
          path: ["dutch_floor"],
          message: "Eng past narx boshlangʻich narxdan past boʻlishi kerak.",
        })
      }
    }
    // Zaxira / buy-now — faqat o'suvchi auksion sozlamalari (boshqa rejimlarda yuborilmaydi).
    if (
      v.mode === "auction" &&
      !descending &&
      v.reserve_price > 0 &&
      v.reserve_price < v.starting_price
    ) {
      ctx.addIssue({
        code: "custom",
        path: ["reserve_price"],
        message: "Zaxira narx boshlangʻich narxdan past boʻlishi mumkin emas.",
      })
    }
    const buyNowIssue =
      v.mode === "auction" && !descending
        ? buyNowError(v.buy_now_price, v.starting_price, v.reserve_price)
        : null
    if (buyNowIssue) {
      ctx.addIssue({ code: "custom", path: ["buy_now_price"], message: buyNowIssue })
    }
  })

type FormValues = z.infer<typeof schema>

const DEFAULTS: FormValues = {
  title: "",
  category_id: "",
  condition: "used",
  year: "",
  description: "",
  no_defects: false,
  defects: "",
  mode: "offer",
  pricing: "ascending",
  price_decrement: 0,
  drop_interval: "60",
  floor_price: 0,
  start_later: false,
  start_at: "",
  dutch_fallback: false,
  dutch_floor: 0,
  quantity: 1,
  starting_price: 0,
  duration_days: "5",
  region_id: "",
  district_id: undefined,
  equipment: [],
  location: "",
  video_url: "",
  minimum_bid_increment: 0,
  reserve_price: 0,
  buy_now_price: 0,
}

type Draft = { values: FormValues; categoryTouched: boolean }

/** Qoralama faqat sotuvchi biror narsa kiritganda saqlanadi (avto-to'ldirilgan joylashuv hisob emas). */
function hasContent(v: Partial<FormValues>): boolean {
  return Boolean(
    v.title?.trim() ||
      v.description?.trim() ||
      v.defects?.trim() ||
      v.video_url?.trim() ||
      (v.starting_price ?? 0) > 0 ||
      (v.reserve_price ?? 0) > 0 ||
      (v.equipment?.length ?? 0) > 0
  )
}

function orUndef(v: string | undefined): string | undefined {
  const t = v?.trim()
  return t ? t : undefined
}

/** Radio "kartochka" — butun maydon bosiladi, tanlangani brend rangida. */
const choiceClass =
  "flex min-h-11 cursor-pointer items-center gap-2 rounded-lg border border-border bg-card px-3 py-2.5 text-sm font-normal transition-colors hover:border-foreground/30 has-[[data-state=checked]]:border-primary has-[[data-state=checked]]:bg-primary/5 has-[:focus-visible]:ring-3 has-[:focus-visible]:ring-ring/50"

/**
 * Mahsulot joylash: tahrirlash -> ko'rib chiqish -> joylash.
 * Asosiy formada faqat zarur maydonlar; qolganlari avtomatik to'ldiriladi
 * (kategoriya — nomdan, joylashuv — oxirgi e'londan, qadam — narxdan) yoki
 * yig'iladigan bo'limlarda turadi.
 * Joylash: createItem -> rasmlar -> createAuction. Xato bo'lsa qayta urinishda
 * yaratilgan mahsulot va yuklangan rasmlar takrorlanmaydi.
 */
function SellForm() {
  const router = useRouter()
  const user = useAuthStore((s) => s.user)
  const draft = useSellDraft<Draft>(user?.id)
  // Qoralama birinchi renderdayoq tiklanadi — effektda reset qilinsa forma bir marta bo'sh chizilardi.
  const [saved] = React.useState(() => {
    const d = loadSellDraft<Draft>(user?.id)
    return d?.values && hasContent(d.values) ? d : null
  })

  const [categories, setCategories] = React.useState<Category[] | null>(null)
  const [images, setImages] = React.useState<PickedImage[]>([])
  const [imagesError, setImagesError] = React.useState<string | null>(null)
  const [step, setStep] = React.useState<"edit" | "preview">("edit")
  const [publishing, setPublishing] = React.useState(false)
  const [publishError, setPublishError] = React.useState<string | null>(null)
  const [categoryTouched, setCategoryTouched] = React.useState(Boolean(saved?.categoryTouched))
  const [restoredDraft, setRestoredDraft] = React.useState(Boolean(saved?.values))
  const [locationSource, setLocationSource] = React.useState<"last" | null>(null)
  const [now, setNow] = React.useState<number | null>(null)

  // Qayta urinishda dublikat bo'lmasin: yaratilgan mahsulot va yuklangan rasmlar eslab qolinadi.
  const createdItemId = React.useRef<number | null>(null)
  // Qoralama qaysi miqdor bilan yaratilgani — qayta urinishda rejim o'zgarsa yangilash uchun.
  const createdQuantity = React.useRef<number>(1)
  const uploadedImageIds = React.useRef(new Set<string>())

  const {
    register,
    handleSubmit,
    control,
    setValue,
    reset,
    getValues,
    clearErrors,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    mode: "onTouched",
    defaultValues: saved?.values ? { ...DEFAULTS, ...saved.values } : DEFAULTS,
  })

  const [title, categoryId, condition, noDefects, description, startingPrice, durationDays] =
    useWatch({
      control,
      name: [
        "title",
        "category_id",
        "condition",
        "no_defects",
        "description",
        "starting_price",
        "duration_days",
      ],
    })
  const regionId = useWatch({ control, name: "region_id" })
  const districtId = useWatch({ control, name: "district_id" })
  const mode = useWatch({ control, name: "mode" })
  const isOffer = mode === "offer"
  const pricing = useWatch({ control, name: "pricing" })
  const isDescending = !isOffer && pricing === "descending"
  const dutchFallback = useWatch({ control, name: "dutch_fallback" })
  const startLater = useWatch({ control, name: "start_later" })
  const startAt = useWatch({ control, name: "start_at" })

  // Holatga qarab standart rejim va tavsiya narxlar — sotuvchi o'zi o'zgartirgan maydonga
  // tegilmaydi (qoralamadan tiklangan qiymat ham "o'zgartirilgan" hisoblanadi).
  const touched = React.useRef({
    pricing: Boolean(saved?.values),
    buyNow: (saved?.values?.buy_now_price ?? 0) > 0,
    floor: (saved?.values?.floor_price ?? 0) > 0,
    step: (saved?.values?.price_decrement ?? 0) > 0,
  })
  React.useEffect(() => {
    if (!touched.current.pricing) {
      setValue("pricing", condition === "new" ? "descending" : "ascending")
    }
  }, [condition, setValue])
  React.useEffect(() => {
    if (!(startingPrice > 0)) return
    if (!touched.current.floor) setValue("floor_price", suggestDutchFloorSoum(startingPrice))
    const floor = getValues("floor_price")
    if (!touched.current.step && floor > 0 && floor < startingPrice) {
      setValue("price_decrement", suggestDutchStepSoum(startingPrice, floor, Number(durationDays)))
    }
    if (!touched.current.buyNow) {
      setValue("buy_now_price", condition === "new" ? 0 : suggestBuyNowSoum(startingPrice))
    }
  }, [startingPrice, durationDays, condition, setValue, getValues])
  const reservePrice = useWatch({ control, name: "reserve_price" })
  const buyNowPrice = useWatch({ control, name: "buy_now_price" })
  const incrementInput = useWatch({ control, name: "minimum_bid_increment" })
  const equipmentValue = useWatch({ control, name: "equipment" })

  const category = categories?.find((c) => String(c.id) === categoryId)
  const profile = categoryProfile(category?.slug)
  const autoIncrement = autoIncrementSoum(startingPrice)
  const effectiveIncrement = incrementInput > 0 ? incrementInput : autoIncrement
  const startMs = !isOffer && startLater && startAt ? Date.parse(startAt) : null
  const endsAt =
    now != null
      ? formatEndsAt(startMs != null && Number.isFinite(startMs) ? startMs : now, Number(durationDays))
      : null
  // Zaxira xatosi darhol ko'rinsin (blur kutilmasin).
  const reserveTooLow = reservePrice > 0 && startingPrice > 0 && reservePrice < startingPrice
  const buyNowIssue = buyNowError(buyNowPrice, startingPrice, reservePrice)

  const regions = useRegions()
  const districts = useDistricts(regionId ? Number(regionId) : null)

  // Tugash vaqti matni uchun joriy vaqt — render ichida Date.now ishlatilmaydi.
  React.useEffect(() => {
    const tick = () => setNow(Date.now())
    tick()
    const id = setInterval(tick, 30_000)
    return () => clearInterval(id)
  }, [])

  React.useEffect(() => {
    let alive = true
    listCategories()
      .then((c) => {
        if (alive) setCategories(c.filter((x) => x.is_active))
      })
      .catch(() => {
        if (alive) setCategories([])
      })
    return () => {
      alive = false
    }
  }, [])

  // Joylashuv qoralamada bo'lmasa — oxirgi e'londan olinadi.
  const prefillStarted = React.useRef(false)
  React.useEffect(() => {
    if (prefillStarted.current || user == null || saved?.values?.region_id) return
    prefillStarted.current = true
    listSellerItems(user.id)
      .then((items) => {
        const last = [...items]
          .filter((i) => i.region_id != null)
          .sort((a, b) => b.created_at.localeCompare(a.created_at))[0]
        if (!last || getValues("region_id")) return
        setValue("region_id", String(last.region_id))
        if (last.district_id != null) setValue("district_id", String(last.district_id))
        if (last.location && !getValues("location")) setValue("location", last.location)
        setLocationSource("last")
      })
      .catch(() => {
        // Oxirgi e'lon topilmasa — sotuvchi o'zi tanlaydi.
      })
  }, [user, saved, setValue, getValues])

  // Har o'zgarishda qoralamani saqlash (kechiktirilgan).
  const allValues = useWatch({ control })
  React.useEffect(() => {
    // useWatch chuqur-qisman tip beradi; qoralama baribir DEFAULTS ustiga yoziladi.
    if (hasContent(allValues as Partial<FormValues>)) {
      draft.save({ values: { ...DEFAULTS, ...allValues } as FormValues, categoryTouched })
    } else {
      draft.clear()
    }
  }, [allValues, draft, categoryTouched])

  // Yil maydoni bu kategoriyada yashirin — eski (yaroqsiz) qiymat ko'rinmas xato bilan
  // yuborishni to'sib qo'ymasin.
  React.useEffect(() => {
    if (profile.showYear) return
    if (getValues("year")) setValue("year", "")
    clearErrors("year")
  }, [profile.showYear, getValues, setValue, clearErrors])

  // Kategoriya taklifi: sotuvchi o'zi tanlamaguncha nomga qarab avtomatik qo'yiladi.
  const suggestedSlug = suggestCategorySlug(title)
  const suggested = categories?.find((c) => c.slug === suggestedSlug)
  React.useEffect(() => {
    if (categoryTouched || !suggested) return
    if (getValues("category_id") !== String(suggested.id)) {
      setValue("category_id", String(suggested.id), { shouldValidate: Boolean(errors.category_id) })
    }
  }, [suggested, categoryTouched, getValues, setValue, errors.category_id])
  const categoryAuto = !categoryTouched && suggested != null && String(suggested.id) === categoryId

  // Rasmlar uchun ochilgan blob URL'lar sahifadan chiqqanda bo'shatiladi.
  const imagesRef = React.useRef(images)
  React.useEffect(() => {
    imagesRef.current = images
  }, [images])
  React.useEffect(() => () => imagesRef.current.forEach((i) => URL.revokeObjectURL(i.url)), [])

  const placeText = (() => {
    const region = regions.data?.find((r) => String(r.id) === regionId)
    const district = districts.data?.find((d) => String(d.id) === districtId)
    return [region?.name_uz, district?.name_uz, orUndef(getValues("location"))]
      .filter(Boolean)
      .join(", ")
  })()

  const toPreview = handleSubmit(
    () => {
      if (images.length === 0) {
        setImagesError("Kamida bitta rasm qoʻshing — rasmsiz mahsulotga taklif kam beriladi.")
        document.getElementById("images")?.scrollIntoView({ behavior: "smooth", block: "center" })
        return
      }
      setPublishError(null)
      setStep("preview")
      window.scrollTo({ top: 0, behavior: "smooth" })
    },
    () => {
      if (images.length === 0) setImagesError("Kamida bitta rasm qoʻshing.")
    }
  )

  const publish = async () => {
    const values = getValues()
    setPublishing(true)
    setPublishError(null)
    try {
      const startingTiyin = soumToTiyin(values.starting_price)
      const offerMode = values.mode === "offer"
      const reserveTiyin =
        !offerMode && values.reserve_price > 0 ? soumToTiyin(values.reserve_price) : undefined
      const quantity = offerMode ? values.quantity : 1

      if (createdItemId.current == null) {
        const item = await createItem({
          title: values.title.trim(),
          quantity,
          description: orUndef(values.description),
          category_id: Number(values.category_id),
          condition: values.condition,
          location: orUndef(values.location),
          year: profile.showYear && values.year ? Number(values.year) : undefined,
          equipment: values.equipment.length ? values.equipment.join(", ") : undefined,
          defects:
            values.condition === "new"
              ? undefined
              : values.no_defects
                ? NO_DEFECTS_TEXT
                : orUndef(values.defects),
          video_url: orUndef(values.video_url),
          region_id: Number(values.region_id),
          district_id: values.district_id ? Number(values.district_id) : undefined,
          starting_price: startingTiyin,
          reserve_price: reserveTiyin,
        })
        createdItemId.current = item.id
        createdQuantity.current = quantity
      } else if (createdQuantity.current !== quantity) {
        // Qayta urinishda rejim/miqdor o'zgargan — qoralama hali e'lon qilinmagan, yangilaymiz.
        await updateItem(createdItemId.current, { quantity })
        createdQuantity.current = quantity
      }
      const itemId = createdItemId.current

      // Birinchi rasm — asosiy. Yuklanganlari qayta urinishda o'tkazib yuboriladi.
      const failed: string[] = []
      for (const [index, img] of images.entries()) {
        if (uploadedImageIds.current.has(img.id)) continue
        try {
          await uploadItemImage(itemId, img.file, index === 0)
          uploadedImageIds.current.add(img.id)
        } catch (e) {
          failed.push(e instanceof ApiError ? e.detail : img.file.name)
        }
      }
      if (uploadedImageIds.current.size === 0) {
        setPublishError(
          `Rasmlar yuklanmadi${failed[0] ? `: ${failed[0]}` : ""}. Qayta urinib koʻring — mahsulot maʼlumotlari saqlangan.`
        )
        return
      }
      if (failed.length) toast.warning(`${failed.length} ta rasm yuklanmadi, qolganlari bilan joylanadi.`)

      if (offerMode) {
        await publishItem(itemId, Number(values.duration_days) as 3 | 5 | 7)
        draft.clear()
        toast.success("Eʼlon joylandi — xaridorlar narx taklif qilishi mumkin")
        router.push(`/item/${itemId}`)
        return
      }

      const auction = await createAuction({
        item_id: itemId,
        start_time:
          values.start_later && values.start_at
            ? new Date(values.start_at).toISOString()
            : new Date().toISOString(),
        duration_days: Number(values.duration_days) as 3 | 5 | 7,
        minimum_bid_increment: soumToTiyin(
          values.minimum_bid_increment > 0
            ? values.minimum_bid_increment
            : autoIncrementSoum(values.starting_price)
        ),
        ...(values.pricing === "descending"
          ? {
              // Golland auksioni: pastki chegara reserve_price sifatida, buy-now yo'q.
              pricing_mode: "descending" as const,
              price_decrement: soumToTiyin(values.price_decrement),
              price_drop_interval_minutes: Number(values.drop_interval),
              reserve_price: soumToTiyin(values.floor_price),
            }
          : {
              reserve_price: reserveTiyin,
              buy_now_price:
                values.buy_now_price > 0 ? soumToTiyin(values.buy_now_price) : undefined,
              dutch_fallback_floor:
                values.dutch_fallback && values.dutch_floor > 0
                  ? soumToTiyin(values.dutch_floor)
                  : undefined,
            }),
      })

      draft.clear()
      toast.success(
        values.start_later
          ? "Auksion rejalashtirildi — boshlanguncha narx rejimini oʻzgartirish mumkin"
          : "Mahsulot joylandi va auksion boshlandi"
      )
      router.push(`/lot/${auction.id}`)
    } catch (e) {
      setPublishError(
        e instanceof ApiError ? e.detail : "Mahsulot joylashda kutilmagan xatolik. Qayta urinib koʻring."
      )
    } finally {
      setPublishing(false)
    }
  }

  const discardDraft = () => {
    draft.clear()
    reset(DEFAULTS)
    setCategoryTouched(false)
    setRestoredDraft(false)
    setLocationSource(null)
  }

  if (step === "preview") {
    const values = getValues()
    const data: PreviewData = {
      title: values.title.trim(),
      description: values.description.trim(),
      categoryName: category?.name ?? "",
      conditionLabel: CONDITIONS.find((c) => c.value === values.condition)?.label ?? "",
      year: profile.showYear ? orUndef(values.year) : undefined,
      defects:
        values.condition === "new"
          ? undefined
          : values.no_defects
            ? NO_DEFECTS_TEXT
            : orUndef(values.defects),
      equipment: values.equipment,
      mode: values.mode,
      descending:
        values.mode === "auction" && values.pricing === "descending"
          ? {
              decrementSoum: values.price_decrement,
              intervalLabel: DROP_INTERVAL_LABEL[values.drop_interval],
              floorSoum: values.floor_price,
            }
          : undefined,
      dutchFallbackFloorSoum:
        values.mode === "auction" && values.pricing !== "descending" && values.dutch_fallback
          ? values.dutch_floor
          : undefined,
      quantity: values.mode === "offer" ? values.quantity : 1,
      startingSoum: values.starting_price,
      incrementSoum: effectiveIncrement,
      incrementIsAuto: values.minimum_bid_increment === 0,
      reserveSoum: values.reserve_price,
      buyNowSoum: values.buy_now_price,
      durationDays: Number(values.duration_days),
      endsAt,
      place: placeText,
      videoUrl: orUndef(values.video_url),
    }
    return (
      <ListingPreview
        data={data}
        images={images}
        publishing={publishing}
        error={publishError}
        onEdit={() => setStep("edit")}
        onPublish={publish}
      />
    )
  }

  const extrasHaveError = Boolean(errors.video_url || errors.location)
  const advancedHasError = Boolean(
    errors.dutch_floor ||
    errors.reserve_price || reserveTooLow || errors.buy_now_price || buyNowIssue
  )

  return (
    <form onSubmit={toPreview} noValidate className="grid gap-6">
      {restoredDraft && (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-border bg-muted/50 px-4 py-3 text-sm">
          <span className="text-muted-foreground">
            Saqlangan qoralama tiklandi. Rasmlar qoralamada saqlanmaydi — ularni qayta qoʻshing.
          </span>
          <Button type="button" variant="ghost" size="sm" onClick={discardDraft}>
            Qoralamani tozalash
          </Button>
        </div>
      )}

      <Field>
        <FieldLabel htmlFor="images">Rasmlar</FieldLabel>
        <ImageDropzone
          id="images"
          images={images}
          onChange={(next) => {
            setImages(next)
            if (next.length) setImagesError(null)
          }}
          invalid={Boolean(imagesError)}
          describedBy="images-hint"
        />
        <FieldDescription id="images-hint">
          Birinchi rasm katalogda chiqadi. Turli burchakdan va nuqsonlarni yaqindan oling.
        </FieldDescription>
        <FieldError>{imagesError}</FieldError>
      </Field>

      <Field>
        <FieldLabel htmlFor="title">Nomi</FieldLabel>
        <Input
          id="title"
          placeholder="Masalan: iPhone 13, 128 GB, koʻk"
          aria-invalid={errors.title ? true : undefined}
          {...register("title")}
        />
        <FieldError>{errors.title?.message}</FieldError>
      </Field>

      <Field>
        <FieldLabel htmlFor="category">Kategoriya</FieldLabel>
        <Controller
          control={control}
          name="category_id"
          render={({ field }) => (
            <Select
              value={field.value || ""}
              onValueChange={(v) => {
                setCategoryTouched(true)
                field.onChange(v)
              }}
              disabled={categories === null}
            >
              <SelectTrigger
                id="category"
                className="w-full"
                aria-invalid={errors.category_id ? true : undefined}
                onBlur={field.onBlur}
              >
                <SelectValue placeholder={categories === null ? "Yuklanmoqda…" : "Kategoriyani tanlang"} />
              </SelectTrigger>
              <SelectContent>
                {(categories ?? []).map((c) => (
                  <SelectItem key={c.id} value={String(c.id)}>
                    {c.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
        />
        {categoryAuto && (
          <FieldDescription className="flex items-center gap-1.5">
            <SparklesIcon className="size-3.5 shrink-0 text-primary" aria-hidden="true" />
            Nomga qarab tanlandi — notoʻgʻri boʻlsa oʻzgartiring.
          </FieldDescription>
        )}
        <FieldError>{errors.category_id?.message}</FieldError>
      </Field>

      <div className={profile.showYear ? "grid gap-4 sm:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]" : "grid"}>
        <Field>
          <FieldLabel id="condition-label">Holati</FieldLabel>
          <Controller
            control={control}
            name="condition"
            render={({ field }) => (
              <RadioGroup
                aria-labelledby="condition-label"
                value={field.value}
                onValueChange={field.onChange}
                className="grid-cols-3 gap-2"
              >
                {CONDITIONS.map((c) => (
                  <Label key={c.value} htmlFor={`condition-${c.value}`} className={choiceClass}>
                    <RadioGroupItem id={`condition-${c.value}`} value={c.value} />
                    {c.label}
                  </Label>
                ))}
              </RadioGroup>
            )}
          />
        </Field>

        {profile.showYear && (
          <Field>
            <FieldLabel htmlFor="year">Yili</FieldLabel>
            <Controller
              control={control}
              name="year"
              render={({ field }) => (
                <Input
                  id="year"
                  inputMode="numeric"
                  maxLength={4}
                  placeholder={String(MAX_YEAR - 3)}
                  aria-invalid={errors.year ? true : undefined}
                  value={field.value}
                  onChange={(e) => field.onChange(e.target.value.replace(/\D/g, ""))}
                  onBlur={field.onBlur}
                />
              )}
            />
            <FieldError>{errors.year?.message}</FieldError>
          </Field>
        )}
      </div>

      <Field>
        <div className="flex items-baseline justify-between gap-2">
          <FieldLabel htmlFor="description">Tavsif</FieldLabel>
          <span
            className={
              description.length > DESCRIPTION_MAX
                ? "text-xs text-destructive tabular-nums"
                : "text-xs text-muted-foreground tabular-nums"
            }
            aria-live="polite"
          >
            {description.length}/{DESCRIPTION_MAX}
          </span>
        </div>
        <Textarea
          id="description"
          rows={4}
          placeholder={profile.descriptionHint}
          aria-invalid={errors.description ? true : undefined}
          aria-describedby="description-hint"
          className="min-h-24 resize-y"
          {...register("description")}
        />
        <FieldDescription id="description-hint">Nimalarni yozish kerak: {profile.descriptionHint}</FieldDescription>
        <FieldError>{errors.description?.message}</FieldError>
      </Field>

      {condition !== "new" && (
        <Field>
          <FieldLabel htmlFor={noDefects ? "no_defects" : "defects"}>Nuqsonlar</FieldLabel>
          <Controller
            control={control}
            name="no_defects"
            render={({ field }) => (
              <Label htmlFor="no_defects" className="flex w-fit cursor-pointer items-center gap-2 text-sm font-normal">
                <Checkbox
                  id="no_defects"
                  checked={field.value}
                  onCheckedChange={(v) => field.onChange(v === true)}
                />
                Nuqsonlari yoʻq
              </Label>
            )}
          />
          {!noDefects && (
            <>
              <Textarea
                id="defects"
                rows={2}
                placeholder="Masalan: orqa qopqoqda kichik tirnalish, batareya 85%"
                aria-invalid={errors.defects ? true : undefined}
                className="resize-y"
                {...register("defects")}
              />
              <FieldDescription>Halol tavsif nizolarni kamaytiradi va xaridor ishonchini oshiradi.</FieldDescription>
            </>
          )}
          <FieldError>{errors.defects?.message}</FieldError>
        </Field>
      )}

      <Field>
        <FieldLabel id="mode-label">Sotish usuli</FieldLabel>
        <Controller
          control={control}
          name="mode"
          render={({ field }) => (
            <RadioGroup
              aria-labelledby="mode-label"
              value={field.value}
              onValueChange={field.onChange}
              className="grid gap-2 sm:grid-cols-2"
            >
              <Label htmlFor="mode-offer" className={`${choiceClass} items-start`}>
                <RadioGroupItem id="mode-offer" value="offer" className="mt-0.5" />
                <span className="grid gap-0.5">
                  <span className="font-medium text-foreground">Narx takliflari</span>
                  <span className="text-xs text-muted-foreground">
                    Xaridorlar oʻz narxi va miqdorini taklif qiladi — siz qabul qilasiz, rad
                    etasiz yoki qarshi taklif berasiz. Bir necha dona sotish mumkin.
                  </span>
                </span>
              </Label>
              <Label htmlFor="mode-auction" className={`${choiceClass} items-start`}>
                <RadioGroupItem id="mode-auction" value="auction" className="mt-0.5" />
                <span className="grid gap-0.5">
                  <span className="font-medium text-foreground">Auksion</span>
                  <span className="text-xs text-muted-foreground">
                    Bitta dona, eng yuqori taklif yutadi. Minimal qadam va zaxira narx bilan.
                  </span>
                </span>
              </Label>
            </RadioGroup>
          )}
        />
      </Field>

      {!isOffer && (
        <Field>
          <FieldLabel id="pricing-label">Narx yoʻnalishi</FieldLabel>
          <Controller
            control={control}
            name="pricing"
            render={({ field }) => (
              <RadioGroup
                aria-labelledby="pricing-label"
                value={field.value}
                onValueChange={(v) => {
                  touched.current.pricing = true
                  field.onChange(v)
                }}
                className="grid gap-2 sm:grid-cols-2"
              >
                <Label htmlFor="pricing-asc" className={`${choiceClass} items-start`}>
                  <RadioGroupItem id="pricing-asc" value="ascending" className="mt-0.5" />
                  <span className="grid gap-0.5">
                    <span className="font-medium text-foreground">Oʻsuvchi</span>
                    <span className="text-xs text-muted-foreground">
                      Xaridorlar taklif qoʻyib narxni oshiradi, eng yuqori taklif yutadi.
                    </span>
                  </span>
                </Label>
                <Label htmlFor="pricing-desc" className={`${choiceClass} items-start`}>
                  <RadioGroupItem id="pricing-desc" value="descending" className="mt-0.5" />
                  <span className="grid gap-0.5">
                    <span className="font-medium text-foreground">Pasayuvchi</span>
                    <span className="text-xs text-muted-foreground">
                      Narx vaqt oʻtishi bilan tushadi, birinchi sotib olgan yutadi. Tez sotish
                      uchun.
                    </span>
                  </span>
                </Label>
              </RadioGroup>
            )}
          />
          <FieldDescription>
            {condition === "new"
              ? "Yangi mahsulot uchun pasayuvchi auksion tavsiya etiladi — narx tushib boradi va tez sotiladi."
              : "Ishlatilgan mahsulot uchun oʻsuvchi auksion va «hoziroq sotib olish» narxi tavsiya etiladi."}{" "}
            Auksion boshlanguncha rejimni oʻzgartirish mumkin.
          </FieldDescription>
        </Field>
      )}

      {isDescending && (
        <div className="grid gap-4 sm:grid-cols-3">
          <Field>
            <FieldLabel htmlFor="price_decrement">Pasayish qadami</FieldLabel>
            <Controller
              control={control}
              name="price_decrement"
              render={({ field }) => (
                <PriceInput
                  id="price_decrement"
                  placeholder="Masalan: 50 000"
                  aria-invalid={errors.price_decrement ? true : undefined}
                  value={field.value}
                  onChange={(v) => {
                    touched.current.step = true
                    field.onChange(v)
                  }}
                  onBlur={field.onBlur}
                />
              )}
            />
            <FieldError>{errors.price_decrement?.message}</FieldError>
          </Field>
          <Field>
            <FieldLabel id="drop-interval-label">Har</FieldLabel>
            <Controller
              control={control}
              name="drop_interval"
              render={({ field }) => (
                <Select value={field.value} onValueChange={field.onChange}>
                  <SelectTrigger aria-labelledby="drop-interval-label" className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {DROP_INTERVALS.map((m) => (
                      <SelectItem key={m} value={m}>
                        {DROP_INTERVAL_LABEL[m]}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            />
          </Field>
          <Field>
            <FieldLabel htmlFor="floor_price">Eng past narx</FieldLabel>
            <Controller
              control={control}
              name="floor_price"
              render={({ field }) => (
                <PriceInput
                  id="floor_price"
                  placeholder="Masalan: 900 000"
                  aria-invalid={errors.floor_price ? true : undefined}
                  value={field.value}
                  onChange={(v) => {
                    touched.current.floor = true
                    field.onChange(v)
                  }}
                  onBlur={field.onBlur}
                />
              )}
            />
            <FieldError>{errors.floor_price?.message}</FieldError>
          </Field>
          <FieldDescription className="sm:col-span-3">
            Narx boshlangʻich summadan shu qadam bilan tushadi va eng past narxdan pastga
            tushmaydi. Eng past narx xaridorlarga koʻrsatilmaydi.
          </FieldDescription>
        </div>
      )}

      {isOffer && (
        <Field>
          <FieldLabel htmlFor="quantity">Miqdor (dona)</FieldLabel>
          <Controller
            control={control}
            name="quantity"
            render={({ field }) => (
              <Input
                id="quantity"
                inputMode="numeric"
                className="max-w-40 tabular-nums"
                aria-invalid={errors.quantity ? true : undefined}
                value={field.value > 0 ? String(field.value) : ""}
                onChange={(e) => field.onChange(Number(e.target.value.replace(/D/g, "").slice(0, 5)) || 0)}
                onBlur={field.onBlur}
              />
            )}
          />
          <FieldDescription>
            Bir xil mahsulotdan nechta bor. Xaridor kerakli miqdorni tanlab, dona narxini taklif qiladi.
          </FieldDescription>
          <FieldError>{errors.quantity?.message}</FieldError>
        </Field>
      )}

      <div className="grid gap-4 sm:grid-cols-2">
        <Field>
          <FieldLabel htmlFor="starting_price">
            {isOffer ? "Narx (1 dona uchun)" : "Boshlangʻich narx"}
          </FieldLabel>
          <Controller
            control={control}
            name="starting_price"
            render={({ field }) => (
              <PriceInput
                id="starting_price"
                placeholder="Masalan: 1 500 000"
                aria-invalid={errors.starting_price ? true : undefined}
                value={field.value}
                onChange={field.onChange}
                onBlur={field.onBlur}
              />
            )}
          />
          <FieldDescription>
            {isOffer
              ? "Moʻljal narx — xaridorlar pastroq yoki yuqoriroq taklif qilishi mumkin."
              : "Auksion shu narxdan boshlanadi."}
          </FieldDescription>
          <FieldError>{errors.starting_price?.message}</FieldError>
        </Field>

        <Field>
          <FieldLabel id="duration-label">Muddat</FieldLabel>
          <Controller
            control={control}
            name="duration_days"
            render={({ field }) => (
              <RadioGroup
                aria-labelledby="duration-label"
                aria-describedby="duration-hint"
                value={field.value}
                onValueChange={field.onChange}
                className="grid-cols-3 gap-2"
              >
                {DURATIONS.map((d) => (
                  <Label key={d} htmlFor={`duration-${d}`} className={choiceClass}>
                    <RadioGroupItem id={`duration-${d}`} value={d} />
                    {d} kun
                  </Label>
                ))}
              </RadioGroup>
            )}
          />
          <FieldDescription id="duration-hint">
            {endsAt
              ? `${endsAt} da ${isOffer ? "yopiladi" : "tugaydi"} (Toshkent vaqti)`
              : isOffer
                ? "Eʼlon hoziroq ochiladi."
                : "Auksion hoziroq boshlanadi."}
          </FieldDescription>
        </Field>
      </div>

      {!isOffer && (
        <Field>
          <div className="flex items-start gap-3">
            <Controller
              control={control}
              name="start_later"
              render={({ field }) => (
                <Checkbox
                  id="start_later"
                  checked={field.value}
                  onCheckedChange={(v) => field.onChange(v === true)}
                  className="mt-0.5"
                />
              )}
            />
            <div className="grid gap-1">
              <Label htmlFor="start_later" className="text-sm font-medium text-foreground">
                Keyinroq boshlash
              </Label>
              <FieldDescription>
                Boshlanguncha narx rejimini (oʻsuvchi / pasayuvchi, «hoziroq sotib olish»)
                «Mening mahsulotlarim» sahifasida oʻzgartirishingiz mumkin.
              </FieldDescription>
            </div>
          </div>
          {startLater && (
            <div className="mt-2 grid gap-1.5 sm:max-w-xs">
              <FieldLabel htmlFor="start_at">Boshlanish vaqti</FieldLabel>
              <Input
                id="start_at"
                type="datetime-local"
                aria-invalid={errors.start_at ? true : undefined}
                {...register("start_at")}
              />
              <FieldError>{errors.start_at?.message}</FieldError>
            </div>
          )}
        </Field>
      )}

      <div className="grid gap-4 sm:grid-cols-2">
        <Field>
          <FieldLabel htmlFor="region">Viloyat</FieldLabel>
          <Controller
            control={control}
            name="region_id"
            render={({ field }) => (
              <RegionSelect
                id="region"
                regions={regions}
                value={field.value || undefined}
                invalid={Boolean(errors.region_id)}
                onValueChange={(v) => {
                  field.onChange(v ?? "")
                  // Tuman faqat tanlangan viloyatga tegishli bo'lishi kerak.
                  setValue("district_id", undefined)
                  setLocationSource(null)
                }}
              />
            )}
          />
          <FieldError>{errors.region_id?.message}</FieldError>
        </Field>

        <Field>
          <FieldLabel htmlFor="district">Tuman yoki shahar</FieldLabel>
          <Controller
            control={control}
            name="district_id"
            render={({ field }) => (
              <DistrictSelect
                id="district"
                regionId={regionId ? Number(regionId) : null}
                value={field.value}
                onValueChange={field.onChange}
              />
            )}
          />
        </Field>
      </div>
      {locationSource === "last" && (
        <p className="-mt-3 text-sm text-muted-foreground">Joylashuv oxirgi eʼloningizdan olindi.</p>
      )}

      <CollapsibleSection
        title="Qoʻshimcha maʼlumotlar"
        summary="Komplektatsiya, aniq manzil, video"
        forceOpen={extrasHaveError}
      >
        {(profile.equipment.length > 0 || equipmentValue.length > 0) && (
          <Field>
            <FieldLabel id="equipment-label">Komplektatsiya</FieldLabel>
            <Controller
              control={control}
              name="equipment"
              render={({ field }) => (
                <EquipmentChips
                  labelledBy="equipment-label"
                  options={profile.equipment}
                  value={field.value}
                  onChange={field.onChange}
                />
              )}
            />
            <FieldDescription>Tovar bilan birga beriladiganlarni belgilang.</FieldDescription>
          </Field>
        )}

        <Field>
          <FieldLabel htmlFor="location">Aniq manzil</FieldLabel>
          <Input
            id="location"
            placeholder="Masalan: Chilonzor 9-kvartal, Novza metrosi yonida"
            aria-invalid={errors.location ? true : undefined}
            {...register("location")}
          />
          <FieldDescription>Topshirish joyini kelishishni osonlashtiradi.</FieldDescription>
          <FieldError>{errors.location?.message}</FieldError>
        </Field>

        <Field>
          <FieldLabel htmlFor="video_url">Video havola</FieldLabel>
          <Input
            id="video_url"
            type="url"
            inputMode="url"
            placeholder="https://youtu.be/..."
            aria-invalid={errors.video_url ? true : undefined}
            {...register("video_url")}
          />
          <FieldError>{errors.video_url?.message}</FieldError>
        </Field>
      </CollapsibleSection>

      {!isOffer && !isDescending && (
      <CollapsibleSection
        title="Kengaytirilgan sozlamalar"
        summary={
          startingPrice > 0
            ? `Minimal qadam ${formatSom(effectiveIncrement)}${incrementInput > 0 ? "" : " (avtomatik)"} · ${
                reservePrice > 0 ? `zaxira ${formatSom(reservePrice)}` : "zaxira narxsiz"
              }${buyNowPrice > 0 ? ` · hoziroq sotib olish ${formatSom(buyNowPrice)}` : ""}`
            : "Minimal qadam, zaxira narx, hoziroq sotib olish"
        }
        forceOpen={advancedHasError}
      >
        <Field>
          <FieldLabel htmlFor="minimum_bid_increment">Minimal qadam</FieldLabel>
          <Controller
            control={control}
            name="minimum_bid_increment"
            render={({ field }) => (
              <PriceInput
                id="minimum_bid_increment"
                placeholder={autoIncrement > 0 ? `Avtomatik: ${formatSom(autoIncrement)}` : "Avtomatik"}
                value={field.value}
                onChange={field.onChange}
                onBlur={field.onBlur}
              />
            )}
          />
          <FieldDescription>
            Boʻsh qoldirsangiz — boshlangʻich narxning 5%. Har bir keyingi taklif kamida shuncha oshadi.
          </FieldDescription>
        </Field>

        <Field>
          <FieldLabel htmlFor="reserve_price">Zaxira narx</FieldLabel>
          <Controller
            control={control}
            name="reserve_price"
            render={({ field }) => (
              <PriceInput
                id="reserve_price"
                placeholder="Yoʻq"
                aria-invalid={reserveTooLow || errors.reserve_price ? true : undefined}
                value={field.value}
                onChange={field.onChange}
                onBlur={field.onBlur}
              />
            )}
          />
          <FieldDescription>
            Shu narxga yetmasa mahsulot sotilmaydi. Xaridorlar summani koʻrmaydi, faqat zaxira borligini.
          </FieldDescription>
          <FieldError>
            {reserveTooLow
              ? "Zaxira narx boshlangʻich narxdan past boʻlishi mumkin emas."
              : errors.reserve_price?.message}
          </FieldError>
        </Field>

        <Field>
          <FieldLabel htmlFor="buy_now_price">Hoziroq sotib olish narxi</FieldLabel>
          <Controller
            control={control}
            name="buy_now_price"
            render={({ field }) => (
              <PriceInput
                id="buy_now_price"
                placeholder="Yoʻq"
                aria-invalid={buyNowIssue || errors.buy_now_price ? true : undefined}
                value={field.value}
                onChange={(v) => {
                  touched.current.buyNow = true
                  field.onChange(v)
                }}
                onBlur={field.onBlur}
              />
            )}
          />
          <FieldDescription>
            Xaridor kutmasdan shu narxda darhol sotib olishi mumkin. Zaxira narx qoʻyilgan boʻlsa,
            takliflar unga yetguncha ochiq turadi; zaxirasiz — birinchi taklif tushishi bilan
            yopiladi. Keyin oddiy auksion davom etadi.
          </FieldDescription>
          <FieldError>{buyNowIssue ?? errors.buy_now_price?.message}</FieldError>
        </Field>

        <Field>
          <div className="flex items-start gap-3">
            <Controller
              control={control}
              name="dutch_fallback"
              render={({ field }) => (
                <Checkbox
                  id="dutch_fallback"
                  checked={field.value}
                  onCheckedChange={(v) => field.onChange(v === true)}
                  className="mt-0.5"
                />
              )}
            />
            <div className="grid gap-1">
              <Label htmlFor="dutch_fallback" className="text-sm font-medium text-foreground">
                Taklif tushmasa — pasayuvchi auksionga oʻtkazilsin
              </Label>
              <FieldDescription>
                Auksion taklifsiz tugasa, lot avtomatik 3 kunlik pasayuvchi auksionga oʻtadi:
                narx boshlangʻich summadan har soatda tushib, siz koʻrsatgan eng past narxga
                yetadi. Birinchi sotib olgan xaridor yutadi. Bu sozlama xaridorlarga koʻrinmaydi.
              </FieldDescription>
            </div>
          </div>
          {dutchFallback && (
            <div className="mt-2 grid gap-1.5 sm:max-w-xs">
              <FieldLabel htmlFor="dutch_floor">Eng past narx</FieldLabel>
              <Controller
                control={control}
                name="dutch_floor"
                render={({ field }) => (
                  <PriceInput
                    id="dutch_floor"
                    placeholder="Masalan: 700 000"
                    aria-invalid={errors.dutch_floor ? true : undefined}
                    value={field.value}
                    onChange={field.onChange}
                    onBlur={field.onBlur}
                  />
                )}
              />
              <FieldError>{errors.dutch_floor?.message}</FieldError>
            </div>
          )}
        </Field>
      </CollapsibleSection>
      )}

      {/* Mobil: tugma ekran pastida (tabbar ustida) qotib turadi, qisqa xulosa bilan. */}
      <div className="sticky bottom-16 z-20 -mx-4 flex items-center justify-between gap-3 border-t border-border bg-background px-4 py-3 sm:-mx-6 sm:px-6 md:static md:mx-0 md:border-0 md:bg-transparent md:p-0">
        <div className="grid min-w-0 text-sm md:hidden">
          <span className="truncate font-semibold tabular-nums text-foreground">
            {startingPrice > 0 ? formatSom(startingPrice) : "Narx kiritilmagan"}
          </span>
          <span className="truncate text-xs text-muted-foreground">
            {isOffer ? `${durationDays} kunlik eʼlon · narx takliflari` : `${durationDays} kunlik auksion`}
          </span>
        </div>
        <Button type="submit" size="lg" className="shrink-0">
          Koʻrib chiqish
        </Button>
      </div>
    </form>
  )
}

export { SellForm }
