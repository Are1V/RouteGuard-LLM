import type { Metadata } from "next";
import { IBM_Plex_Mono, Manrope } from "next/font/google";
import { Shell } from "@/components/shell";
import "./globals.css";

const sans = Manrope({ subsets: ["latin", "cyrillic"], variable: "--font-sans" });
const mono = IBM_Plex_Mono({ subsets: ["latin", "cyrillic"], weight: ["400", "500"], variable: "--font-mono" });

export const metadata: Metadata = {
  title: "RouteGuard",
  description: "Reliable routing for multi-model LLM applications.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className={`${sans.variable} ${mono.variable}`}>
        <Shell>{children}</Shell>
      </body>
    </html>
  );
}
