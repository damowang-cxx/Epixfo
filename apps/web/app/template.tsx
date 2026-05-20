import { AppShell } from "@/components/layout/app-shell";

export default function Template({ children }: { children: React.ReactNode }) {
  return <AppShell>{children}</AppShell>;
}
