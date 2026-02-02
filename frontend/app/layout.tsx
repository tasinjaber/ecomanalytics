import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Firebolt Analytics",
  description: "Turn e-commerce data into actionable insights.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen antialiased">{children}</body>
    </html>
  );
}




