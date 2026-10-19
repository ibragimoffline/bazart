import type { Metadata } from "next";
import { Inter, Space_Grotesk, Geist_Mono } from "next/font/google";
import "./globals.css";

// Matn (body) — o'qishga qulay, neytral grotesk.
const inter = Inter({
  variable: "--font-sans",
  subsets: ["latin"],
  display: "swap",
});

// Sarlavha (heading) — xarakterli, matndan aniq ajralib turadi.
const spaceGrotesk = Space_Grotesk({
  variable: "--font-heading",
  subsets: ["latin"],
  display: "swap",
});

// Raqamlar/kod uchun monospace (narx ustunlarini tekislashda ham asqotadi).
const geistMono = Geist_Mono({
  variable: "--font-mono",
  subsets: ["latin"],
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
    <html
      lang="uz"
      className={`${inter.variable} ${spaceGrotesk.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
