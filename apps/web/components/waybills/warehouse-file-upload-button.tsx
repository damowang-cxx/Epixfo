"use client";

import { useRef, useState } from "react";
import { Upload } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { ApiError, apiClient } from "@/lib/client-api";
import type { WarehouseBoxConflict, WarehouseFileUploadResult, WarehouseUploadIntegrityIssue } from "@/lib/types";

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

interface WarehouseUploadIntegrityDetail {
  error_code: "warehouse_upload_integrity_failed";
  file_name?: string;
  warehouse_no?: string;
  expected_count?: number;
  uploaded_count?: number;
  message?: string;
  issues: WarehouseUploadIntegrityIssue[];
}

function isWarehouseUploadIntegrityDetail(detail: unknown): detail is WarehouseUploadIntegrityDetail {
  return (
    Boolean(detail) &&
    typeof detail === "object" &&
    (detail as { error_code?: unknown }).error_code === "warehouse_upload_integrity_failed" &&
    Array.isArray((detail as { issues?: unknown }).issues)
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
  const [integrityFailure, setIntegrityFailure] = useState<WarehouseUploadIntegrityDetail | null>(null);

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
      setIntegrityFailure(null);
      onUploaded?.(result);
    } catch (err) {
      if (err instanceof ApiError && err.status === 409 && isWarehouseConflictDetail(err.detail)) {
        setPendingFile(file);
        setConflicts(err.detail.conflicts);
        setSelectedBoxNos(new Set(err.detail.conflicts.map((item) => item.box_no)));
        return;
      }
      if (err instanceof ApiError && err.status === 400 && isWarehouseUploadIntegrityDetail(err.detail)) {
        setIntegrityFailure(err.detail);
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
      <Dialog open={Boolean(integrityFailure)} onOpenChange={(open) => !open && setIntegrityFailure(null)}>
        <DialogContent className="w-[min(760px,calc(100vw-32px))]">
          <DialogTitle className="pr-10 text-base font-semibold text-slate-900">入仓文件外箱数量校验失败</DialogTitle>
          {integrityFailure ? (
            <div className="mt-3 space-y-3 text-sm text-slate-600">
              <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-red-800">
                {integrityFailure.message || "Excel 外箱条码数量与本次成功写入数量不一致。"}
              </div>
              <div className="flex flex-wrap gap-3 text-slate-700">
                <span>文件：{integrityFailure.file_name || "-"}</span>
                <span>入仓号：{integrityFailure.warehouse_no || "-"}</span>
                <span>Excel 条码数：{integrityFailure.expected_count ?? "-"}</span>
                <span>成功写入数：{integrityFailure.uploaded_count ?? "-"}</span>
              </div>
              {integrityFailure.issues.length ? (
                <Table>
                  <THead>
                    <TR>
                      <TH>Excel 行号</TH>
                      <TH>外箱条码</TH>
                      <TH>说明</TH>
                    </TR>
                  </THead>
                  <TBody>
                    {integrityFailure.issues.map((issue) => (
                      <TR key={`${issue.row_number}-${issue.box_no}`}>
                        <TD>{issue.row_number}</TD>
                        <TD className="font-medium text-slate-900">{issue.box_no}</TD>
                        <TD>{issue.message}</TD>
                      </TR>
                    ))}
                  </TBody>
                </Table>
              ) : null}
              <div className="flex justify-end">
                <Button type="button" onClick={() => setIntegrityFailure(null)}>
                  知道了
                </Button>
              </div>
            </div>
          ) : null}
        </DialogContent>
      </Dialog>
    </>
  );
}
