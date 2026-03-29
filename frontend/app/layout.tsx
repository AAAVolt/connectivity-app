import type { Metadata } from "next";
import { Inter } from "next/font/google";
import Link from "next/link";
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
    <html lang="en">
      <body className={inter.className}>
        <div className="flex min-h-screen flex-col">
          <header className="border-b">
            <div className="container flex h-14 items-center gap-4">
              <h1 className="text-lg font-semibold">Bizkaia Connectivity</h1>
              <nav className="ml-auto flex items-center gap-4 text-sm">
                <Link
                  href="/"
                  className="text-muted-foreground hover:text-foreground"
                >
                  Dashboard
                </Link>
                <Link
                  href="/map"
                  className="text-muted-foreground hover:text-foreground"
                >
                  Map
                </Link>
              </nav>
            </div>
          </header>
          <main className="flex-1">{children}</main>
        </div>
      </body>
    </html>
  );
}
