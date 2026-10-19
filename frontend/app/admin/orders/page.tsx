import { AdminOrdersTable } from "@/components/admin/orders-table"

export default function AdminOrdersPage() {
  return (
    <section className="grid gap-5">
      <div>
        <h1 className="text-2xl font-semibold text-foreground">Buyurtmalar</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {"Barcha buyurtmalar va ularning holati."}
        </p>
      </div>
      <AdminOrdersTable />
    </section>
  )
}
