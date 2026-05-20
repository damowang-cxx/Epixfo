"""[app/adapters/carrier_query/csair/html_parser.py](app/adapters/carrier_query/csair/html_parser.py) 单元测试。

覆盖中文 + 英文 header 的解析路径，并固定一段最小可复现 HTML 防止回归。
"""

from __future__ import annotations

from app.adapters.carrier_query.csair.html_parser import parse_result


# 真实 HTML 摘选（覆盖运单摘要 + 订舱信息 + 货物状态 + 货物组装 + milestone）
_REAL_HTML_CN = """
<html><body>
<span id="ctl00_ContentPlaceHolder1_awbLbl"></span>
<table border="0" width="100%" class="commTblStyle_8">
    <tbody><tr>
        <th>运单号</th>
        <th>承运人</th>
        <th>航程</th>
        <th>货物品名</th>
        <th>总件数</th>
        <th>总重量(KG)</th>
        <th>总体积</th>
    </tr>
    <tr>
        <td>784-83707805</td>
        <td>CZ/CZ</td>
        <td>广州(CAN)--北京大兴(PKX)--阿姆斯特丹(AMS)</td>
        <td>MEN S SHIRTS HS CODE6205200099</td>
        <td>50</td>
        <td>1041</td>
        <td>4.03</td>
    </tr>
</tbody></table>

<table id="ctl00_ContentPlaceHolder1_gvBookInfo">
    <tr>
        <th>订舱号</th><th>订舱航程</th><th>出发站</th><th>到达站</th>
        <th>航班号</th><th>航班日期</th><th>件数</th><th>重量</th><th>体积</th><th>订舱性质</th>
    </tr>
    <tr>
        <td>63151182</td><td>CAN-PKX-AMS</td><td>CAN</td><td>PKX</td>
        <td>CZ3105</td><td>2026-05-12</td><td>40</td><td>1000.00</td><td>4.00</td><td>KK</td>
    </tr>
</table>

<table id="ctl00_ContentPlaceHolder1_gvCargoState">
    <tr><th>操作时间</th><th>操作城市</th><th>航班号</th><th>货物状态</th><th>件数</th><th>重量</th></tr>
    <tr>
        <td>2026年05月12日 21:30:27</td><td>CAN</td><td>CZ3105</td>
        <td>货物已装机。</td><td>50</td><td>1041</td>
    </tr>
</table>

<table id="ctl00_ContentPlaceHolder1_gvCombine">
    <tr><th>操作时间</th><th>操作城市</th><th>货物状态</th><th>件数</th><th>重量</th></tr>
    <tr>
        <td>2026年05月12日 15:14:03</td><td>广州</td>
        <td>货物组装（PMC46859CZ）。</td><td>50</td><td>1041</td>
    </tr>
</table>

<img id="ctl00_ContentPlaceHolder1_img0" src="/img/100.gif"/>
<img id="ctl00_ContentPlaceHolder1_img1" src="/img/110.gif"/>
<img id="ctl00_ContentPlaceHolder1_img2" src="/img/121.gif"/>
<img id="ctl00_ContentPlaceHolder1_img3" src="/img/132.gif"/>
<img id="ctl00_ContentPlaceHolder1_img4" src="/img/142.gif"/>
</body></html>
"""


_REAL_HTML_EN = """
<html><body>
<span id="ctl00_ContentPlaceHolder1_awbLbl"></span>
<table class="commTblStyle_8">
    <tr>
        <th>AWB No.</th>
        <th>Carrier</th>
        <th>Route</th>
        <th>Description</th>
        <th>Pieces</th>
        <th>Weight(KG)</th>
        <th>Volume</th>
    </tr>
    <tr>
        <td>784-83707805</td>
        <td>CZ/CZ</td>
        <td>CAN--PKX--AMS</td>
        <td>SHIRTS</td>
        <td>50</td>
        <td>1041</td>
        <td>4.03</td>
    </tr>
</table>

<table id="ctl00_ContentPlaceHolder1_gvBookInfo">
    <tr>
        <th>Booking No</th><th>Route</th><th>From</th><th>To</th>
        <th>Flight</th><th>Flight Date</th><th>Pieces</th><th>Weight</th><th>Volume</th><th>Type</th>
    </tr>
    <tr>
        <td>63151182</td><td>CAN-PKX-AMS</td><td>CAN</td><td>PKX</td>
        <td>CZ3105</td><td>2026-05-12</td><td>40</td><td>1000.00</td><td>4.00</td><td>KK</td>
    </tr>
</table>

<table id="ctl00_ContentPlaceHolder1_gvCargoState">
    <tr><th>Time</th><th>City</th><th>Flight</th><th>Status</th><th>Pieces</th><th>Weight</th></tr>
    <tr>
        <td>2026-05-12 21:30:27</td><td>CAN</td><td>CZ3105</td>
        <td>Cargo Loaded</td><td>50</td><td>1041</td>
    </tr>
</table>

<table id="ctl00_ContentPlaceHolder1_gvCombine">
    <tr><th>Time</th><th>City</th><th>Status</th><th>Pieces</th><th>Weight</th></tr>
    <tr>
        <td>2026-05-12 15:14:03</td><td>Guangzhou</td>
        <td>Cargo Assembled (PMC46859CZ)</td><td>50</td><td>1041</td>
    </tr>
</table>
</body></html>
"""


# 包含两个 table 干扰 awbLbl find_next 的场景（先碰到一个无关 table，再找到 awb summary）
_NOISY_HTML = """
<html><body>
<span id="ctl00_ContentPlaceHolder1_awbLbl"></span>
<table>
    <tr><th>无关</th></tr>
    <tr><td>这是噪声</td></tr>
</table>
<table class="commTblStyle_8">
    <tr><th>运单号</th><th>承运人</th><th>航程</th><th>货物品名</th><th>总件数</th><th>总重量(KG)</th><th>总体积</th></tr>
    <tr><td>784-83707805</td><td>CZ/CZ</td><td>X</td><td>Y</td><td>50</td><td>1041</td><td>4.03</td></tr>
</table>
</body></html>
"""


def test_parse_real_chinese_awb_summary_full_fields() -> None:
    result = parse_result(_REAL_HTML_CN)
    info = result["awbInfo"]

    assert info is not None
    assert info["awbNo"] == "784-83707805"
    assert info["carrier"] == "CZ/CZ"
    assert info["route"] == "广州(CAN)--北京大兴(PKX)--阿姆斯特丹(AMS)"
    assert "MEN S SHIRTS" in info["commodity"]
    # 关键回归：用户报告的三个字段
    assert info["totalPieces"] == "50"
    assert info["totalWeightKg"] == "1041"
    assert info["totalVolume"] == "4.03"


def test_parse_real_chinese_booking_and_events() -> None:
    result = parse_result(_REAL_HTML_CN)

    assert len(result["booking"]) == 1
    booking = result["booking"][0]
    assert booking["bookingNo"] == "63151182"
    assert booking["flight"] == "CZ3105"
    assert booking["weight"] == "1000.00"
    assert booking["volume"] == "4.00"

    assert len(result["cargoState"]) == 1
    state = result["cargoState"][0]
    assert state["status"] == "货物已装机。"
    assert state["time"] == "2026-05-12 21:30:27"
    assert state["weight"] == "1041"

    assert len(result["combine"]) == 1
    assert "PMC46859CZ" in result["combine"][0]["status"]
    assert result["combine"][0]["time"] == "2026-05-12 15:14:03"

    assert result["milestones"]["received"]["status"] == "done"
    assert result["milestones"]["departed"]["status"] == "in_progress"
    assert result["milestones"]["arrived"]["status"] == "pending"


def test_parse_english_awb_summary() -> None:
    """英文页面的字段映射要能拿到同样的标准 key。"""
    result = parse_result(_REAL_HTML_EN)
    info = result["awbInfo"]

    assert info is not None
    assert info["awbNo"] == "784-83707805"
    assert info["carrier"] == "CZ/CZ"
    assert info["commodity"] == "SHIRTS"
    assert info["totalPieces"] == "50"
    assert info["totalWeightKg"] == "1041"
    assert info["totalVolume"] == "4.03"


def test_parse_english_booking_and_events() -> None:
    result = parse_result(_REAL_HTML_EN)

    booking = result["booking"][0]
    assert booking["bookingNo"] == "63151182"
    assert booking["flight"] == "CZ3105"
    assert booking["fromStation"] == "CAN"
    assert booking["toStation"] == "PKX"
    assert booking["weight"] == "1000.00"

    state = result["cargoState"][0]
    assert state["flight"] == "CZ3105"
    assert state["status"] == "Cargo Loaded"

    combine = result["combine"][0]
    assert "PMC46859CZ" in combine["status"]


def test_awb_summary_skips_unrelated_first_table() -> None:
    """awbLbl 之后第一张表不是 awb summary 时，应继续往后找。"""
    result = parse_result(_NOISY_HTML)
    info = result["awbInfo"]

    assert info is not None
    assert info["awbNo"] == "784-83707805"
    assert info["totalPieces"] == "50"
    assert info["totalWeightKg"] == "1041"
    assert info["totalVolume"] == "4.03"


def test_cargo_state_time_header_with_extra_controls() -> None:
    html = """
    <table id="ctl00_ContentPlaceHolder1_gvCargoState">
        <tr>
            <th>操作时间  <label id='currentTimeArea'>当前时区</label><input value='当地时间' /></th>
            <th>操作城市</th><th>航班号</th><th>货物状态</th><th>件数</th><th>重量</th>
        </tr>
        <tr>
            <td>2026年05月02日 01:02:36</td>
            <td>广州</td><td>CZ307</td><td>航班已起飞。</td><td></td><td></td>
        </tr>
    </table>
    """

    result = parse_result(html)

    assert result["cargoState"][0]["time"] == "2026-05-02 01:02:36"
    assert result["cargoState"][0]["flight"] == "CZ307"
    assert result["cargoState"][0]["status"] == "航班已起飞。"
