"use client"

import * as React from "react"
import { ImagePlusIcon, StarIcon, XIcon } from "lucide-react"

import { ALLOWED_IMAGE_TYPES, MAX_IMAGE_BYTES, MAX_IMAGES } from "@/lib/listing"
import { cn } from "@/lib/utils"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"

export type PickedImage = {
  id: string
  file: File
  /** URL.createObjectURL — olib tashlanganda bo'shatiladi. */
  url: string
}

let seq = 0

/** Tanlangan fayllarni server qoidalari bo'yicha ajratadi: qabul qilinganlar + xato matni. */
function acceptFiles(files: File[], current: number): { accepted: PickedImage[]; error: string | null } {
  const accepted: PickedImage[] = []
  const problems = new Set<string>()
  for (const file of files) {
    if (current + accepted.length >= MAX_IMAGES) {
      problems.add(`Koʻpi bilan ${MAX_IMAGES} ta rasm yuklash mumkin.`)
      break
    }
    if (!ALLOWED_IMAGE_TYPES.includes(file.type)) {
      problems.add("Faqat JPG, PNG, WebP yoki GIF rasm yuklang.")
      continue
    }
    if (file.size > MAX_IMAGE_BYTES) {
      problems.add("Har bir rasm 5 MB dan oshmasin.")
      continue
    }
    accepted.push({ id: `img-${++seq}`, file, url: URL.createObjectURL(file) })
  }
  return { accepted, error: problems.size ? [...problems].join(" ") : null }
}

/**
 * Rasm tanlash: sudrab tashlash yoki tugma orqali, bir nechta fayl, oldindan ko'rish.
 * Birinchi rasm — asosiy (katalog kartasida chiqadi). Brauzerning standart fayl
 * tugmasi ishlatilmaydi — u tizim tilida ("Выберите файл") chiqib qolardi.
 */
function ImageDropzone({
  id,
  images,
  onChange,
  invalid,
  describedBy,
}: {
  id: string
  images: PickedImage[]
  onChange: (next: PickedImage[]) => void
  invalid?: boolean
  describedBy?: string
}) {
  const inputRef = React.useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  const add = (files: File[]) => {
    const { accepted, error: problem } = acceptFiles(files, images.length)
    setError(problem)
    if (accepted.length) onChange([...images, ...accepted])
  }

  const remove = (target: PickedImage) => {
    URL.revokeObjectURL(target.url)
    onChange(images.filter((i) => i.id !== target.id))
  }

  const makePrimary = (target: PickedImage) => {
    onChange([target, ...images.filter((i) => i.id !== target.id)])
  }

  const full = images.length >= MAX_IMAGES

  return (
    <div className="grid gap-3">
      <input
        ref={inputRef}
        id={id}
        type="file"
        accept={ALLOWED_IMAGE_TYPES.join(",")}
        multiple
        className="sr-only"
        tabIndex={-1}
        aria-hidden="true"
        onChange={(e) => {
          add(Array.from(e.target.files ?? []))
          // Bir xil faylni qayta tanlash ham change hodisasini bersin.
          e.target.value = ""
        }}
      />

      <button
        type="button"
        disabled={full}
        aria-describedby={describedBy}
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault()
          if (!full) setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault()
          setDragging(false)
          if (!full) add(Array.from(e.dataTransfer.files))
        }}
        className={cn(
          "flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-input bg-card px-4 py-8 text-center outline-none transition-colors",
          "hover:border-primary hover:bg-primary/5 focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50",
          "disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:border-input disabled:hover:bg-card",
          dragging && "border-primary bg-primary/5",
          invalid && "border-destructive"
        )}
      >
        <ImagePlusIcon className="size-6 text-muted-foreground" aria-hidden="true" />
        <span className="text-sm font-medium text-foreground">
          {full ? "Rasmlar soni toʻldi" : "Rasmlarni shu yerga tashlang yoki tanlang"}
        </span>
        <span className="text-xs text-muted-foreground">
          JPG, PNG, WebP · har biri 5 MB gacha · {images.length}/{MAX_IMAGES}
        </span>
      </button>

      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}

      {images.length > 0 && (
        <ul className="grid grid-cols-3 gap-2 sm:grid-cols-5" aria-label="Tanlangan rasmlar">
          {images.map((img, index) => (
            <li
              key={img.id}
              className="group relative aspect-square overflow-hidden rounded-md border border-border bg-muted"
            >
              {/* eslint-disable-next-line @next/next/no-img-element -- lokal blob URL, next/image optimallashtira olmaydi */}
              <img src={img.url} alt={`Rasm ${index + 1}`} className="size-full object-cover" />
              {index === 0 ? (
                <Badge className="absolute bottom-1.5 left-1.5">Asosiy</Badge>
              ) : (
                <Button
                  type="button"
                  size="icon-sm"
                  variant="secondary"
                  className="absolute bottom-1.5 left-1.5"
                  aria-label={`${index + 1}-rasmni asosiy qilish`}
                  onClick={() => makePrimary(img)}
                >
                  <StarIcon aria-hidden="true" />
                </Button>
              )}
              <Button
                type="button"
                size="icon-sm"
                variant="secondary"
                className="absolute top-1.5 right-1.5"
                aria-label={`${index + 1}-rasmni olib tashlash`}
                onClick={() => remove(img)}
              >
                <XIcon aria-hidden="true" />
              </Button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

export { ImageDropzone }
