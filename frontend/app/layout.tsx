import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

// Yagona shrift — Inter: sarlavha, matn, narx va taymer o'lcham va qalinlik bilan
// ajraladi. U+02BB (oʻ, gʻ) "latin" to'plamida bor.
const inter = Inter({
  variable: "--font-sans",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "Bazart — muddatli auksion marketplace",
  description:
    "Har e'londa majburiy deadline, narx taklifi yoki auksion, kelishuvdan keyin toʻgʻridan-toʻgʻri aloqa.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="uz" className={`${inter.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
