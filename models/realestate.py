"""Real Estate models — cap-rate valuation, RE DCF, development pro forma,
REIT FFO/AFFO, and the Property Verdict mix."""

import numpy as np
import plotly.graph_objects as go

from core.branding import ACCENT_COLOR, PRIMARY_COLOR
from core.charts import MUTED, base_figure, chart_result, fmt
from core.result import Kpi
from models.base import Field, ModelOutput, ModelSpec, register


def _L(en: str, hi: str) -> dict:
    return {"en": en, "hi": hi}


def _pct(x) -> float:
    return float(x or 0) / 100.0


def _noi(v: dict) -> float:
    gross = float(v["rent"]) * 12 if v.get("monthly") else float(v["rent"])
    effective = gross * (1 - _pct(v["vacancy_pct"]))
    return effective * (1 - _pct(v["opex_pct"]))


_CAP_FIELDS = [
    Field("rent", _L("Annual gross rent", "सालाना कुल किराया"), default=2400000.0),
    Field("vacancy_pct", _L("Vacancy allowance %", "ख़ालीपन भत्ता %"), "percent", 5.0),
    Field("opex_pct", _L("Operating expenses % of rent", "परिचालन खर्च (किराए का %)"), "percent", 25.0),
    Field("cap_rate_pct", _L("Market cap rate %", "बाज़ार cap rate %"), "percent", 7.0),
]


def _cap_compute(v: dict, lang: str) -> ModelOutput:
    hi = lang == "hi"
    noi = _noi(v)
    cap = _pct(v["cap_rate_pct"])
    if cap <= 0:
        return ModelOutput(kpis=[], results=[], verdict="⚠️ Cap rate must be > 0.")
    value = noi / cap
    lo, hie = noi / (cap + 0.005), noi / (cap - 0.005) if cap > 0.005 else value

    caps = np.linspace(max(cap - 0.02, 0.02), cap + 0.02, 40)
    title = "Value vs cap rate" if not hi else "मूल्य बनाम cap rate"
    fig = base_figure(title)
    fig.add_trace(go.Scatter(x=caps * 100, y=noi / caps, mode="lines",
                             line=dict(color=PRIMARY_COLOR, width=2.5),
                             hovertemplate="%{x:.1f}%: <b>%{y:,.0f}</b><extra></extra>"))
    fig.add_trace(go.Scatter(x=[cap * 100], y=[value], mode="markers+text",
                             marker=dict(color=ACCENT_COLOR, size=12),
                             text=[f" {fmt(value)}"], textposition="top right",
                             textfont=dict(color=MUTED, size=12), hoverinfo="skip"))
    fig.update_xaxes(ticksuffix="%")
    insight = ((f"NOI of {fmt(noi)} at a {v['cap_rate_pct']:.1f}% cap rate values the "
                f"property at {fmt(value)} (±0.5% cap: {fmt(lo)}–{fmt(hie)}).")
               if not hi else
               (f"{fmt(noi)} के NOI पर {v['cap_rate_pct']:.1f}% cap rate से संपत्ति "
                f"{fmt(value)} की बनती है (±0.5% cap: {fmt(lo)}–{fmt(hie)})।"))
    guide = ("NOI = rent after vacancy and running costs. Value = NOI ÷ cap rate — "
             "the curve shows how sensitive price is to the market's mood."
             if not hi else
             "NOI = ख़ालीपन और खर्च के बाद का किराया। मूल्य = NOI ÷ cap rate — "
             "curve दिखाता है क़ीमत बाज़ार के मूड से कितनी हिलती है।")
    kpis = [Kpi("NOI", fmt(noi)),
            Kpi("Value" if not hi else "मूल्य", fmt(value)),
            Kpi("Range (±0.5%)" if not hi else "दायरा (±0.5%)", f"{fmt(lo)}–{fmt(hie)}")]
    return ModelOutput(kpis=kpis, verdict=insight,
                       results=[chart_result(title, fig, insight, guide, priority=1)])


register(ModelSpec(
    key="cap_rate", category="realestate",
    name=_L("Cap Rate Valuation", "Cap Rate मूल्यांकन"),
    desc=_L("Property value from its rent, the way the market prices income property.",
            "किराए से संपत्ति की क़ीमत — जैसे बाज़ार income property आँकता है।"),
    fields=_CAP_FIELDS, compute=_cap_compute,
))


_REDCF_FIELDS = _CAP_FIELDS[:3] + [
    Field("growth_pct", _L("NOI growth % / year", "NOI वृद्धि % / साल"), "percent", 4.0),
    Field("hold", _L("Holding period (years)", "होल्डिंग अवधि (साल)"), "int", 7),
    Field("discount_pct", _L("Discount rate %", "छूट दर %"), "percent", 10.0),
    Field("exit_cap_pct", _L("Exit cap rate %", "एग्ज़िट cap rate %"), "percent", 7.5),
]


def _redcf_compute(v: dict, lang: str) -> ModelOutput:
    hi = lang == "hi"
    noi = _noi(v)
    hold = max(3, min(15, int(v["hold"])))
    disc = _pct(v["discount_pct"])
    exit_cap = _pct(v["exit_cap_pct"])
    if exit_cap <= 0:
        return ModelOutput(kpis=[], results=[], verdict="⚠️ Exit cap must be > 0.")
    pvs, cur = [], noi
    for y in range(1, hold + 1):
        pvs.append(cur / (1 + disc) ** y)
        cur *= 1 + _pct(v["growth_pct"])
    exit_value = cur / exit_cap
    pv_exit = exit_value / (1 + disc) ** hold
    value = sum(pvs) + pv_exit

    title = "Income + exit value (present value)" if not hi else "आय + एग्ज़िट मूल्य (वर्तमान मूल्य)"
    fig = base_figure(title)
    xs = [f"Y{y}" for y in range(1, hold + 1)] + [("Exit" if not hi else "एग्ज़िट")]
    colors = [PRIMARY_COLOR] * hold + [ACCENT_COLOR]
    fig.add_trace(go.Bar(x=xs, y=pvs + [pv_exit], marker_color=colors,
                         hovertemplate="%{x}: <b>%{y:,.0f}</b><extra></extra>"))
    exit_share = pv_exit / value * 100 if value else 0
    insight = ((f"DCF value {fmt(value)} — {exit_share:.0f}% of it rides on the exit "
                f"sale at a {v['exit_cap_pct']:.1f}% cap.")
               if not hi else
               (f"DCF मूल्य {fmt(value)} — इसका {exit_share:.0f}% "
                f"{v['exit_cap_pct']:.1f}% cap पर एग्ज़िट बिक्री पर टिका है।"))
    guide = ("Navy bars are yearly rents in today's money; the gold bar is the "
             "resale. If gold dominates, the deal is a bet on the exit, not the "
             "rent." if not hi else
             "नीली बार आज की क़ीमत में सालाना किराए हैं; सुनहरी बार पुनर्बिक्री। "
             "सुनहरी हावी हो तो सौदा किराए पर नहीं, एग्ज़िट पर दाँव है।")
    kpis = [Kpi("DCF value" if not hi else "DCF मूल्य", fmt(value)),
            Kpi("Exit share" if not hi else "एग्ज़िट हिस्सा", f"{exit_share:.0f}%"),
            Kpi("Exit value" if not hi else "एग्ज़िट मूल्य", fmt(exit_value))]
    return ModelOutput(kpis=kpis, verdict=insight,
                       results=[chart_result(title, fig, insight, guide, priority=1)])


register(ModelSpec(
    key="re_dcf", category="realestate",
    name=_L("Real Estate DCF", "रियल एस्टेट DCF"),
    desc=_L("Property value from projected rents plus the eventual resale.",
            "अनुमानित किराए और अंतिम पुनर्बिक्री से संपत्ति की क़ीमत।"),
    fields=_REDCF_FIELDS, compute=_redcf_compute,
))


_DEV_FIELDS = [
    Field("land", _L("Land cost", "ज़मीन की लागत"), default=30000000.0),
    Field("construction", _L("Construction cost", "निर्माण लागत"), default=45000000.0),
    Field("soft_pct", _L("Soft costs % of construction", "अन्य लागत (निर्माण का %)"), "percent", 12.0),
    Field("contingency_pct", _L("Contingency % of construction", "आकस्मिक (निर्माण का %)"), "percent", 8.0),
    Field("gdv", _L("Gross development value (total sales)", "कुल बिक्री मूल्य (GDV)"), default=105000000.0),
]


def _dev_compute(v: dict, lang: str) -> ModelOutput:
    hi = lang == "hi"
    land, cons = float(v["land"]), float(v["construction"])
    soft = cons * _pct(v["soft_pct"])
    cont = cons * _pct(v["contingency_pct"])
    total = land + cons + soft + cont
    gdv = float(v["gdv"])
    profit = gdv - total
    margin = profit / total * 100 if total else 0

    title = "Development pro forma" if not hi else "डेवलपमेंट प्रो फ़ॉर्मा"
    fig = base_figure(title)
    fig.add_trace(go.Waterfall(
        x=(["Sales (GDV)", "− Land", "− Construction", "− Soft costs", "− Contingency", "Profit"]
           if not hi else
           ["बिक्री (GDV)", "− ज़मीन", "− निर्माण", "− अन्य लागत", "− आकस्मिक", "लाभ"]),
        measure=["absolute", "relative", "relative", "relative", "relative", "total"],
        y=[gdv, -land, -cons, -soft, -cont, 0],
        connector=dict(line=dict(color="#e8eaed")),
        increasing=dict(marker=dict(color=PRIMARY_COLOR)),
        decreasing=dict(marker=dict(color=ACCENT_COLOR)),
        totals=dict(marker=dict(color="#3D5C9E")),
        hovertemplate="%{x}: <b>%{y:,.0f}</b><extra></extra>",
    ))
    insight = ((f"All-in cost {fmt(total)} against sales of {fmt(gdv)} → profit "
                f"{fmt(profit)}, a {margin:.1f}% margin on cost (developers "
                f"typically want 15-20%+).")
               if not hi else
               (f"कुल लागत {fmt(total)} बनाम बिक्री {fmt(gdv)} → लाभ {fmt(profit)}, "
                f"लागत पर {margin:.1f}% मार्जिन (developer आमतौर पर 15-20%+ चाहते हैं)।"))
    guide = ("Costs stack up left to right, then sales come in; what's left is the "
             "developer's profit. The margin must also pay for time and risk."
             if not hi else
             "बाएँ से दाएँ लागतें जुड़ती हैं, फिर बिक्री आती है; जो बचा वही developer "
             "का लाभ। इस मार्जिन में समय और जोखिम की क़ीमत भी शामिल होनी चाहिए।")
    kpis = [Kpi("Profit" if not hi else "लाभ", fmt(profit)),
            Kpi("Margin on cost" if not hi else "लागत पर मार्जिन", f"{margin:.1f}%"),
            Kpi("Total cost" if not hi else "कुल लागत", fmt(total))]
    icon = "✅" if margin >= 15 else "🟡" if margin >= 8 else "❌"
    verdict = (f"{icon} {margin:.1f}% " +
               (("margin — healthy." if margin >= 15 else "margin — thin for the risk."
                 if margin >= 8 else "margin — does not pay for development risk.") if not hi else
                ("मार्जिन — सेहतमंद।" if margin >= 15 else "मार्जिन — जोखिम के लिए पतला।"
                 if margin >= 8 else "मार्जिन — जोखिम की क़ीमत नहीं निकलती।")))
    return ModelOutput(kpis=kpis, verdict=verdict,
                       results=[chart_result(title, fig, insight, guide, priority=1)])


register(ModelSpec(
    key="dev_proforma", category="realestate",
    name=_L("Development Pro Forma", "डेवलपमेंट प्रो फ़ॉर्मा"),
    desc=_L("Build-and-sell profitability: land + construction vs sales value.",
            "बनाओ-और-बेचो का हिसाब: ज़मीन + निर्माण बनाम बिक्री मूल्य।"),
    fields=_DEV_FIELDS, compute=_dev_compute,
))


_REIT_FIELDS = [
    Field("net_income", _L("Net income", "शुद्ध लाभ"), default=800.0),
    Field("depreciation", _L("Depreciation & amortization", "मूल्यह्रास"), default=450.0),
    Field("gains", _L("Gains on property sales", "संपत्ति बिक्री का लाभ"), default=120.0),
    Field("capex", _L("Recurring maintenance capex", "नियमित रखरखाव capex"), default=140.0),
    Field("shares", _L("Units/shares outstanding", "कुल यूनिट/शेयर"), default=500.0),
    Field("price", _L("Unit/share price", "यूनिट/शेयर भाव"), default=22.0),
    Field("dps", _L("Distribution per unit (annual)", "प्रति यूनिट वितरण (सालाना)"), default=1.6),
]


def _reit_compute(v: dict, lang: str) -> ModelOutput:
    hi = lang == "hi"
    ffo = float(v["net_income"]) + float(v["depreciation"]) - float(v["gains"])
    affo = ffo - float(v["capex"])
    shares = max(float(v["shares"]), 1e-9)
    affo_ps = affo / shares
    p_affo = float(v["price"]) / affo_ps if affo_ps else float("inf")
    payout = float(v["dps"]) / affo_ps * 100 if affo_ps else 0
    dist_yield = float(v["dps"]) / max(float(v["price"]), 1e-9) * 100

    title = "Net income → FFO → AFFO" if not hi else "शुद्ध लाभ → FFO → AFFO"
    fig = base_figure(title)
    fig.add_trace(go.Waterfall(
        x=(["Net income", "+ Depreciation", "− Sale gains", "FFO", "− Capex", "AFFO"]
           if not hi else
           ["शुद्ध लाभ", "+ मूल्यह्रास", "− बिक्री लाभ", "FFO", "− Capex", "AFFO"]),
        measure=["absolute", "relative", "relative", "total", "relative", "total"],
        y=[float(v["net_income"]), float(v["depreciation"]), -float(v["gains"]), 0,
           -float(v["capex"]), 0],
        connector=dict(line=dict(color="#e8eaed")),
        increasing=dict(marker=dict(color=PRIMARY_COLOR)),
        decreasing=dict(marker=dict(color=ACCENT_COLOR)),
        totals=dict(marker=dict(color="#3D5C9E")),
        hovertemplate="%{x}: <b>%{y:,.0f}</b><extra></extra>",
    ))
    insight = ((f"True cash earnings (AFFO) are {fmt(affo)} — {affo_ps:.2f}/unit. "
                f"Units trade at {p_affo:.1f}× AFFO with a {dist_yield:.1f}% yield; "
                f"payout is {payout:.0f}% of AFFO.")
               if not hi else
               (f"असल नक़द कमाई (AFFO) {fmt(affo)} है — {affo_ps:.2f}/यूनिट। भाव "
                f"{p_affo:.1f}× AFFO पर, यील्ड {dist_yield:.1f}%; वितरण AFFO का "
                f"{payout:.0f}%।"))
    guide = ("REIT profits are understated by depreciation on buildings that "
             "don't really wear out — FFO/AFFO fix that. Payout above 100% of "
             "AFFO is unsustainable." if not hi else
             "REIT का लाभ इमारतों के मूल्यह्रास से दबा दिखता है — FFO/AFFO असली "
             "तस्वीर देते हैं। AFFO से 100% ऊपर का वितरण टिक नहीं सकता।")
    kpis = [Kpi("AFFO / unit" if not hi else "AFFO / यूनिट", f"{affo_ps:.2f}"),
            Kpi("P / AFFO", f"{p_affo:.1f}×"),
            Kpi("Yield" if not hi else "यील्ड", f"{dist_yield:.1f}%"),
            Kpi("Payout of AFFO" if not hi else "AFFO का वितरण", f"{payout:.0f}%")]
    icon = "✅" if payout <= 90 else "🟡" if payout <= 100 else "❌"
    verdict = (f"{icon} " + ((f"Payout {payout:.0f}% of AFFO — "
               + ("sustainable." if payout <= 90 else "tight." if payout <= 100 else "not covered by cash earnings."))
               if not hi else
               (f"वितरण AFFO का {payout:.0f}% — "
                + ("टिकाऊ।" if payout <= 90 else "तंग।" if payout <= 100 else "नक़द कमाई से पूरा नहीं होता।"))))
    return ModelOutput(kpis=kpis, verdict=verdict,
                       results=[chart_result(title, fig, insight, guide, priority=1)])


register(ModelSpec(
    key="reit", category="realestate",
    name=_L("REIT — FFO / AFFO", "REIT — FFO / AFFO"),
    desc=_L("A REIT's real cash earnings and whether its payout is sustainable.",
            "REIT की असली नक़द कमाई, और वितरण टिकाऊ है या नहीं।"),
    fields=_REIT_FIELDS, compute=_reit_compute,
))


# ------------------------------------------- ⭐ Property Verdict mix
_MIX_FIELDS = _CAP_FIELDS + [
    Field("asking", _L("Asking price", "माँगी गई क़ीमत"), default=24000000.0),
    Field("growth_pct", _L("NOI growth % / year", "NOI वृद्धि % / साल"), "percent", 4.0),
    Field("hold", _L("Holding period (years)", "होल्डिंग अवधि (साल)"), "int", 7),
    Field("discount_pct", _L("Discount rate %", "छूट दर %"), "percent", 10.0),
    Field("exit_cap_pct", _L("Exit cap rate %", "एग्ज़िट cap rate %"), "percent", 7.5),
]


def _property_mix_compute(v: dict, lang: str) -> ModelOutput:
    hi = lang == "hi"
    noi = _noi(v)
    cap = _pct(v["cap_rate_pct"])
    exit_cap = _pct(v["exit_cap_pct"])
    if cap <= 0 or exit_cap <= 0:
        return ModelOutput(kpis=[], results=[], verdict="⚠️ Cap rates must be > 0.")
    cap_value = noi / cap
    disc = _pct(v["discount_pct"])
    hold = max(3, min(15, int(v["hold"])))
    pvs, cur = [], noi
    for y in range(1, hold + 1):
        pvs.append(cur / (1 + disc) ** y)
        cur *= 1 + _pct(v["growth_pct"])
    dcf_value = sum(pvs) + (cur / exit_cap) / (1 + disc) ** hold
    blended = (cap_value + dcf_value) / 2
    asking = float(v["asking"])
    vs_asking = (blended / asking - 1) * 100 if asking else 0
    yoc = noi / asking * 100 if asking else 0

    title = "⭐ Property verdict — value vs asking" if not hi else "⭐ संपत्ति फ़ैसला — मूल्य बनाम माँग"
    fig = base_figure(title)
    names = (["Cap-rate value", "DCF value", "Blended"] if not hi
             else ["Cap-rate मूल्य", "DCF मूल्य", "मिश्रित"])
    vals = [cap_value, dcf_value, blended]
    fig.add_trace(go.Bar(x=names, y=vals,
                         marker_color=[PRIMARY_COLOR, PRIMARY_COLOR, "#3D5C9E"],
                         text=[fmt(x) for x in vals], textposition="outside",
                         textfont=dict(color=MUTED, size=12),
                         hovertemplate="%{x}: <b>%{y:,.0f}</b><extra></extra>"))
    fig.add_hline(y=asking, line_color=ACCENT_COLOR, line_width=2.5,
                  annotation_text=(f"Asking {fmt(asking)}" if not hi
                                   else f"माँग {fmt(asking)}"),
                  annotation_font=dict(color=ACCENT_COLOR, size=12))
    insight = ((f"Two methods value the property at {fmt(blended)} (cap "
                f"{fmt(cap_value)}, DCF {fmt(dcf_value)}) vs asking {fmt(asking)} — "
                f"{vs_asking:+.0f}%. Yield on cost at asking: {yoc:.1f}% vs market "
                f"cap {v['cap_rate_pct']:.1f}%.")
               if not hi else
               (f"दो तरीक़ों से संपत्ति {fmt(blended)} की बनती है (cap {fmt(cap_value)}, "
                f"DCF {fmt(dcf_value)}) बनाम माँग {fmt(asking)} — {vs_asking:+.0f}%। "
                f"माँग पर यील्ड {yoc:.1f}% बनाम बाज़ार cap {v['cap_rate_pct']:.1f}%।"))
    guide = ("Bars = what the property is worth by two independent methods; gold "
             "line = the seller's price. Bars above the line = bargain; below = "
             "overpriced." if not hi else
             "बार = दो स्वतंत्र तरीक़ों से संपत्ति की क़ीमत; सुनहरी रेखा = विक्रेता "
             "की माँग। बार रेखा से ऊपर = सस्ता सौदा; नीचे = महँगा।")
    band = (("Buy" if vs_asking >= 5 else "Fair" if vs_asking >= -5 else "Overpriced")
            if not hi else
            ("ख़रीदें" if vs_asking >= 5 else "उचित" if vs_asking >= -5 else "महँगा"))
    kpis = [Kpi("Blended value" if not hi else "मिश्रित मूल्य", fmt(blended), band),
            Kpi("Vs asking" if not hi else "माँग से", f"{vs_asking:+.0f}%"),
            Kpi("Yield on cost" if not hi else "लागत पर यील्ड", f"{yoc:.1f}%")]
    icon = "✅" if vs_asking >= 5 else "🟡" if vs_asking >= -5 else "❌"
    verdict = f"{icon} {band} — {vs_asking:+.0f}% vs asking." if not hi \
        else f"{icon} {band} — माँग से {vs_asking:+.0f}%।"
    return ModelOutput(kpis=kpis, verdict=verdict,
                       results=[chart_result(title, fig, insight, guide, priority=1)])


register(ModelSpec(
    key="mix_realestate", category="realestate", is_mix=True,
    name=_L("⭐ RE Mix — Property Verdict", "⭐ RE मिक्स — संपत्ति फ़ैसला"),
    desc=_L("Cap-rate and DCF values blended and compared with the asking price — "
            "Buy / Fair / Overpriced.",
            "Cap-rate और DCF मूल्य मिलाकर माँगी क़ीमत से तुलना — ख़रीदें / उचित / महँगा।"),
    fields=_MIX_FIELDS, compute=_property_mix_compute,
))
