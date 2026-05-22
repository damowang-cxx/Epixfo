import type { WarehouseFileUploadResult } from "@/lib/types";

const MAX_VISIBLE_ERRORS = 5;

export function formatWarehouseUploadMessage(result: WarehouseFileUploadResult) {
  const skippedText = result.skipped_count ? `，跳过空行 ${result.skipped_count} 行` : "";
  const errors = result.errors || [];
  const errorText = errors.length
    ? `，失败 ${errors.length} 行：${errors
        .slice(0, MAX_VISIBLE_ERRORS)
        .map((item) => `第 ${item.row_number} 行（${item.message}）`)
        .join("；")}${errors.length > MAX_VISIBLE_ERRORS ? `；另 ${errors.length - MAX_VISIBLE_ERRORS} 行` : ""}`
    : "";

  return `入仓文件已上传：${result.warehouse_no}，绑定 ${result.success_count} 个外箱条码${skippedText}${errorText}。`;
}
