import type { Metadata } from "next";
import { Barlow_Condensed } from "next/font/google";
import "./globals.css";

const display = Barlow_Condensed({
  subsets: ["latin"],
  weight: ["600", "700", "800"],
  variable: "--font-display",
});

export const metadata: Metadata = {
  title: "Repo2Web",
  description: "Turn GitHub repositories into running apps",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className={`${display.variable} bg-gray-50 min-h-screen`}>{children}</body>
    </html>
  );
}
