import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

export function Panel({
  title,
  action,
  children,
  className
}: {
  title?: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={cn("rounded-md border border-slate-200 bg-white", className)}>
      {(title || action) && (
        <div className="flex min-h-12 items-center justify-between border-b border-slate-200 px-4">
          {title ? <h2 className="text-sm font-semibold text-slate-900">{title}</h2> : <div />}
          {action}
        </div>
      )}
      <div className="p-4">{children}</div>
    </section>
  );
}
