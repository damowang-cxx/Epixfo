from typing import Any


SUMMARY_LABELS = {"合计", "合計", "总计", "總計", "小计", "小計", "总方数", "總方數", "总重量", "總重量", "总数量", "總數量", "总箱数", "總箱數", "TOTAL", "GRANDTOTAL", "SUBTOTAL"}


def is_warehouse_summary_row(box_no: Any, waybill_no: Any, goods_name: Any, quantity: Any) -> bool:
    def text(value: Any) -> str:
        return "" if value is None else "".join(str(value).split()).strip(":：").upper()

    barcode, waybill, goods, count = map(text, (box_no, waybill_no, goods_name, quantity))
    if barcode in SUMMARY_LABELS:
        return True
    if barcode:
        return False
    if waybill in SUMMARY_LABELS:
        return True
    return not waybill and (goods in SUMMARY_LABELS or count in SUMMARY_LABELS)
