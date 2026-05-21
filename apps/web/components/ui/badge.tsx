import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

const variants: Record<string, string> = {
  default: "border-slate-300 bg-slate-100 text-slate-800",
  blue: "border-blue-200 bg-blue-50 text-blue-700",
  green: "border-emerald-200 bg-emerald-50 text-emerald-700",
  amber: "border-amber-200 bg-amber-50 text-amber-800",
  red: "border-red-200 bg-red-50 text-red-700",
  purple: "border-violet-200 bg-violet-50 text-violet-700",
  gray: "border-slate-300 bg-slate-50 text-slate-500",
  cyan: "border-cyan-200 bg-cyan-50 text-cyan-700",
  indigo: "border-indigo-200 bg-indigo-50 text-indigo-700",
  orange: "border-orange-200 bg-orange-50 text-orange-700",
  teal: "border-teal-200 bg-teal-50 text-teal-700",
  pink: "border-pink-200 bg-pink-50 text-pink-700"
};

export function Badge({
  children,
  variant = "default",
  className
}: {
  children: ReactNode;
  variant?: keyof typeof variants;
  className?: string;
}) {
  return (
    <span className={cn("inline-flex h-6 items-center rounded-md border px-2 text-xs font-medium", variants[variant], className)}>
      {children}
    </span>
  );
}
