import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "CNAS | Criminal Network Analysis System",
  description: "Air-gapped POLE graph intelligence platform.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="font-mono min-h-screen bg-tactical-bg text-slate-200 antialiased">
        {children}
      </body>
    </html>
  );
}
