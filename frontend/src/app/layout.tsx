import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import Sidebar from "@/components/Sidebar";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Project Anarchy",
  description: "Propensity to Sell - Irish Real Estate Analytics",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex bg-slate-50 text-slate-900">
        <Sidebar />
        <main className="flex-1 min-w-0 h-screen overflow-y-auto pt-14 lg:pt-0">
          <div className="max-w-7xl mx-auto p-6 lg:p-8">{children}</div>
        </main>
      </body>
    </html>
  );
}
