import { notFound } from "next/navigation"

import { LotDetail } from "@/components/lot/lot-detail"

export default async function LotPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = await params
  const auctionId = Number(id)
  if (!Number.isInteger(auctionId) || auctionId <= 0) notFound()

  return (
    <div className="mx-auto max-w-page px-4 py-6 sm:px-6">
      <LotDetail auctionId={auctionId} />
    </div>
  )
}
