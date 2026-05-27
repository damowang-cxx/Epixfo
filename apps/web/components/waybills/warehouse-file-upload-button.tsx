"use client";

import { useRef, useState } from "react";
import { Upload } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { ApiError, apiClient } from "@/lib/client-api";
import type { WarehouseBoxConflict, WarehouseFileUploadResult } from "@/lib/types";

function isWarehouseConflictDetail(detail: unknown): detail is {
  error_code: "warehouse_box_conflicts";
  conflicts: WarehouseBoxConflict[];
} {
  return (
    Boolean(detail) &&
    typeof detail === "object" &&
    (detail as { error_code?: unknown }).error_code === "warehouse_box_conflicts" &&
    Array.isArray((detail as { conflicts?: unknown }).conflicts)
  );
}

export function WarehouseFileUploadButton({
  waybillId,
  uploadPath,
  label = "上传入仓文件",
  size = "sm",
  variant = "secondary",
  onUploaded,
  onError
}: {
  waybillId?: number;
  uploadPath?: string;
  label?: string;
  size?: "default" | "sm" | "icon";
  variant?: "default" | "secondary" | "ghost" | "danger";
  onUploaded?: (result: WarehouseFileUploadResult) => void;
  onError?: (message: string) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const [conflicts, setConflicts] = useState<WarehouseBoxConflict[]>([]);
  const [selectedBoxNos, setSelectedBoxNos] = useState<Set<string>>(new Set());

  async function upload(file: File, forceMoveBoxNos: string[] = [], skipConflictBoxNos: string[] = []) {
    const formData = new FormData();
    formData.append("file", file);
    forceMoveBoxNos.forEach((boxNo) => formData.append("force_move_box_nos", boxNo));
    skipConflictBoxNos.forEach((boxNo) => formData.append("skip_conflict_box_nos", boxNo));
    setUploading(true);
    try {
      const result = await apiClient.postForm<WarehouseFileUploadResult>(
        uploadPath || `/waybills/${waybillId}/warehouse-file`,
        formData
      );
      setPendingFile(null);
      setConflicts([]);
      setSelectedBoxNos(new Set());
      onUploaded?.(result);
    } catch (err) {
      if (err instanceof ApiError && err.status === 409 && isWarehouseConflictDetail(err.detail)) {
        setPendingFile(file);
        setConflicts(err.detail.conflicts);
        setSelectedBoxNos(new Set(err.detail.conflicts.map((item) => item.box_no)));
        return;
      }
      onError?.(err instanceof Error ? err.message : "入仓文件上传失败");
    } finally {
      setUploading(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  function toggleConflict(boxNo: string, checked: boolean) {
    setSelectedBoxNos((prev) => {
      const next = new Set(prev);
      if (checked) next.add(boxNo);
      else next.delete(boxNo);
      return next;
    });
  }

  function closeConflictDialog() {
    setPendingFile(null);
    setConflicts([]);
    setSelectedBoxNos(new Set());
  }

  return (
    <>
      <input
        ref={inputRef}
        type="file"
        accept=".xlsx"
        className="hidden"
        onChange={(event) => {
          const file = event.target.files?.[0];
          if (file) void upload(file);
        }}
      />
      <Button
        type="button"
        variant={variant}
        size={size}
        onClick={() => inputRef.current?.click()}
        disabled={uploading || (!uploadPath && !waybillId)}
      >
        <Upload className="h-4 w-4" />
        {uploading ? "上传中..." : label}
      </Button>
      <Dialog open={conflicts.length > 0} onOpenChange={(open) => !open && closeConflictDialog()}>
        <DialogContent className="w-[min(880px,calc(100vw-32px))]">
          <DialogTitle className="pr-10 text-base font-semibold text-slate-900">外箱条码已绑定到其他提单</DialogTitle>
          <div className="space-y-3 text-sm text-slate-600">
            <p>勾选需要转移到本次入仓号的外箱条码，未勾选的箱号会保留原绑定。</p>
            <Table>
              <THead>
                <TR>
                  <TH>选择</TH>
                  <TH>外箱条码</TH>
                  <TH>当前提单</TH>
                  <TH>当前入仓号</TH>
                  <TH>目标提单</TH>
                  <TH>目标入仓号</TH>
                </TR>
              </THead>
              <TBody>
                {conflicts.map((item) => (
                  <TR key={item.box_no}>
                    <TD>
                      <input
                        type="checkbox"
                        checked={selectedBoxNos.has(item.box_no)}
                        onChange={(event) => toggleConflict(item.box_no, event.target.checked)}
                      />
                    </TD>
                    <TD className="font-medium text-slate-900">{item.box_no}</TD>
                    <TD>{item.current_waybill_no || "-"}</TD>
                    <TD>{item.current_warehouse_no || "-"}</TD>
                    <TD>{item.target_waybill_no}</TD>
                    <TD>{item.target_warehouse_no}</TD>
                  </TR>
                ))}
              </TBody>
            </Table>
            <div className="flex justify-end gap-2">
              <Button type="button" variant="secondary" onClick={closeConflictDialog} disabled={uploading}>
                取消
              </Button>
              <Button
                type="button"
                disabled={uploading || !pendingFile}
                onClick={() =>
                  pendingFile &&
                  void upload(
                    pendingFile,
                    Array.from(selectedBoxNos),
                    conflicts.map((item) => item.box_no).filter((boxNo) => !selectedBoxNos.has(boxNo))
                  )
                }
              >
                确认并继续上传
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
