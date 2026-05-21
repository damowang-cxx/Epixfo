import { PageHeader } from "@/components/ui/page-header";
import { WaybillForm } from "@/components/waybills/waybill-form";

export default function NewWaybillPage() {
  return (
    <>
      <PageHeader title="新建提单" description="录入人工计划航班与提单基础信息" />
      <WaybillForm />
    </>
  );
}
