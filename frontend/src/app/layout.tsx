import type { Metadata } from "next";
import { EB_Garamond, IBM_Plex_Mono, IM_Fell_English_SC } from "next/font/google";
import "./globals.css";

const garamond = EB_Garamond({ variable: "--font-serif", subsets: ["latin"], style: ["normal", "italic"] });
const mono = IBM_Plex_Mono({ variable: "--font-mono", subsets: ["latin"], weight: ["400", "500", "600"] });
// A 1600s type, not a costume-pirate face: real ink spread, genuine small caps.
const chart = IM_Fell_English_SC({ variable: "--font-chart", subsets: ["latin"], weight: "400" });

export const metadata: Metadata = {
  title: "Diplomacy",
  description: "Human vs AI Diplomacy",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${garamond.variable} ${mono.variable} ${chart.variable}`} style={{ height: "100%" }}>
      <body style={{ height: "100%", margin: 0 }}>{children}</body>
    </html>
  );
}
