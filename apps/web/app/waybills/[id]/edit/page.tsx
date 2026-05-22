"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/ui/page-header";
import { WaybillForm } from "@/components/waybills/waybill-form";
import { apiClient } from "@/lib/client-api";
import type { Waybill } from "@/lib/types";

export default function WaybillEditPage() {
  const params = useParams<{ id: string }>();
  const id = Array.isArray(params.id) ? params.id[0] : params.id;
  const [waybill, setWaybill] = useState<Waybill | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!id) return;
    apiClient
      .get<Waybill>(`/waybills/${id}`)
      .then(setWaybill)
      .catch((err) => setError(err instanceof Error ? err.message : "提单加载失败"));
  }, [id]);

  return (
    <>
      <PageHeader
        title={waybill ? `编辑提单 ${waybill.waybill_no}` : "编辑提单"}
        description="修改提单基础信息、计划航班、收件人、费用与备注。"
        action={
          id ? (
            <Button asChild variant="secondary">
              <Link href={`/waybills/${id}`}>
                <ArrowLeft className="h-4 w-4" />
                返回详情
              </Link>
            </Button>
          ) : null
        }
      />
      {error ? <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div> : null}
      {!error && !waybill ? <div className="text-sm text-slate-500">正在加载提单...</div> : null}
      {waybill ? <WaybillForm waybill={waybill} /> : null}
    </>
  );
}
