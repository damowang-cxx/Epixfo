import { PageHeader } from "@/components/ui/page-header";
import { WaybillForm } from "@/components/waybills/waybill-form";

export default function NewWaybillPage() {
  return (
    <>
      <PageHeader title="新建运单" description="录入人工计划航班与运单基础信息" />
      <WaybillForm />
    </>
  );
}
