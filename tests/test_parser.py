from app.models.enums import OfficialEventType
from app.parsers.cz_parser import CZParser


def test_cz_parser_parses_template_sections() -> None:
    parsed = CZParser().parse(
        {
            "订舱信息": [
                {
                    "订舱号": "63151182",
                    "订舱航程": "CANCZ/PKXCZ/AMS",
                    "出发站": "CAN",
                    "到达站": "PKX",
                    "航班号": "CZ3105",
                    "航班日期": "2026-05-12",
                    "件数": "40",
                    "重量": "1000.00",
                    "体积": "4.00",
                    "订舱性质": "KK",
                }
            ],
            "运单信息": {
                "运单号": "784-83707805",
                "承运人": "CZ/CZ",
                "航程": "广州(CAN)--北京大兴(PKX)--阿姆斯特丹(AMS)",
                "货物品名": "MEN S SHIRTS",
                "总件数": "50",
                "总重量(KG)": "1041",
                "总体积": "4.03",
            },
            "货物状态": [
                {
                    "操作时间": "2026年05月12日 21:30:27",
                    "操作城市": "CAN",
                    "航班号": "CZ3105",
                    "货物状态": "货物已装机。",
                    "件数": "50",
                    "重量": "1041",
                }
            ],
            "货物组装信息": [
                {
                    "操作时间": "2026年05月12日 15:14:03",
                    "操作城市": "广州",
                    "货物状态": "货物组装（PMC46859CZ）。",
                    "件数": "50",
                    "重量": "1041",
                }
            ],
        }
    )

    assert parsed.official_info is not None
    assert parsed.official_info.official_waybill_no == "784-83707805"
    assert parsed.flight_segments[0].flight_no == "CZ3105"
    assert parsed.status_events[0].normalized_event_type == OfficialEventType.CARGO_LOADED
    assert parsed.assembly_events[0].uld_no == "PMC46859CZ"
