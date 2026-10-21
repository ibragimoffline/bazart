import { SiteHeader } from "@/components/site/header"
import { SiteFooter } from "@/components/site/footer"
import { MobileTabBar } from "@/components/site/mobile-tabbar"
import { AuthProvider } from "@/components/auth/auth-provider"
import { PhoneGateProvider } from "@/components/phone/phone-gate"
import { Toaster } from "@/components/ui/sonner"

export default function ShopLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <div className="flex min-h-full flex-col">
      <SiteHeader />
      <main className="flex-1">{children}</main>
      <SiteFooter />
      {/* Mobil tab-bar ostidagi joy. */}
      <div className="h-16 md:hidden" aria-hidden="true" />
      <MobileTabBar />
      <AuthProvider />
      <PhoneGateProvider />
      <Toaster />
    </div>
  )
}
