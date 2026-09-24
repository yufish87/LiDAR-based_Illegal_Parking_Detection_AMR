import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
});

export const metadata: Metadata = {
  title: "校園違停監控中心 | 科技執法系統",
  description: "即時監控校園違規停車事件，搭載 3D LiDAR 車輛辨識技術",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-Hant" className={inter.variable}>
      <body className="antialiased">
        {children}
      </body>
    </html>
  );
}
