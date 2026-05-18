import type { Metadata } from "next";
import "./globals.css";
import { cn } from "@/lib/utils";
import { Toaster } from "@/components/ui/toaster";

export const metadata: Metadata = {
  title: "PlaceReady",
  description: "AI-Driven Placement Readiness Platform",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={cn("font-sans")}>
      <body className="font-sans antialiased text-foreground bg-background">
        {children}
        <Toaster />
      </body>
    </html>
  );
}
