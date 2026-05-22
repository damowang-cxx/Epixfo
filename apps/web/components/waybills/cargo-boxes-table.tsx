"use client";

import { EmptyState } from "@/components/ui/empty-state";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { compact } from "@/lib/utils";
import type { CargoBox } from "@/lib/types";

function formatDecimal(value?: string | number | null) {
  if (value === null || value === undefined || value === "") return "-";
  const num = Number(value);
  if (!Number.isFinite(num)) return compact(value);
  return num.toFixed(3).replace(/\.?0+$/, "");
}

export function CargoBoxesTable({ boxes }: { boxes: CargoBox[] }) {
  if (!boxes.length) {
    return <EmptyState title="暂无入仓货物明细" description="上传入仓 Excel 文件后会显示实际运输货物。" />;
  }

  return (
    <Table>
      <THead>
        <TR>
          <TH>外箱条码</TH>
          <TH>仓库文件提单号码</TH>
          <TH>品名</TH>
          <TH>数量</TH>
          <TH>重量</TH>
          <TH>体积</TH>
          <TH>重量/方</TH>
          <TH>源行</TH>
        </TR>
      </THead>
      <TBody>
        {boxes.map((item) => (
          <TR key={item.id}>
            <TD className="font-medium">{item.box_no}</TD>
            <TD>{compact(item.warehouse_waybill_no)}</TD>
            <TD>{compact(item.goods_name)}</TD>
            <TD>{compact(item.quantity)}</TD>
            <TD>{formatDecimal(item.weight)}</TD>
            <TD>{formatDecimal(item.volume)}</TD>
            <TD>{formatDecimal(item.weight_volume_ratio)}</TD>
            <TD>{compact(item.source_row_number)}</TD>
          </TR>
        ))}
      </TBody>
    </Table>
  );
}
