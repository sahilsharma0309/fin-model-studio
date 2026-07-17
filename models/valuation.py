"""Valuation models — DCF, Trading Comps, Precedent Transactions, DDM,
NAV, NPV/IRR, and the Triangulated Valuation Mix.

Every compute function is pure math on the form inputs; verdicts and
insights are written for non-technical readers in the selected language.
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from core.branding import ACCENT_COLOR, PRIMARY_COLOR
from core.charts import MUTED, base_figure, chart_result, fmt
from core.result import Kpi
from models.base import Field, ModelOutput, ModelSpec, clean_table, register

FORECAST_YEARS = 5


def _L(en: str, hi: str) -> dict:
    return {"en": en, "hi": hi}


def _pct(x) -> float:
    return float(x or 0) / 100.0


# ----------------------------------------------------------------- DCF
def _dcf_core(v: dict) -> dict:
    """Shared DCF math; returns dict of intermediate series + values."""
    revenue = float(v["revenue"])
    growth, margin = _pct(v["growth_pct"]), _pct(v["ebit_margin_pct"])
    tax, da = _pct(v["tax_pct"]), _pct(v["da_pct"])
    capex, nwc = _pct(v["capex_pct"]), _pct(v["nwc_pct"])
    wacc, tg = _pct(v["wacc_pct"]), _pct(v["tg_pct"])

    years, fcffs, pvs = [], [], []
    rev = revenue
    for year in range(1, FORECAST_YEARS + 1):
        rev *= (1 + growth)
        ebit = rev * margin
        fcff = ebit * (1 - tax) + rev * da - rev * capex - rev * growth * nwc
        pv = fcff / (1 + wacc) ** year
        years.append(year)
        fcffs.append(fcff)
        pvs.append(pv)

    terminal = fcffs[-1] * (1 + tg) / (wacc - tg) if wacc > tg else float("nan")
    pv_terminal = terminal / (1 + wacc) ** FORECAST_YEARS if wacc > tg else float("nan")
    ev = sum(pvs) + pv_terminal
    equity = ev - float(v["net_debt"])
    shares = max(float(v["shares"]), 1e-9)
    return dict(years=years, fcffs=fcffs, pvs=pvs, pv_terminal=pv_terminal,
                ev=ev, equity=equity, per_share=equity / shares, wacc=wacc, tg=tg)


_DCF_FIELDS = [
    Field("revenue", _L("Latest annual revenue", "ताज़ा सालाना राजस्व"), default=1000.0),
    Field("growth_pct", _L("Revenue growth % (per year)", "राजस्व वृद्धि % (सालाना)"), "percent", 8.0),
    Field("ebit_margin_pct", _L("EBIT margin %", "EBIT मार्जिन %"), "percent", 18.0),
    Field("tax_pct", _L("Tax rate %", "कर दर %"), "percent", 25.0),
    Field("da_pct", _L("D&A as % of revenue", "D&A (राजस्व का %)"), "percent", 4.0),
    Field("capex_pct", _L("Capex as % of revenue", "पूंजीगत खर्च (राजस्व का %)"), "percent", 5.0),
    Field("nwc_pct", _L("Working-capital need as % of new revenue", "कार्यशील पूंजी (नए राजस्व का %)"), "percent", 10.0),
    Field("wacc_pct", _L("WACC / discount rate %", "WACC / छूट दर %"), "percent", 11.0),
    Field("tg_pct", _L("Terminal growth %", "दीर्घकालिक वृद्धि %"), "percent", 3.0),
    Field("net_debt", _L("Net debt (debt − cash)", "शुद्ध क़र्ज़ (क़र्ज़ − नक़द)"), default=200.0),
    Field("shares", _L("Shares outstanding", "कुल शेयर"), default=100.0, min_value=0.0001),
]


def _dcf_compute(v: dict, lang: str) -> ModelOutput:
    if _pct(v["wacc_pct"]) <= _pct(v["tg_pct"]):
        msg = ("WACC must be higher than terminal growth — otherwise the formula "
               "breaks (division by zero)." if lang != "hi" else
               "WACC दीर्घकालिक वृद्धि से ज़्यादा होना चाहिए — वरना फ़ॉर्मूला टूट जाता है।")
        return ModelOutput(kpis=[], results=[], verdict=f"⚠️ {msg}")

    d = _dcf_core(v)
    per_share = d["per_share"]

    title1 = ("Projected free cash flow (5 years)" if lang != "hi"
              else "अनुमानित फ्री कैश फ्लो (5 साल)")
    fig1 = base_figure(title1)
    fig1.add_trace(go.Bar(
        x=[f"Y{y}" for y in d["years"]], y=d["fcffs"], marker_color=PRIMARY_COLOR,
        text=[fmt(f) for f in d["fcffs"]], textposition="outside",
        textfont=dict(color=MUTED, size=11),
        hovertemplate="%{x}: <b>%{y:,.0f}</b><extra></extra>",
    ))
    ins1 = (f"Cash flows grow from {fmt(d['fcffs'][0])} to {fmt(d['fcffs'][-1])} "
            f"over {FORECAST_YEARS} years." if lang != "hi" else
            f"{FORECAST_YEARS} साल में कैश फ्लो {fmt(d['fcffs'][0])} से बढ़कर "
            f"{fmt(d['fcffs'][-1])} हो जाता है।")
    g1 = ("Each bar is one future year's cash the business should generate — "
          "taller is better." if lang != "hi" else
          "हर बार आने वाले एक साल का कैश है जो कारोबार बनाएगा — जितनी ऊँची, उतना अच्छा।")

    title2 = "Value bridge — from operations to per-share" if lang != "hi" else "मूल्य सेतु — कारोबार से प्रति शेयर तक"
    fig2 = base_figure(title2)
    fig2.add_trace(go.Waterfall(
        x=(["PV of 5y cash", "PV of terminal", "Enterprise value", "Less net debt", "Equity value"]
           if lang != "hi" else
           ["5 साल के कैश का PV", "टर्मिनल PV", "एंटरप्राइज़ वैल्यू", "शुद्ध क़र्ज़ घटाया", "इक्विटी वैल्यू"]),
        measure=["relative", "relative", "total", "relative", "total"],
        y=[sum(d["pvs"]), d["pv_terminal"], 0, -float(v["net_debt"]), 0],
        connector=dict(line=dict(color="#e8eaed")),
        increasing=dict(marker=dict(color=PRIMARY_COLOR)),
        decreasing=dict(marker=dict(color=ACCENT_COLOR)),
        totals=dict(marker=dict(color="#3D5C9E")),
        hovertemplate="%{x}: <b>%{y:,.0f}</b><extra></extra>",
    ))
    ins2 = (f"Enterprise value {fmt(d['ev'])} less net debt gives equity of "
            f"{fmt(d['equity'])} — {fmt(per_share)} per share." if lang != "hi" else
            f"एंटरप्राइज़ वैल्यू {fmt(d['ev'])} में से शुद्ध क़र्ज़ घटाने पर इक्विटी "
            f"{fmt(d['equity'])} — यानी {fmt(per_share)} प्रति शेयर।")
    g2 = ("Read left to right: business value builds up, debt is subtracted, "
          "what remains belongs to shareholders." if lang != "hi" else
          "बाएँ से दाएँ पढ़ें: कारोबार की क़ीमत जुड़ती है, क़र्ज़ घटता है, जो बचा वो शेयरधारकों का।")

    tv_share = d["pv_terminal"] / d["ev"] * 100 if d["ev"] else 0
    verdict = (f"DCF value: {fmt(per_share)} per share. Note: {tv_share:.0f}% of the value "
               f"sits in the terminal period — long-term assumptions matter most."
               if lang != "hi" else
               f"DCF मूल्य: {fmt(per_share)} प्रति शेयर। ध्यान दें: {tv_share:.0f}% क़ीमत "
               f"टर्मिनल अवधि में है — लंबी अवधि की मान्यताएँ सबसे अहम हैं।")

    kpis = [
        Kpi("Enterprise value" if lang != "hi" else "एंटरप्राइज़ वैल्यू", fmt(d["ev"])),
        Kpi("Equity value" if lang != "hi" else "इक्विटी वैल्यू", fmt(d["equity"])),
        Kpi("Value / share" if lang != "hi" else "प्रति शेयर मूल्य", fmt(per_share)),
        Kpi("WACC", f"{v['wacc_pct']:.1f}%"),
    ]
    return ModelOutput(kpis=kpis, verdict=verdict, results=[
        chart_result(title1, fig1, ins1, g1, priority=1),
        chart_result(title2, fig2, ins2, g2, priority=2),
    ])


register(ModelSpec(
    key="dcf", category="valuation",
    name=_L("DCF — Discounted Cash Flow", "DCF — डिस्काउंटेड कैश फ्लो"),
    desc=_L("Values the business from the cash it will generate in future.",
            "भविष्य में बनने वाले कैश से कारोबार की क़ीमत निकालता है।"),
    fields=_DCF_FIELDS, compute=_dcf_compute,
))


# ---------------------------------------------------------- Trading comps
_COMPS_TABLE_COLS = [
    ("peer", _L("Peer company", "समकक्ष कंपनी")),
    ("ev_ebitda", _L("EV/EBITDA", "EV/EBITDA")),
    ("pe", _L("P/E", "P/E")),
    ("ev_rev", _L("EV/Revenue", "EV/Revenue")),
]

_COMPS_FIELDS = [
    Field("revenue", _L("Target: annual revenue", "टार्गेट: सालाना राजस्व"), default=1000.0),
    Field("ebitda", _L("Target: EBITDA", "टार्गेट: EBITDA"), default=220.0),
    Field("net_income", _L("Target: net income", "टार्गेट: शुद्ध लाभ"), default=120.0),
    Field("net_debt", _L("Target: net debt", "टार्गेट: शुद्ध क़र्ज़"), default=200.0),
    Field("shares", _L("Shares outstanding", "कुल शेयर"), default=100.0, min_value=0.0001),
    Field("peers", _L("Peer multiples (2-8 rows)", "समकक्ष कंपनियों के मल्टीपल (2-8 पंक्तियाँ)"),
          "table", columns=_COMPS_TABLE_COLS, rows=4),
]


def _multiples_core(v: dict, deal: bool) -> dict | None:
    """Median-multiple math shared by comps, precedents, and the mix."""
    peers = clean_table(v["peers"], ["ev_ebitda", "pe", "ev_rev"])
    if len(peers) < 2:
        return None
    shares = max(float(v["shares"]), 1e-9)
    net_debt = float(v["net_debt"])
    implied, med = {}, {}
    if peers["ev_ebitda"].notna().sum() >= 2:
        med["EV/EBITDA"] = peers["ev_ebitda"].median()
        implied["EV/EBITDA"] = (med["EV/EBITDA"] * float(v["ebitda"]) - net_debt) / shares
    if not deal and peers["pe"].notna().sum() >= 2:
        med["P/E"] = peers["pe"].median()
        implied["P/E"] = med["P/E"] * float(v["net_income"]) / shares
    if peers["ev_rev"].notna().sum() >= 2:
        med["EV/Revenue"] = peers["ev_rev"].median()
        implied["EV/Revenue"] = (med["EV/Revenue"] * float(v["revenue"]) - net_debt) / shares
    if not implied:
        return None
    return dict(implied=implied, med=med, n_peers=len(peers),
                mid=float(np.median(list(implied.values()))))


def _ddm_core(v: dict) -> float:
    ke, g1, gt = _pct(v["ke_pct"]), _pct(v["g1_pct"]), _pct(v["gt_pct"])
    n = int(v["years_high"])
    d = float(v["d0"])
    divs, pvs = [], []
    for year in range(1, n + 1):
        d *= (1 + g1)
        divs.append(d)
        pvs.append(d / (1 + ke) ** year)
    terminal = divs[-1] * (1 + gt) / (ke - gt)
    return sum(pvs) + terminal / (1 + ke) ** n


def _multiples_valuation(v: dict, lang: str, deal: bool) -> ModelOutput:
    core = _multiples_core(v, deal)
    if core is None:
        msg = ("Add at least 2 peer rows with at least one multiple column filled."
               if lang != "hi"
               else "कम से कम 2 समकक्ष पंक्तियाँ भरें, कम से कम एक मल्टीपल कॉलम के साथ।")
        return ModelOutput(kpis=[], results=[], verdict=f"⚠️ {msg}")
    implied, med = core["implied"], core["med"]
    peers_n = core["n_peers"]

    label = ("Precedent transactions" if deal else "Trading comps") if lang != "hi" \
        else ("पिछली डील्स" if deal else "ट्रेडिंग कॉम्प्स")
    title = (f"Implied value per share — {label}" if lang != "hi"
             else f"प्रति शेयर निकला मूल्य — {label}")
    fig = base_figure(title)
    methods = list(implied)
    values = [implied[m] for m in methods]
    colors = [ACCENT_COLOR if val == max(values) else PRIMARY_COLOR for val in values]
    fig.add_trace(go.Bar(
        x=methods, y=values, marker_color=colors,
        text=[fmt(val) for val in values], textposition="outside",
        textfont=dict(color=MUTED, size=12),
        hovertemplate="%{x}: <b>%{y:,.2f}</b><extra></extra>",
    ))

    lo, hi = min(values), max(values)
    mid = float(np.median(values))
    premium_note = ""
    if deal:
        premium_note = (" Deal multiples already include the control premium buyers pay."
                        if lang != "hi" else
                        " डील मल्टीपल में ख़रीदार का कंट्रोल प्रीमियम पहले से शामिल होता है।")
    insight = ((f"Peers' median multiples imply {fmt(lo)}–{fmt(hi)} per share "
                f"(midpoint {fmt(mid)}) from {peers_n} peers.{premium_note}")
               if lang != "hi" else
               (f"{peers_n} समकक्षों के median मल्टीपल से प्रति शेयर मूल्य "
                f"{fmt(lo)}–{fmt(hi)} निकलता है (बीच का {fmt(mid)})।{premium_note}"))
    guide = ("Each bar is what the company would be worth per share if it traded "
             "at the peers' typical multiple." if lang != "hi" else
             "हर बार बताती है कि समकक्षों के आम मल्टीपल पर कंपनी की प्रति शेयर "
             "क़ीमत क्या होती।")

    kpis = [Kpi(f"Median {m}", f"{med[m]:.1f}×") for m in methods][:3]
    kpis.append(Kpi("Midpoint / share" if lang != "hi" else "बीच का मूल्य/शेयर", fmt(mid)))
    verdict = (f"{label}: {fmt(lo)}–{fmt(hi)} per share." if lang != "hi"
               else f"{label}: {fmt(lo)}–{fmt(hi)} प्रति शेयर।")
    return ModelOutput(kpis=kpis, verdict=verdict, results=[
        chart_result(title, fig, insight, guide, priority=1),
    ])


register(ModelSpec(
    key="comps", category="valuation",
    name=_L("Trading Comps — peer multiples", "ट्रेडिंग कॉम्प्स — समकक्ष मल्टीपल"),
    desc=_L("Values the company at the multiples similar listed companies trade at.",
            "जैसी listed कंपनियाँ जिन मल्टीपल पर चलती हैं, उन्हीं से क़ीमत निकालता है।"),
    fields=_COMPS_FIELDS,
    compute=lambda v, lang: _multiples_valuation(v, lang, deal=False),
))

register(ModelSpec(
    key="precedents", category="valuation",
    name=_L("Precedent Transactions — deal multiples", "पिछली डील्स — डील मल्टीपल"),
    desc=_L("Values the company at multiples paid in recent comparable acquisitions.",
            "हाल की मिलती-जुलती डील्स में चुकाए गए मल्टीपल से क़ीमत निकालता है।"),
    fields=[f for f in _COMPS_FIELDS if f.key != "net_income"],
    compute=lambda v, lang: _multiples_valuation({**v, "net_income": 0}, lang, deal=True),
))


# ----------------------------------------------------------------- DDM
_DDM_FIELDS = [
    Field("d0", _L("Latest annual dividend per share", "ताज़ा सालाना लाभांश प्रति शेयर"), default=10.0),
    Field("g1_pct", _L("High-growth dividend growth %", "शुरुआती वृद्धि %"), "percent", 12.0),
    Field("years_high", _L("High-growth years", "तेज़ वृद्धि के साल"), "int", 5),
    Field("gt_pct", _L("Long-term growth %", "दीर्घकालिक वृद्धि %"), "percent", 4.0),
    Field("ke_pct", _L("Cost of equity %", "इक्विटी लागत %"), "percent", 12.5),
]


def _ddm_compute(v: dict, lang: str) -> ModelOutput:
    ke, g1, gt = _pct(v["ke_pct"]), _pct(v["g1_pct"]), _pct(v["gt_pct"])
    n = int(v["years_high"])
    if ke <= gt:
        msg = ("Cost of equity must exceed long-term growth." if lang != "hi"
               else "इक्विटी लागत दीर्घकालिक वृद्धि से ज़्यादा होनी चाहिए।")
        return ModelOutput(kpis=[], results=[], verdict=f"⚠️ {msg}")

    d = float(v["d0"])
    divs, pvs = [], []
    for year in range(1, n + 1):
        d *= (1 + g1)
        divs.append(d)
        pvs.append(d / (1 + ke) ** year)
    terminal = divs[-1] * (1 + gt) / (ke - gt)
    pv_terminal = terminal / (1 + ke) ** n
    value = sum(pvs) + pv_terminal

    title = "Dividend stream and value" if lang != "hi" else "लाभांश धारा और मूल्य"
    fig = base_figure(title)
    fig.add_trace(go.Bar(
        x=[f"Y{y}" for y in range(1, n + 1)], y=divs, marker_color=PRIMARY_COLOR,
        text=[fmt(x) for x in divs], textposition="outside",
        textfont=dict(color=MUTED, size=11),
        hovertemplate="%{x}: <b>%{y:,.2f}</b><extra></extra>",
    ))
    insight = (f"Fair value {fmt(value)} per share — dividends growing {v['g1_pct']:.0f}% "
               f"for {n} years, then {v['gt_pct']:.0f}% forever." if lang != "hi" else
               f"उचित मूल्य {fmt(value)} प्रति शेयर — {n} साल {v['g1_pct']:.0f}% वृद्धि, "
               f"फिर हमेशा {v['gt_pct']:.0f}%।")
    guide = ("Good for steady dividend payers (banks, utilities). The value is "
             "simply all future dividends, discounted to today." if lang != "hi" else
             "नियमित लाभांश देने वाली कंपनियों के लिए सही (बैंक, utilities)। मूल्य = "
             "भविष्य के सारे लाभांश, आज की क़ीमत पर।")
    kpis = [
        Kpi("Value / share" if lang != "hi" else "प्रति शेयर मूल्य", fmt(value)),
        Kpi("PV of terminal" if lang != "hi" else "टर्मिनल का PV", fmt(pv_terminal)),
        Kpi("Cost of equity" if lang != "hi" else "इक्विटी लागत", f"{v['ke_pct']:.1f}%"),
    ]
    verdict = (f"DDM value: {fmt(value)} per share." if lang != "hi"
               else f"DDM मूल्य: {fmt(value)} प्रति शेयर।")
    return ModelOutput(kpis=kpis, verdict=verdict,
                       results=[chart_result(title, fig, insight, guide, priority=1)])


register(ModelSpec(
    key="ddm", category="valuation",
    name=_L("DDM — Dividend Discount Model", "DDM — लाभांश छूट मॉडल"),
    desc=_L("Values a steady dividend payer from its future dividends.",
            "नियमित लाभांश देने वाली कंपनी की क़ीमत उसके भावी लाभांश से।"),
    fields=_DDM_FIELDS, compute=_ddm_compute,
))


# ----------------------------------------------------------------- NAV
_NAV_COLS = [
    ("item", _L("Asset", "संपत्ति")),
    ("book", _L("Book value", "बही मूल्य")),
    ("market", _L("Market value", "बाज़ार मूल्य")),
]

_NAV_FIELDS = [
    Field("assets", _L("Assets (book vs market)", "संपत्तियाँ (बही बनाम बाज़ार)"),
          "table", columns=_NAV_COLS, rows=5),
    Field("liabilities", _L("Total liabilities", "कुल देनदारियाँ"), default=400.0),
    Field("shares", _L("Shares outstanding", "कुल शेयर"), default=100.0, min_value=0.0001),
]


def _nav_compute(v: dict, lang: str) -> ModelOutput:
    assets = clean_table(v["assets"], ["book", "market"])
    if assets.empty or assets["market"].notna().sum() == 0:
        msg = ("Add at least one asset with a market value." if lang != "hi"
               else "कम से कम एक संपत्ति का बाज़ार मूल्य भरें।")
        return ModelOutput(kpis=[], results=[], verdict=f"⚠️ {msg}")
    total_market = assets["market"].fillna(assets["book"]).sum()
    total_book = assets["book"].fillna(0).sum()
    nav = total_market - float(v["liabilities"])
    per_share = nav / max(float(v["shares"]), 1e-9)

    title = "Book vs market value of assets" if lang != "hi" else "संपत्तियाँ: बही बनाम बाज़ार मूल्य"
    fig = base_figure(title)
    names = assets["item"].fillna("—").astype(str).tolist()
    fig.add_trace(go.Bar(name="Book" if lang != "hi" else "बही",
                         x=names, y=assets["book"].fillna(0), marker_color="#3D5C9E"))
    fig.add_trace(go.Bar(name="Market" if lang != "hi" else "बाज़ार",
                         x=names, y=assets["market"].fillna(0), marker_color="#A8862F"))
    fig.update_layout(barmode="group", showlegend=True,
                      legend=dict(orientation="h", y=1.08, x=0))
    hidden = total_market - total_book
    insight = ((f"Market value of assets exceeds books by {fmt(hidden)}. "
                f"NAV after liabilities: {fmt(nav)} ({fmt(per_share)}/share).")
               if lang != "hi" else
               (f"संपत्तियों का बाज़ार मूल्य बही से {fmt(hidden)} ज़्यादा है। देनदारियाँ "
                f"घटाकर NAV: {fmt(nav)} ({fmt(per_share)}/शेयर)।"))
    guide = ("Blue = accounting value, gold = what it would fetch today. Big gaps "
             "mean hidden value (common in land, real estate)." if lang != "hi" else
             "नीला = खातों की क़ीमत, सुनहरा = आज बिकने पर क़ीमत। बड़ा फ़र्क़ = छुपी "
             "हुई क़ीमत (ज़मीन/प्रॉपर्टी में आम)।")
    kpis = [
        Kpi("Assets (market)" if lang != "hi" else "संपत्तियाँ (बाज़ार)", fmt(total_market)),
        Kpi("NAV", fmt(nav)),
        Kpi("NAV / share" if lang != "hi" else "NAV / शेयर", fmt(per_share)),
    ]
    verdict = (f"NAV: {fmt(per_share)} per share." if lang != "hi"
               else f"NAV: {fmt(per_share)} प्रति शेयर।")
    return ModelOutput(kpis=kpis, verdict=verdict,
                       results=[chart_result(title, fig, insight, guide, priority=1)])


register(ModelSpec(
    key="nav", category="valuation",
    name=_L("NAV — asset-based valuation", "NAV — संपत्ति-आधारित मूल्यांकन"),
    desc=_L("Values the company from what its assets are worth minus what it owes.",
            "संपत्तियों की क़ीमत में से देनदारियाँ घटाकर कंपनी की क़ीमत।"),
    fields=_NAV_FIELDS, compute=_nav_compute,
))


# --------------------------------------------------------------- NPV/IRR
_NPV_COLS = [("year", _L("Year", "साल")), ("cash_flow", _L("Cash flow", "कैश फ्लो"))]

_NPV_FIELDS = [
    Field("investment", _L("Initial investment (today)", "शुरुआती निवेश (आज)"), default=1000.0),
    Field("flows", _L("Future cash flows", "भावी कैश फ्लो"),
          "table", columns=_NPV_COLS, rows=6),
    Field("rate_pct", _L("Discount rate %", "छूट दर %"), "percent", 12.0),
]


def _irr(cashflows: list[float]) -> float | None:
    """Bisection IRR; cashflows[0] is negative investment."""
    def npv(rate):
        return sum(cf / (1 + rate) ** i for i, cf in enumerate(cashflows))
    lo, hi = -0.95, 10.0
    if npv(lo) * npv(hi) > 0:
        return None
    for _ in range(200):
        mid = (lo + hi) / 2
        if npv(lo) * npv(mid) <= 0:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2


def _npv_compute(v: dict, lang: str) -> ModelOutput:
    flows = clean_table(v["flows"], ["cash_flow"])
    if flows.empty:
        msg = ("Add at least one future cash flow." if lang != "hi"
               else "कम से कम एक भावी कैश फ्लो भरें।")
        return ModelOutput(kpis=[], results=[], verdict=f"⚠️ {msg}")
    cfs = flows["cash_flow"].fillna(0).tolist()
    invest = float(v["investment"])
    rate = _pct(v["rate_pct"])
    npv = -invest + sum(cf / (1 + rate) ** (i + 1) for i, cf in enumerate(cfs))
    irr = _irr([-invest] + cfs)

    cumulative = np.cumsum([-invest] + cfs)
    payback = next((i for i, c in enumerate(cumulative) if c >= 0), None)

    title = "Cumulative cash position" if lang != "hi" else "संचयी कैश स्थिति"
    fig = base_figure(title)
    xs = ([("Today" if lang != "hi" else "आज")] +
          [f"Y{i}" for i in range(1, len(cfs) + 1)])
    fig.add_trace(go.Scatter(
        x=xs, y=cumulative, mode="lines+markers",
        line=dict(color=PRIMARY_COLOR, width=2.5), marker=dict(size=8),
        hovertemplate="%{x}: <b>%{y:,.0f}</b><extra></extra>",
    ))
    fig.add_hline(y=0, line_color=ACCENT_COLOR, line_width=2)
    pb_text = (f"payback in year {payback}" if payback else "never pays back") \
        if lang != "hi" else (f"साल {payback} में लागत वसूल" if payback else "लागत वसूल नहीं होती")
    insight = ((f"NPV is {fmt(npv)} at {v['rate_pct']:.0f}% — "
                f"{'value-creating' if npv > 0 else 'value-destroying'}; {pb_text}.")
               if lang != "hi" else
               (f"{v['rate_pct']:.0f}% पर NPV {fmt(npv)} है — "
                f"{'फ़ायदे का सौदा' if npv > 0 else 'घाटे का सौदा'}; {pb_text}।"))
    guide = ("The line starts below zero (money invested) and climbs as cash "
             "returns. Where it crosses the gold line, you've earned it back."
             if lang != "hi" else
             "रेखा शून्य से नीचे शुरू होती है (लगाया पैसा) और कैश आने पर चढ़ती है। "
             "जहाँ सुनहरी रेखा पार करती है, वहाँ लागत वसूल।")
    kpis = [
        Kpi("NPV", fmt(npv)),
        Kpi("IRR", f"{irr * 100:.1f}%" if irr is not None else "—"),
        Kpi("Payback" if lang != "hi" else "लागत वसूली",
            (f"Y{payback}" if payback else "—")),
    ]
    good = npv > 0 and (irr or 0) > rate
    verdict = (("✅ Invest — returns beat the hurdle rate." if good
                else "❌ Skip — returns don't cover the hurdle rate.") if lang != "hi"
               else ("✅ निवेश करें — रिटर्न ज़रूरी दर से ऊपर है।" if good
                     else "❌ रहने दें — रिटर्न ज़रूरी दर से कम है।"))
    return ModelOutput(kpis=kpis, verdict=verdict,
                       results=[chart_result(title, fig, insight, guide, priority=1)])


register(ModelSpec(
    key="npv_irr", category="valuation",
    name=_L("NPV / IRR — investment appraisal", "NPV / IRR — निवेश जाँच"),
    desc=_L("Quick check: is a project/investment worth its cost?",
            "झटपट जाँच: कोई प्रोजेक्ट/निवेश अपनी लागत के लायक़ है या नहीं?"),
    fields=_NPV_FIELDS, compute=_npv_compute,
))


# ------------------------------------------------- ⭐ Triangulated Mix
_MIX_FIELDS = (
    [Field("use_dcf", _L("Include DCF", "DCF शामिल करें"), "bool", True)]
    + _DCF_FIELDS
    + [Field("use_comps", _L("Include trading comps", "ट्रेडिंग कॉम्प्स शामिल करें"), "bool", True),
       Field("ebitda", _L("Target: EBITDA", "टार्गेट: EBITDA"), default=220.0),
       Field("net_income", _L("Target: net income", "टार्गेट: शुद्ध लाभ"), default=120.0),
       Field("peers", _L("Peer trading multiples", "समकक्ष ट्रेडिंग मल्टीपल"),
             "table", columns=_COMPS_TABLE_COLS, rows=4),
       Field("use_prec", _L("Include precedent deals", "पिछली डील्स शामिल करें"), "bool", False),
       Field("deals", _L("Precedent deal multiples", "पिछली डील्स के मल्टीपल"),
             "table", columns=_COMPS_TABLE_COLS, rows=3),
       Field("use_ddm", _L("Include DDM (dividend payers)", "DDM शामिल करें (लाभांश देने वाली)"), "bool", False)]
    + _DDM_FIELDS
)


def _mix_compute(v: dict, lang: str) -> ModelOutput:
    hi = lang == "hi"
    components: dict[str, float] = {}
    base_weights: dict[str, float] = {}

    if v.get("use_dcf") and _pct(v["wacc_pct"]) > _pct(v["tg_pct"]):
        components["DCF"] = _dcf_core(v)["per_share"]
        base_weights["DCF"] = 0.40
    if v.get("use_comps"):
        core = _multiples_core(v, deal=False)
        if core:
            components["Comps"] = core["mid"]
            # fewer than 3 peers = thinner evidence, lower weight
            base_weights["Comps"] = 0.35 if core["n_peers"] >= 3 else 0.20
    if v.get("use_prec"):
        core = _multiples_core(v | {"peers": v["deals"], "net_income": 0}, deal=True)
        if core:
            components["Precedents"] = core["mid"]
            base_weights["Precedents"] = 0.15
    if v.get("use_ddm") and _pct(v["ke_pct"]) > _pct(v["gt_pct"]):
        components["DDM"] = _ddm_core(v)
        base_weights["DDM"] = 0.10

    if len(components) < 2:
        msg = ("Turn on at least two methods (with valid inputs) to triangulate."
               if not hi else
               "त्रिकोणन के लिए कम से कम दो तरीक़े चालू करें (सही इनपुट के साथ)।")
        return ModelOutput(kpis=[], results=[], verdict=f"⚠️ {msg}")

    total_weight = sum(base_weights[m] for m in components)
    weights = {m: base_weights[m] / total_weight for m in components}
    blended = sum(components[m] * weights[m] for m in components)
    values = list(components.values())
    dispersion = float(np.std(values))
    bear, bull = blended - dispersion, blended + dispersion

    title = ("⭐ Triangulated valuation — football field" if not hi
             else "⭐ त्रिकोणित मूल्यांकन — फ़ुटबॉल फ़ील्ड")
    fig = base_figure(title)
    methods = list(components)
    for i, m in enumerate(methods):
        val = components[m]
        fig.add_trace(go.Bar(
            y=[m], x=[val * 0.2], base=[val * 0.9], orientation="h",
            marker_color=PRIMARY_COLOR, opacity=0.75, width=0.5,
            hovertemplate=f"{m}: <b>{fmt(val)}</b> (w {weights[m]:.0%})<extra></extra>",
        ))
        fig.add_annotation(x=val, y=m, text=f"{fmt(val)} · {weights[m]:.0%}",
                           showarrow=False, yshift=22,
                           font=dict(color=MUTED, size=11))
    fig.add_vline(x=blended, line_color=ACCENT_COLOR, line_width=3,
                  annotation_text=(f"Blended {fmt(blended)}" if not hi
                                   else f"मिश्रित {fmt(blended)}"),
                  annotation_font=dict(color=ACCENT_COLOR, size=12))
    fig.update_layout(showlegend=False)

    insight = ((f"{len(components)} methods triangulate to {fmt(blended)} per share "
                f"(range {fmt(bear)}–{fmt(bull)}). Weights: "
                + ", ".join(f"{m} {weights[m]:.0%}" for m in methods) + ".")
               if not hi else
               (f"{len(components)} तरीक़ों का त्रिकोणन: {fmt(blended)} प्रति शेयर "
                f"(दायरा {fmt(bear)}–{fmt(bull)})। वज़न: "
                + ", ".join(f"{m} {weights[m]:.0%}" for m in methods) + "।"))
    guide = ("Each bar is one method's answer; the gold line is the weighted blend. "
             "Methods close together = trustworthy value; far apart = check the "
             "assumptions of the outlier." if not hi else
             "हर बार एक तरीक़े का जवाब है; सुनहरी रेखा वज़नी मिश्रण है। बार पास-पास = "
             "भरोसेमंद क़ीमत; दूर-दूर = अलग वाले तरीक़े की मान्यताएँ जाँचें।")

    agreement = dispersion / blended * 100 if blended else 0
    kpis = [
        Kpi("Blended / share" if not hi else "मिश्रित मूल्य/शेयर", fmt(blended)),
        Kpi("Bear – Bull" if not hi else "निचला – ऊपरी", f"{fmt(bear)} – {fmt(bull)}"),
        Kpi("Methods" if not hi else "तरीक़े", str(len(components))),
        Kpi("Spread" if not hi else "फैलाव", f"±{agreement:.0f}%"),
    ]
    confidence = ("high" if agreement < 15 else "medium" if agreement < 30 else "low") \
        if not hi else ("ऊँचा" if agreement < 15 else "मध्यम" if agreement < 30 else "कम")
    verdict = ((f"Triangulated value: {fmt(blended)} per share; methods agree within "
                f"±{agreement:.0f}%, so confidence is {confidence}.")
               if not hi else
               (f"त्रिकोणित मूल्य: {fmt(blended)} प्रति शेयर; तरीक़े ±{agreement:.0f}% "
                f"के भीतर सहमत हैं, भरोसा {confidence} है।"))
    return ModelOutput(kpis=kpis, verdict=verdict,
                       results=[chart_result(title, fig, insight, guide, priority=1)])


register(ModelSpec(
    key="mix_valuation", category="valuation", is_mix=True,
    name=_L("⭐ Valuation Mix — Triangulated Valuation",
            "⭐ वैल्यूएशन मिक्स — त्रिकोणित मूल्यांकन"),
    desc=_L("Runs DCF, comps, precedents and DDM together and blends them with "
            "transparent weights into one defendable value range — the way "
            "fairness opinions are built.",
            "DCF, कॉम्प्स, पिछली डील्स और DDM एक साथ चलाकर पारदर्शी वज़न से एक "
            "भरोसेमंद value range बनाता है — जैसे असली fairness opinion बनती है।"),
    fields=_MIX_FIELDS, compute=_mix_compute,
))
