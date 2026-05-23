"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Bell, Mail, Pencil, Phone, Plus, Power, Save, Trash2, X } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/ui/page-header";
import { Panel } from "@/components/ui/panel";
import { Textarea } from "@/components/ui/textarea";
import { apiClient } from "@/lib/client-api";
import { cn } from "@/lib/utils";
import type { Consignee, ConsigneeContact, ConsigneeNotifyParty } from "@/lib/types";

type ConsigneeDraft = {
  name: string;
  remark: string;
  enabled: boolean;
};

type ContactDraft = {
  name: string;
  address: string;
  email: string;
  phone: string;
  taxInfo: string;
  remark: string;
};

type NotifyPartyDraft = {
  name: string;
  address: string;
  email: string;
  phone: string;
  taxInfo: string;
  remark: string;
  enabled: boolean;
};

function emptyConsigneeDraft(): ConsigneeDraft {
  return { name: "", remark: "", enabled: true };
}

function emptyContactDraft(): ContactDraft {
  return { name: "", address: "", email: "", phone: "", taxInfo: "", remark: "" };
}

function emptyNotifyPartyDraft(defaultName = ""): NotifyPartyDraft {
  return { name: defaultName, address: "", email: "", phone: "", taxInfo: "", remark: "", enabled: true };
}

function contactDraftFromItem(item: ConsigneeContact): ContactDraft {
  return {
    name: item.name || "",
    address: item.address || "",
    email: item.email || "",
    phone: item.phone || "",
    taxInfo: item.tax_info || "",
    remark: item.remark || ""
  };
}

function notifyDraftFromItem(item: ConsigneeNotifyParty): NotifyPartyDraft {
  return {
    name: item.name || "",
    address: item.address || "",
    email: item.email || "",
    phone: item.phone || "",
    taxInfo: item.tax_info || "",
    remark: item.remark || "",
    enabled: item.enabled
  };
}

function errorMessage(err: unknown, fallback: string) {
  return err instanceof Error ? err.message : fallback;
}

export default function ConsigneesPage() {
  const [consignees, setConsignees] = useState<Consignee[]>([]);
  const [contacts, setContacts] = useState<ConsigneeContact[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);

  const [editingConsigneeId, setEditingConsigneeId] = useState<number | "new" | null>(null);
  const [consigneeDraft, setConsigneeDraft] = useState<ConsigneeDraft>(() => emptyConsigneeDraft());
  const [consigneeError, setConsigneeError] = useState("");
  const [savingConsignee, setSavingConsignee] = useState(false);

  const [editingContactId, setEditingContactId] = useState<number | "new" | null>(null);
  const [contactDraft, setContactDraft] = useState<ContactDraft>(() => emptyContactDraft());
  const [contactError, setContactError] = useState("");
  const [savingContact, setSavingContact] = useState(false);
  const [togglingContactId, setTogglingContactId] = useState<number | null>(null);
  const [deletingContactId, setDeletingContactId] = useState<number | null>(null);

  const [notifyContact, setNotifyContact] = useState<ConsigneeContact | null>(null);
  const [notifyDraft, setNotifyDraft] = useState<NotifyPartyDraft>(() => emptyNotifyPartyDraft());
  const [notifyError, setNotifyError] = useState("");
  const [notifyLoading, setNotifyLoading] = useState(false);
  const [savingNotify, setSavingNotify] = useState(false);

  const fetchConsigneeData = useCallback(
    () =>
      Promise.all([
        apiClient.get<Consignee[]>("/consignees"),
        apiClient.get<ConsigneeContact[]>("/consignee-contacts")
      ]),
    []
  );

  const applyConsigneeData = useCallback(([cs, ct]: [Consignee[], ConsigneeContact[]]) => {
    setConsignees(cs);
    setContacts(ct);
    setSelectedId((current) => current ?? cs[0]?.id ?? null);
  }, []);

  const reload = useCallback(async () => {
    const data = await fetchConsigneeData();
    applyConsigneeData(data);
  }, [applyConsigneeData, fetchConsigneeData]);

  useEffect(() => {
    let cancelled = false;
    fetchConsigneeData()
      .then((data) => {
        if (!cancelled) applyConsigneeData(data);
      })
      .catch(() => {
        if (!cancelled) {
          setConsignees([]);
          setContacts([]);
          setSelectedId(null);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [applyConsigneeData, fetchConsigneeData]);

  const selectedConsignee = useMemo(
    () => consignees.find((c) => c.id === selectedId) || null,
    [consignees, selectedId]
  );
  const selectedContacts = useMemo(
    () => contacts.filter((c) => c.consignee_id === selectedId),
    [contacts, selectedId]
  );

  function startNewConsignee() {
    setEditingConsigneeId("new");
    setConsigneeDraft(emptyConsigneeDraft());
    setConsigneeError("");
  }

  function startEditConsignee(item: Consignee) {
    setEditingConsigneeId(item.id);
    setConsigneeDraft({ name: item.name, remark: item.remark || "", enabled: item.enabled });
    setConsigneeError("");
  }

  function cancelConsigneeEdit() {
    setEditingConsigneeId(null);
    setConsigneeDraft(emptyConsigneeDraft());
    setConsigneeError("");
  }

  async function saveConsignee() {
    if (!consigneeDraft.name.trim()) {
      setConsigneeError("收件厂商名称为必填");
      return;
    }
    setSavingConsignee(true);
    setConsigneeError("");
    try {
      if (editingConsigneeId === "new") {
        const created = await apiClient.post<Consignee>("/consignees", {
          name: consigneeDraft.name.trim(),
          remark: consigneeDraft.remark.trim() || null,
          enabled: consigneeDraft.enabled
        });
        await reload();
        setSelectedId(created.id);
      } else if (typeof editingConsigneeId === "number") {
        await apiClient.patch<Consignee>(`/consignees/${editingConsigneeId}`, {
          name: consigneeDraft.name.trim(),
          remark: consigneeDraft.remark.trim() || null,
          enabled: consigneeDraft.enabled
        });
        await reload();
      }
      cancelConsigneeEdit();
    } catch (err) {
      setConsigneeError(errorMessage(err, "收件厂商保存失败"));
    } finally {
      setSavingConsignee(false);
    }
  }

  function startNewContact() {
    if (!selectedConsignee) return;
    setEditingContactId("new");
    setContactDraft(emptyContactDraft());
    setContactError("");
  }

  function startEditContact(item: ConsigneeContact) {
    setEditingContactId(item.id);
    setContactDraft(contactDraftFromItem(item));
    setContactError("");
  }

  function cancelContactEdit() {
    setEditingContactId(null);
    setContactDraft(emptyContactDraft());
    setContactError("");
  }

  async function saveContact() {
    if (!selectedConsignee) return;
    if (!contactDraft.name.trim()) {
      setContactError("收件人名/收件公司名称为必填");
      return;
    }
    setSavingContact(true);
    setContactError("");
    try {
      const body = {
        name: contactDraft.name.trim(),
        address: contactDraft.address.trim() || null,
        email: contactDraft.email.trim() || null,
        phone: contactDraft.phone.trim() || null,
        tax_info: contactDraft.taxInfo.trim() || null,
        remark: contactDraft.remark.trim() || null
      };
      if (editingContactId === "new") {
        await apiClient.post<ConsigneeContact>("/consignee-contacts", {
          consignee_id: selectedConsignee.id,
          ...body
        });
      } else if (typeof editingContactId === "number") {
        await apiClient.patch<ConsigneeContact>(`/consignee-contacts/${editingContactId}`, body);
      }
      cancelContactEdit();
      await reload();
    } catch (err) {
      setContactError(errorMessage(err, "收件人保存失败"));
    } finally {
      setSavingContact(false);
    }
  }

  async function toggleContactEnabled(item: ConsigneeContact) {
    setTogglingContactId(item.id);
    setContactError("");
    try {
      await apiClient.patch<ConsigneeContact>(`/consignee-contacts/${item.id}`, {
        enabled: !item.enabled
      });
      await reload();
    } catch (err) {
      setContactError(errorMessage(err, item.enabled ? "收件人停用失败" : "收件人启用失败"));
    } finally {
      setTogglingContactId(null);
    }
  }

  async function deleteContact(item: ConsigneeContact) {
    if (!window.confirm(`确认删除收件人 ${item.name}？删除后不可恢复，历史提单会保留已写入的收件人文本。`)) {
      return;
    }
    setDeletingContactId(item.id);
    setContactError("");
    try {
      await apiClient.delete<void>(`/consignee-contacts/${item.id}`);
      if (editingContactId === item.id) {
        cancelContactEdit();
      }
      await reload();
    } catch (err) {
      setContactError(errorMessage(err, "收件人删除失败"));
    } finally {
      setDeletingContactId(null);
    }
  }

  async function openNotifyDialog(contact: ConsigneeContact) {
    setNotifyContact(contact);
    setNotifyDraft(emptyNotifyPartyDraft(contact.name));
    setNotifyError("");
    setNotifyLoading(true);
    try {
      const notifyParty = await apiClient.get<ConsigneeNotifyParty | null>(
        `/consignee-contacts/${contact.id}/notify-party`
      );
      setNotifyDraft(notifyParty ? notifyDraftFromItem(notifyParty) : emptyNotifyPartyDraft(contact.name));
    } catch (err) {
      setNotifyError(errorMessage(err, "通知人信息加载失败"));
    } finally {
      setNotifyLoading(false);
    }
  }

  function closeNotifyDialog() {
    setNotifyContact(null);
    setNotifyDraft(emptyNotifyPartyDraft());
    setNotifyError("");
    setNotifyLoading(false);
    setSavingNotify(false);
  }

  async function saveNotifyParty() {
    if (!notifyContact) return;
    setSavingNotify(true);
    setNotifyError("");
    try {
      await apiClient.put<ConsigneeNotifyParty>(`/consignee-contacts/${notifyContact.id}/notify-party`, {
        name: notifyDraft.name.trim() || null,
        address: notifyDraft.address.trim() || null,
        email: notifyDraft.email.trim() || null,
        phone: notifyDraft.phone.trim() || null,
        tax_info: notifyDraft.taxInfo.trim() || null,
        remark: notifyDraft.remark.trim() || null,
        enabled: notifyDraft.enabled
      });
      closeNotifyDialog();
    } catch (err) {
      setNotifyError(errorMessage(err, "通知人信息保存失败"));
    } finally {
      setSavingNotify(false);
    }
  }

  return (
    <>
      <PageHeader
        title="收件人管理"
        description="维护收件厂商、具体收件人记录及其绑定的通知人资料。"
      />

      <div className="grid gap-4 lg:grid-cols-[320px_1fr]">
        <Panel
          title="收件厂商"
          action={
            <Button size="sm" onClick={startNewConsignee} disabled={editingConsigneeId !== null}>
              <Plus className="h-4 w-4" />
              新建
            </Button>
          }
        >
          {consigneeError ? (
            <div className="mb-2 rounded-md border border-red-200 bg-red-50 px-2 py-1 text-xs text-red-700">
              {consigneeError}
            </div>
          ) : null}

          {editingConsigneeId !== null ? (
            <div className="mb-3 space-y-2 rounded-md border border-purple-200 bg-purple-50 p-3">
              <div>
                <Label className="text-xs">厂商名称</Label>
                <Input
                  value={consigneeDraft.name}
                  onChange={(event) => setConsigneeDraft((prev) => ({ ...prev, name: event.target.value }))}
                  placeholder="例如 Mission Freight BV"
                />
              </div>
              <div>
                <Label className="text-xs">备注</Label>
                <Input
                  value={consigneeDraft.remark}
                  onChange={(event) => setConsigneeDraft((prev) => ({ ...prev, remark: event.target.value }))}
                />
              </div>
              <label className="flex items-center gap-2 text-xs text-slate-700">
                <input
                  type="checkbox"
                  className="h-4 w-4 rounded border-slate-300"
                  checked={consigneeDraft.enabled}
                  onChange={(event) => setConsigneeDraft((prev) => ({ ...prev, enabled: event.target.checked }))}
                />
                启用
              </label>
              <div className="flex gap-2">
                <Button size="sm" onClick={saveConsignee} disabled={savingConsignee}>
                  <Save className="h-4 w-4" />
                  保存
                </Button>
                <Button type="button" size="sm" variant="secondary" onClick={cancelConsigneeEdit} disabled={savingConsignee}>
                  <X className="h-4 w-4" />
                  取消
                </Button>
              </div>
            </div>
          ) : null}

          {consignees.length === 0 ? (
            <EmptyState title="暂无厂商" description="点击右上角“新建”开始维护。" />
          ) : (
            <div className="space-y-1">
              {consignees.map((item) => {
                const active = item.id === selectedId;
                return (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => setSelectedId(item.id)}
                    className={cn(
                      "flex w-full items-center justify-between rounded-md border px-3 py-2 text-left text-sm",
                      active
                        ? "border-purple-300 bg-purple-50 text-purple-900 ring-2 ring-purple-300"
                        : "border-slate-200 bg-white hover:bg-slate-50"
                    )}
                  >
                    <div className="min-w-0 flex-1 truncate">
                      <span className="font-medium">{item.name}</span>
                      {!item.enabled ? <span className="ml-1 text-xs text-slate-500">(停用)</span> : null}
                    </div>
                    <span
                      role="button"
                      tabIndex={0}
                      className="ml-2 cursor-pointer text-slate-400 hover:text-slate-700"
                      onClick={(event) => {
                        event.stopPropagation();
                        startEditConsignee(item);
                      }}
                      onKeyDown={(event) => {
                        if (event.key === "Enter") {
                          event.stopPropagation();
                          startEditConsignee(item);
                        }
                      }}
                      aria-label="编辑厂商"
                    >
                      <Pencil className="h-3.5 w-3.5" />
                    </span>
                  </button>
                );
              })}
            </div>
          )}
        </Panel>

        <Panel
          title={selectedConsignee ? `${selectedConsignee.name} · 收件人` : "收件人"}
          action={
            <Button size="sm" onClick={startNewContact} disabled={!selectedConsignee || editingContactId !== null}>
              <Plus className="h-4 w-4" />
              新建收件人
            </Button>
          }
        >
          {!selectedConsignee ? (
            <EmptyState title="请先选择厂商" description="左侧选中一个厂商后才能维护其下属收件人。" />
          ) : (
            <>
              {contactError ? (
                <div className="mb-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                  {contactError}
                </div>
              ) : null}

              {editingContactId !== null ? (
                <div className="mb-4 rounded-md border border-purple-200 bg-purple-50 p-4">
                  <div className="grid gap-3 md:grid-cols-2">
                    <div className="md:col-span-2">
                      <Label>收件人名/收件公司名称</Label>
                      <Input
                        value={contactDraft.name}
                        onChange={(event) => setContactDraft((prev) => ({ ...prev, name: event.target.value }))}
                        placeholder="例如 Mission Freight BV - AMS"
                      />
                    </div>
                    <div className="md:col-span-2">
                      <Label>地址</Label>
                      <Textarea
                        rows={2}
                        value={contactDraft.address}
                        onChange={(event) => setContactDraft((prev) => ({ ...prev, address: event.target.value }))}
                        placeholder="tokyostraat 1-1175 RB Lijnden"
                      />
                    </div>
                    <div>
                      <Label>邮箱</Label>
                      <Input
                        value={contactDraft.email}
                        onChange={(event) => setContactDraft((prev) => ({ ...prev, email: event.target.value }))}
                        placeholder="info@example.com"
                      />
                    </div>
                    <div>
                      <Label>电话</Label>
                      <Input
                        value={contactDraft.phone}
                        onChange={(event) => setContactDraft((prev) => ({ ...prev, phone: event.target.value }))}
                        placeholder="+31 20 6531312"
                      />
                    </div>
                    <div className="md:col-span-2">
                      <Label>税号信息</Label>
                      <Textarea
                        rows={2}
                        value={contactDraft.taxInfo}
                        onChange={(event) => setContactDraft((prev) => ({ ...prev, taxInfo: event.target.value }))}
                        placeholder={"自由文本，例如\nEORI: NL822303474\nT.G.: NL00740018009"}
                      />
                    </div>
                    <div className="md:col-span-2">
                      <Label>备注</Label>
                      <Textarea
                        rows={2}
                        value={contactDraft.remark}
                        onChange={(event) => setContactDraft((prev) => ({ ...prev, remark: event.target.value }))}
                      />
                    </div>
                  </div>
                  <div className="mt-3 flex gap-2">
                    <Button size="sm" onClick={saveContact} disabled={savingContact}>
                      <Save className="h-4 w-4" />
                      保存
                    </Button>
                    <Button type="button" size="sm" variant="secondary" onClick={cancelContactEdit} disabled={savingContact}>
                      <X className="h-4 w-4" />
                      取消
                    </Button>
                  </div>
                </div>
              ) : null}

              {selectedContacts.length === 0 ? (
                <EmptyState title="该厂商暂无收件人" description="点击右上角“新建收件人”开始维护。" />
              ) : (
                <div className="space-y-2">
                  {selectedContacts.map((item) => (
                    <div
                      key={item.id}
                      className="grid gap-3 rounded-md border border-slate-200 p-3 md:grid-cols-[1fr_auto]"
                    >
                      <div className="min-w-0 space-y-1 text-sm text-slate-800">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-medium text-slate-950">{item.name}</span>
                          <Badge variant={item.enabled ? "green" : "gray"}>{item.enabled ? "启用" : "停用"}</Badge>
                        </div>
                        {item.address ? (
                          <div className="whitespace-pre-wrap break-words text-slate-700">{item.address}</div>
                        ) : (
                          <div className="text-slate-400">(无地址)</div>
                        )}
                        <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-slate-600">
                          {item.email ? (
                            <span className="inline-flex items-center gap-1">
                              <Mail className="h-3.5 w-3.5" />
                              {item.email}
                            </span>
                          ) : null}
                          {item.phone ? (
                            <span className="inline-flex items-center gap-1">
                              <Phone className="h-3.5 w-3.5" />
                              {item.phone}
                            </span>
                          ) : null}
                        </div>
                        {item.tax_info ? (
                          <div className="whitespace-pre-wrap rounded bg-slate-50 p-2 text-xs text-slate-600">
                            {item.tax_info}
                          </div>
                        ) : null}
                        {item.remark ? <div className="text-xs text-slate-500">备注: {item.remark}</div> : null}
                      </div>
                      <div className="flex flex-wrap items-start gap-2 md:justify-end">
                        <Button type="button" variant="secondary" size="sm" onClick={() => openNotifyDialog(item)}>
                          <Bell className="h-4 w-4" />
                          通知人
                        </Button>
                        <Button
                          type="button"
                          variant={item.enabled ? "ghost" : "secondary"}
                          size="sm"
                          onClick={() => toggleContactEnabled(item)}
                          disabled={editingContactId !== null || togglingContactId === item.id || deletingContactId === item.id}
                        >
                          <Power className="h-4 w-4" />
                          {item.enabled ? "停用" : "启用"}
                        </Button>
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          onClick={() => startEditContact(item)}
                          disabled={editingContactId !== null}
                        >
                          <Pencil className="h-4 w-4" />
                          编辑
                        </Button>
                        <Button
                          type="button"
                          variant="danger"
                          size="sm"
                          onClick={() => deleteContact(item)}
                          disabled={editingContactId !== null || deletingContactId === item.id}
                        >
                          <Trash2 className="h-4 w-4" />
                          删除
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
        </Panel>
      </div>

      <Dialog open={Boolean(notifyContact)} onOpenChange={(open) => !open && closeNotifyDialog()}>
        <DialogContent className="w-[min(920px,calc(100vw-32px))]">
          <DialogTitle className="pr-10 text-base font-semibold text-slate-900">
            {notifyContact ? `${notifyContact.name} · 通知人` : "通知人"}
          </DialogTitle>

          {notifyError ? (
            <div className="mt-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
              {notifyError}
            </div>
          ) : null}

          {notifyLoading ? (
            <div className="mt-4 rounded-md border border-slate-200 bg-slate-50 px-3 py-6 text-center text-sm text-slate-500">
              加载中...
            </div>
          ) : (
            <div className="mt-4 overflow-x-auto">
              <table className="min-w-[820px] border-separate border-spacing-0 text-sm">
                <thead>
                  <tr className="text-left text-xs text-slate-500">
                    <th className="border-b border-slate-200 pb-2 pr-3 font-medium">通知人名称</th>
                    <th className="border-b border-slate-200 pb-2 pr-3 font-medium">地址</th>
                    <th className="border-b border-slate-200 pb-2 pr-3 font-medium">邮箱</th>
                    <th className="border-b border-slate-200 pb-2 pr-3 font-medium">电话</th>
                    <th className="border-b border-slate-200 pb-2 pr-3 font-medium">税号</th>
                    <th className="border-b border-slate-200 pb-2 font-medium">状态</th>
                  </tr>
                </thead>
                <tbody>
                  <tr className="align-top">
                    <td className="w-44 pt-3 pr-3">
                      <Input
                        value={notifyDraft.name}
                        onChange={(event) => setNotifyDraft((prev) => ({ ...prev, name: event.target.value }))}
                      />
                    </td>
                    <td className="w-56 pt-3 pr-3">
                      <Textarea
                        rows={3}
                        value={notifyDraft.address}
                        onChange={(event) => setNotifyDraft((prev) => ({ ...prev, address: event.target.value }))}
                      />
                    </td>
                    <td className="w-44 pt-3 pr-3">
                      <Input
                        value={notifyDraft.email}
                        onChange={(event) => setNotifyDraft((prev) => ({ ...prev, email: event.target.value }))}
                      />
                    </td>
                    <td className="w-36 pt-3 pr-3">
                      <Input
                        value={notifyDraft.phone}
                        onChange={(event) => setNotifyDraft((prev) => ({ ...prev, phone: event.target.value }))}
                      />
                    </td>
                    <td className="w-44 pt-3 pr-3">
                      <Textarea
                        rows={3}
                        value={notifyDraft.taxInfo}
                        onChange={(event) => setNotifyDraft((prev) => ({ ...prev, taxInfo: event.target.value }))}
                      />
                    </td>
                    <td className="w-24 pt-3">
                      <label className="flex items-center gap-2 text-sm text-slate-700">
                        <input
                          type="checkbox"
                          className="h-4 w-4 rounded border-slate-300"
                          checked={notifyDraft.enabled}
                          onChange={(event) => setNotifyDraft((prev) => ({ ...prev, enabled: event.target.checked }))}
                        />
                        启用
                      </label>
                    </td>
                  </tr>
                </tbody>
              </table>
              <div className="mt-3">
                <Label>备注</Label>
                <Textarea
                  rows={2}
                  value={notifyDraft.remark}
                  onChange={(event) => setNotifyDraft((prev) => ({ ...prev, remark: event.target.value }))}
                />
              </div>
            </div>
          )}

          <div className="mt-4 flex justify-end gap-2">
            <Button type="button" variant="secondary" onClick={closeNotifyDialog} disabled={savingNotify}>
              取消
            </Button>
            <Button type="button" onClick={saveNotifyParty} disabled={notifyLoading || savingNotify}>
              <Save className="h-4 w-4" />
              保存通知人
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
