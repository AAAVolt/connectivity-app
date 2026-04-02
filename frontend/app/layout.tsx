import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { AppSidebar } from "@/components/app-sidebar";
import { LanguageProvider } from "@/lib/i18n";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Bizkaia Connectivity",
  description: "Transport connectivity analysis for Bizkaia",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="es">
      <body className={inter.className}>
        <LanguageProvider>
          <AppSidebar>{children}</AppSidebar>
        </LanguageProvider>
      </body>
    </html>
  );
}
