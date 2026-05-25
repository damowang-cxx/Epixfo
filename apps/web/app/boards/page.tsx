"use client";

import { useCallback, useEffect, useState } from "react";
import { Plus, Save, Trash2, Unlink } from "lucide-react";
import { LifecycleBadge } from "@/components/ui/status-badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { Panel } from "@/components/ui/panel";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { ApiError, apiClient } from "@/lib/client-api";
import { compact } from "@/lib/utils";
import type { BoardWaybill, PageResponse, WaybillBoard } from "@/lib/types";

function parseWaybillInput(value: string) {
  return value
    .split(/[\s,，;；]+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function formatDecimal(value?: string | number | null) {
  if (value === null || value === undefined || value === "") return "-";
  const num = Number(value);
  if (!Number.isFinite(num)) return compact(value);
  return num.toFixed(3).replace(/\.?0+$/, "");
}

function sumBookedVolume(waybills: WaybillBoard["waybills"]) {
  return waybills.reduce((total, item) => {
    const value = Number(item.booked_volume);
    return Number.isFinite(value) ? total + value : total;
  }, 0);
}

function mergeWaybillInput(current: string, waybillNos: string[]) {
  const merged: string[] = [];
  const seen = new Set<string>();
  for (const waybillNo of [...parseWaybillInput(current), ...waybillNos]) {
    if (seen.has(waybillNo)) continue;
    seen.add(waybillNo);
    merged.push(waybillNo);
  }
  return merged.join("\n");
}

function formatApiError(error: unknown) {
  if (error instanceof ApiError && error.detail && typeof error.detail === "object") {
    const detail = error.detail as { message?: unknown; errors?: Array<{ waybill_no?: string; message?: string }> };
    if (Array.isArray(detail.errors) && detail.errors.length > 0) {
      const lines = detail.errors.map((item) => `${item.waybill_no || "-"}：${item.message || "无法绑定"}`);
      return `${typeof detail.message === "string" ? detail.message : "部分提单无法绑定"}\n${lines.join("\n")}`;
    }
  }
  return error instanceof Error ? error.message : "操作失败";
}

export default function BoardsPage() {
  const [data, setData] = useState<PageResponse<WaybillBoard> | null>(null);
  const [page, setPage] = useState(1);
  const [message, setMessage] = useState("");
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [createDialogMessage, setCreateDialogMessage] = useState("");
  const [newActualBoardNo, setNewActualBoardNo] = useState("");
  const [newWaybillInput, setNewWaybillInput] = useState("");
  const [candidateData, setCandidateData] = useState<PageResponse<BoardWaybill> | null>(null);
  const [candidatePage, setCandidatePage] = useState(1);
  const [candidateSearchDraft, setCandidateSearchDraft] = useState("");
  const [candidateSearch, setCandidateSearch] = useState("");
  const [selectedCandidateNos, setSelectedCandidateNos] = useState<string[]>([]);
  const [editingBoardId, setEditingBoardId] = useState<number | null>(null);
  const [actualDraft, setActualDraft] = useState("");
  const [appendBoardId, setAppendBoardId] = useState<number | null>(null);
  const [appendInput, setAppendInput] = useState("");
  const [saving, setSaving] = useState(false);

  const load = useCallback(() => {
    apiClient.get<PageResponse<WaybillBoard>>(`/boards?page=${page}&page_size=20`).then(setData);
  }, [page]);

  const loadCandidates = useCallback(() => {
    const params = new URLSearchParams({
      page: String(candidatePage),
      page_size: "20"
    });
    if (candidateSearch) params.set("waybill_no", candidateSearch);
    apiClient
      .get<PageResponse<BoardWaybill>>(`/boards/bind-candidates?${params.toString()}`)
      .then(setCandidateData)
      .catch((error) => setCreateDialogMessage(formatApiError(error)));
  }, [candidatePage, candidateSearch]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (createDialogOpen) {
      loadCandidates();
    }
  }, [createDialogOpen, loadCandidates]);

  function resetCreateDialogState() {
    setNewActualBoardNo("");
    setNewWaybillInput("");
    setCandidateSearchDraft("");
    setCandidateSearch("");
    setCandidatePage(1);
    setCandidateData(null);
    setSelectedCandidateNos([]);
    setCreateDialogMessage("");
  }

  function openCreateDialog() {
    resetCreateDialogState();
    setCreateDialogOpen(true);
  }

  function closeCreateDialog() {
    if (saving) return;
    setCreateDialogOpen(false);
    resetCreateDialogState();
  }

  async function createBoard() {
    const waybill_nos = parseWaybillInput(newWaybillInput);
    if (!waybill_nos.length) {
      setCreateDialogMessage("请录入至少一个提单号。");
      return;
    }
    try {
      setSaving(true);
      const board = await apiClient.post<WaybillBoard>("/boards", {
        actual_board_no: newActualBoardNo.trim() || null,
        waybill_nos
      });
      setMessage(`已创建板号 ${board.board_no}。`);
      setCreateDialogOpen(false);
      resetCreateDialogState();
      setPage(1);
      load();
    } catch (error) {
      setCreateDialogMessage(formatApiError(error));
    } finally {
      setSaving(false);
    }
  }

  function searchCandidates() {
    setCandidatePage(1);
    setCandidateSearch(candidateSearchDraft.trim());
  }

  function clearCandidateSearch() {
    setCandidateSearchDraft("");
    setCandidateSearch("");
    setCandidatePage(1);
  }

  function toggleCandidate(waybillNo: string) {
    setSelectedCandidateNos((prev) =>
      prev.includes(waybillNo) ? prev.filter((item) => item !== waybillNo) : [...prev, waybillNo]
    );
  }

  function toggleCurrentCandidatePage() {
    const pageWaybillNos = (candidateData?.items || []).map((item) => item.waybill_no);
    if (!pageWaybillNos.length) return;
    const allSelected = pageWaybillNos.every((waybillNo) => selectedCandidateNos.includes(waybillNo));
    setSelectedCandidateNos((prev) => {
      if (allSelected) {
        return prev.filter((waybillNo) => !pageWaybillNos.includes(waybillNo));
      }
      const next = [...prev];
      for (const waybillNo of pageWaybillNos) {
        if (!next.includes(waybillNo)) next.push(waybillNo);
      }
      return next;
    });
  }

  function addSelectedToNewBoardInput() {
    if (!selectedCandidateNos.length) {
      setCreateDialogMessage("请先选择至少一个可绑定提单。");
      return;
    }
    setNewWaybillInput((prev) => mergeWaybillInput(prev, selectedCandidateNos));
    setCreateDialogMessage(`已将 ${selectedCandidateNos.length} 个提单号加入新建板号输入框。`);
  }

  function startEdit(board: WaybillBoard) {
    setEditingBoardId(board.id);
    setActualDraft(board.actual_board_no || "");
  }

  function startAppend(board: WaybillBoard) {
    setAppendBoardId(board.id);
    setAppendInput("");
    setSelectedCandidateNos([]);
    setCandidatePage(1);
  }

  function cancelAppend() {
    setAppendBoardId(null);
    setAppendInput("");
    setSelectedCandidateNos([]);
    setCandidatePage(1);
  }

  async function saveActualBoardNo(board: WaybillBoard) {
    try {
      setSaving(true);
      const updated = await apiClient.patch<WaybillBoard>(`/boards/${board.id}`, {
        actual_board_no: actualDraft.trim() || null
      });
      setData((prev) =>
        prev ? { ...prev, items: prev.items.map((item) => (item.id === updated.id ? updated : item)) } : prev
      );
      setMessage(`板号 ${updated.board_no} 已更新。`);
      setEditingBoardId(null);
      setActualDraft("");
    } catch (error) {
      setMessage(formatApiError(error));
    } finally {
      setSaving(false);
    }
  }

  async function appendWaybills(board: WaybillBoard) {
    const waybill_nos = parseWaybillInput(appendInput);
    if (!waybill_nos.length) {
      setMessage("请录入至少一个提单号。");
      return;
    }
    try {
      setSaving(true);
      const updated = await apiClient.post<WaybillBoard>(`/boards/${board.id}/waybills`, { waybill_nos });
      setData((prev) =>
        prev ? { ...prev, items: prev.items.map((item) => (item.id === updated.id ? updated : item)) } : prev
      );
      setMessage(`板号 ${updated.board_no} 已追加提单。`);
      cancelAppend();
    } catch (error) {
      setMessage(formatApiError(error));
    } finally {
      setSaving(false);
    }
  }

  async function unbindWaybill(board: WaybillBoard, waybillId: number, waybillNo: string) {
    if (!window.confirm(`确认将提单 ${waybillNo} 从板号 ${board.board_no} 解绑吗？`)) return;
    try {
      setSaving(true);
      await apiClient.delete<void>(`/boards/${board.id}/waybills/${waybillId}`);
      setData((prev) =>
        prev
          ? {
              ...prev,
              items: prev.items.map((item) => {
                if (item.id !== board.id) return item;
                const waybills = item.waybills.filter((waybill) => waybill.id !== waybillId);
                return {
                  ...item,
                  waybills,
                  member_count: waybills.length,
                  total_booked_volume: sumBookedVolume(waybills)
                };
              })
            }
          : prev
      );
      setMessage(`提单 ${waybillNo} 已解绑。`);
      load();
      if (createDialogOpen) {
        loadCandidates();
      }
    } catch (error) {
      setMessage(formatApiError(error));
    } finally {
      setSaving(false);
    }
  }

  async function deleteBoard(board: WaybillBoard) {
    if (!window.confirm(`确认删除空板 ${board.board_no} 吗？`)) return;
    try {
      setSaving(true);
      await apiClient.delete<void>(`/boards/${board.id}`);
      const shouldMoveToPreviousPage = (data?.items.length || 0) <= 1 && page > 1;
      setData((prev) =>
        prev
          ? {
              ...prev,
              items: prev.items.filter((item) => item.id !== board.id),
              total: Math.max(0, prev.total - 1)
            }
          : prev
      );
      setMessage(`板号 ${board.board_no} 已删除。`);
      if (shouldMoveToPreviousPage) {
        setPage((prev) => Math.max(1, prev - 1));
      } else {
        load();
      }
    } catch (error) {
      setMessage(formatApiError(error));
    } finally {
      setSaving(false);
    }
  }

  const candidateItems = candidateData?.items || [];
  const allCurrentCandidatePageSelected =
    candidateItems.length > 0 && candidateItems.every((item) => selectedCandidateNos.includes(item.waybill_no));

  return (
    <>
      <PageHeader
        title="板号管理"
        description="将存活周期内且收件人一致的提单绑定到同一个板号"
        action={
          <Button type="button" onClick={openCreateDialog}>
            <Plus className="h-4 w-4" />
            新建板号
          </Button>
        }
      />
      {message ? (
        <div className="mb-4 whitespace-pre-line rounded-md border border-blue-200 bg-blue-50 px-3 py-2 text-sm text-blue-700">
          {message}
        </div>
      ) : null}

      <Dialog open={createDialogOpen} onOpenChange={(open) => (open ? setCreateDialogOpen(true) : closeCreateDialog())}>
        <DialogContent className="max-h-[calc(100vh-48px)] w-[min(1040px,calc(100vw-32px))] overflow-y-auto">
          <DialogTitle className="pr-10 text-base font-semibold text-slate-900">新建板号</DialogTitle>
          {createDialogMessage ? (
            <div className="mt-4 whitespace-pre-line rounded-md border border-blue-200 bg-blue-50 px-3 py-2 text-sm text-blue-700">
              {createDialogMessage}
            </div>
          ) : null}

          <div className="mt-4 space-y-4">
            <div className="grid gap-3 lg:grid-cols-[260px_1fr_auto]">
              <Input
                value={newActualBoardNo}
                onChange={(event) => setNewActualBoardNo(event.target.value)}
                placeholder="实际板号 ID（可选）"
              />
              <Textarea
                value={newWaybillInput}
                onChange={(event) => setNewWaybillInput(event.target.value)}
                placeholder="录入或粘贴多个提单号，可用换行、逗号或空格分隔"
                className="min-h-20"
              />
              <Button type="button" disabled={saving} onClick={() => void createBoard()}>
                <Plus className="h-4 w-4" />
                生成板号
              </Button>
            </div>

            <div className="border-t border-slate-100 pt-4">
              <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
                <div className="flex flex-wrap items-center gap-2">
                  <Input
                    value={candidateSearchDraft}
                    onChange={(event) => setCandidateSearchDraft(event.target.value)}
                    placeholder="搜索提单号"
                    className="w-56"
                  />
                  <Button type="button" variant="secondary" size="sm" onClick={searchCandidates}>
                    搜索
                  </Button>
                  <Button type="button" variant="ghost" size="sm" onClick={clearCandidateSearch}>
                    清空
                  </Button>
                </div>
                <span className="text-sm text-slate-500">已选 {selectedCandidateNos.length} 个</span>
              </div>
              <div className="mb-3 flex flex-wrap gap-2">
                <Button type="button" variant="secondary" size="sm" onClick={addSelectedToNewBoardInput}>
                  加入新建板号
                </Button>
                <Button type="button" variant="ghost" size="sm" onClick={() => setSelectedCandidateNos([])}>
                  清空选择
                </Button>
              </div>
              <p className="mb-3 text-xs text-slate-500">仅显示未绑定板号且处于存活周期的提单。</p>
              <Table>
                <THead>
                  <TR>
                    <TH>
                      <input
                        type="checkbox"
                        className="h-4 w-4 rounded border-slate-300 accent-purple-700"
                        checked={allCurrentCandidatePageSelected}
                        onChange={toggleCurrentCandidatePage}
                        aria-label="选择当前页可绑定提单"
                      />
                    </TH>
                    <TH>提单号</TH>
                    <TH>收件人</TH>
                    <TH>订舱方数</TH>
                    <TH>生命周期</TH>
                  </TR>
                </THead>
                <TBody>
                  {candidateItems.length ? (
                    candidateItems.map((waybill) => (
                      <TR key={waybill.id}>
                        <TD>
                          <input
                            type="checkbox"
                            className="h-4 w-4 rounded border-slate-300 accent-purple-700"
                            checked={selectedCandidateNos.includes(waybill.waybill_no)}
                            onChange={() => toggleCandidate(waybill.waybill_no)}
                            aria-label={`选择提单 ${waybill.waybill_no}`}
                          />
                        </TD>
                        <TD className="font-medium">{waybill.waybill_no}</TD>
                        <TD>{compact(waybill.consignee)}</TD>
                        <TD>{formatDecimal(waybill.booked_volume)}</TD>
                        <TD>
                          <LifecycleBadge value={waybill.lifecycle_status} />
                        </TD>
                      </TR>
                    ))
                  ) : (
                    <TR>
                      <TD colSpan={5} className="text-slate-500">
                        暂无可绑定提单
                      </TD>
                    </TR>
                  )}
                </TBody>
              </Table>
              <div className="mt-4 flex items-center justify-between text-sm text-slate-500">
                <span>共 {candidateData?.total ?? 0} 个可绑定提单</span>
                <div className="flex gap-2">
                  <Button
                    type="button"
                    variant="secondary"
                    size="sm"
                    disabled={candidatePage <= 1}
                    onClick={() => setCandidatePage((prev) => prev - 1)}
                  >
                    上一页
                  </Button>
                  <Button
                    type="button"
                    variant="secondary"
                    size="sm"
                    disabled={!candidateData || candidatePage * candidateData.page_size >= candidateData.total}
                    onClick={() => setCandidatePage((prev) => prev + 1)}
                  >
                    下一页
                  </Button>
                </div>
              </div>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      <Panel title="板号列表">
        <div className="space-y-4">
          {(data?.items || []).map((board) => (
            <div key={board.id} className="rounded-md border border-slate-200">
              <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 bg-slate-50 px-3 py-2">
                <div className="flex flex-wrap items-center gap-3 text-sm">
                  <span className="font-semibold text-slate-900">{board.board_no}</span>
                  <span className="text-slate-600">实际板号：{compact(board.actual_board_no)}</span>
                  <span className="text-slate-600">收件人：{compact(board.consignee_text)}</span>
                  <span className="text-slate-600">成员：{board.member_count}</span>
                  <span className="text-slate-600">总方数：{formatDecimal(board.total_booked_volume)}</span>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button type="button" variant="secondary" size="sm" onClick={() => startEdit(board)}>
                    编辑实际板号
                  </Button>
                  <Button type="button" variant="secondary" size="sm" onClick={() => startAppend(board)}>
                    追加提单
                  </Button>
                  <Button type="button" variant="ghost" size="sm" disabled={saving || board.member_count > 0} onClick={() => void deleteBoard(board)}>
                    <Trash2 className="h-4 w-4" />
                    删除空板
                  </Button>
                </div>
              </div>

              {editingBoardId === board.id ? (
                <div className="flex flex-wrap items-center gap-2 border-b border-slate-100 px-3 py-2">
                  <Input
                    value={actualDraft}
                    onChange={(event) => setActualDraft(event.target.value)}
                    placeholder="实际板号 ID"
                    className="w-72"
                  />
                  <Button type="button" size="sm" disabled={saving} onClick={() => void saveActualBoardNo(board)}>
                    <Save className="h-4 w-4" />
                    保存
                  </Button>
                  <Button type="button" variant="ghost" size="sm" onClick={() => setEditingBoardId(null)}>
                    取消
                  </Button>
                </div>
              ) : null}

              {appendBoardId === board.id ? (
                <div className="grid gap-2 border-b border-slate-100 px-3 py-2 lg:grid-cols-[1fr_auto_auto]">
                  <Textarea
                    value={appendInput}
                    onChange={(event) => setAppendInput(event.target.value)}
                    placeholder="追加提单号，可用换行、逗号或空格分隔"
                    className="min-h-16"
                  />
                  <Button type="button" size="sm" disabled={saving} onClick={() => void appendWaybills(board)}>
                    绑定
                  </Button>
                  <Button type="button" variant="ghost" size="sm" onClick={cancelAppend}>
                    取消
                  </Button>
                </div>
              ) : null}

              <Table>
                <THead>
                  <TR>
                    <TH>提单号</TH>
                    <TH>收件人</TH>
                    <TH>订舱方数</TH>
                    <TH>生命周期</TH>
                    <TH>操作</TH>
                  </TR>
                </THead>
                <TBody>
                  {board.waybills.length ? (
                    board.waybills.map((waybill) => (
                      <TR key={waybill.id}>
                        <TD className="font-medium">{waybill.waybill_no}</TD>
                        <TD>{compact(waybill.consignee)}</TD>
                        <TD>{formatDecimal(waybill.booked_volume)}</TD>
                        <TD>
                          <LifecycleBadge value={waybill.lifecycle_status} />
                        </TD>
                        <TD>
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            disabled={saving}
                            onClick={() => void unbindWaybill(board, waybill.id, waybill.waybill_no)}
                          >
                            <Unlink className="h-4 w-4" />
                            解绑
                          </Button>
                        </TD>
                      </TR>
                    ))
                  ) : (
                    <TR>
                      <TD colSpan={5} className="text-slate-500">
                        当前为空板，可追加提单或删除。
                      </TD>
                    </TR>
                  )}
                </TBody>
              </Table>
            </div>
          ))}
          {!data?.items.length ? <div className="py-8 text-center text-sm text-slate-500">暂无板号</div> : null}
        </div>
        <div className="mt-4 flex items-center justify-between text-sm text-slate-500">
          <span>共 {data?.total ?? 0} 个板号</span>
          <div className="flex gap-2">
            <Button variant="secondary" size="sm" disabled={page <= 1} onClick={() => setPage((prev) => prev - 1)}>
              上一页
            </Button>
            <Button
              variant="secondary"
              size="sm"
              disabled={!data || page * data.page_size >= data.total}
              onClick={() => setPage((prev) => prev + 1)}
            >
              下一页
            </Button>
          </div>
        </div>
      </Panel>
    </>
  );
}
