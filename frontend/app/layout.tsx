import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { cookies } from "next/headers";
import { SidebarLayout } from "@/components/sidebar-layout";
import { QueryProvider } from "@/components/query-provider";
import { LanguageProvider } from "@/lib/i18n";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Bizkaia Connectivity",
  description: "Transport connectivity analysis for Bizkaia",
  icons: {
    icon: [
      { url: "/favicon.ico", sizes: "any" },
      { url: "/favicon-16x16.png", sizes: "16x16", type: "image/png" },
      { url: "/favicon-32x32.png", sizes: "32x32", type: "image/png" },
    ],
    apple: "/apple-touch-icon.png",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const cookieStore = cookies();
  const sidebarOpen = cookieStore.get("sidebar_state")?.value !== "false";

  return (
    <html lang="es">
      <body className={inter.className}>
        <QueryProvider>
          <LanguageProvider>
            <SidebarLayout defaultOpen={sidebarOpen}>
              {children}
            </SidebarLayout>
          </LanguageProvider>
        </QueryProvider>
      </body>
    </html>
  );
}
