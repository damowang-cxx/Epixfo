import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "航空头程提单监控系统",
  description: "物流航空头程提单监控后台"
};

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
