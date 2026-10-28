import { notFound } from "next/navigation"

import { OfferListingDetail } from "@/components/offer/offer-listing-detail"

export default async function OfferListingPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = await params
  const itemId = Number(id)
  if (!Number.isInteger(itemId) || itemId <= 0) notFound()

  return (
    <div className="mx-auto max-w-page px-4 py-6 sm:px-6">
      <OfferListingDetail itemId={itemId} />
    </div>
  )
}
