import type { Metadata, Viewport } from "next";
import { BottomNav } from "@/components/ui";
import { AuthProvider } from "@/lib/auth";
import "./globals.css";

export const metadata: Metadata = {
  title: "EQura — every artist deserves a stage",
  description: "Find gigs, book performers and grow your live-music network.",
  appleWebApp: { capable: true, title: "EQura", statusBarStyle: "black-translucent" },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover", // lets env(safe-area-inset-*) work on notched phones
  themeColor: "#0e0c13",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <AuthProvider>
          <div className="app">{children}</div>
          <BottomNav />
        </AuthProvider>
      </body>
    </html>
  );
}
