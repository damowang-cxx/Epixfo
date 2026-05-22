"use client";

import { useRef, useState } from "react";
import { Upload } from "lucide-react";
import { Button } from "@/components/ui/button";
import { apiClient } from "@/lib/client-api";
import type { WarehouseFileUploadResult } from "@/lib/types";

export function WarehouseFileUploadButton({
  waybillId,
  label = "上传入仓文件",
  size = "sm",
  variant = "secondary",
  onUploaded,
  onError
}: {
  waybillId: number;
  label?: string;
  size?: "default" | "sm" | "icon";
  variant?: "default" | "secondary" | "ghost" | "danger";
  onUploaded?: (result: WarehouseFileUploadResult) => void;
  onError?: (message: string) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);

  async function upload(file: File) {
    const formData = new FormData();
    formData.append("file", file);
    setUploading(true);
    try {
      const result = await apiClient.postForm<WarehouseFileUploadResult>(
        `/waybills/${waybillId}/warehouse-file`,
        formData
      );
      onUploaded?.(result);
    } catch (err) {
      onError?.(err instanceof Error ? err.message : "入仓文件上传失败");
    } finally {
      setUploading(false);
      if (inputRef.current) inputRef.current.value = "";
    }
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
        disabled={uploading}
      >
        <Upload className="h-4 w-4" />
        {uploading ? "上传中..." : label}
      </Button>
    </>
  );
}
