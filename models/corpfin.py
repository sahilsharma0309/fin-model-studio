"""Corporate Finance / FP&A models — 3-statement lite, break-even,
working capital, sensitivity tornado, and the Business Health Engine mix.
Pure formulas; insights and guides written for non-technical readers.
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from core.branding import ACCENT_COLOR, PRIMARY_COLOR
from core.charts import MUTED, base_figure, chart_result, fmt
from core.result import AnalysisResult, Kpi
from models.base import Field, ModelOutput, ModelSpec, register


def _L(en: str, hi: str) -> dict:
    return {"en": en, "hi": hi}


def _pct(x) -> float:
    return float(x or 0) / 100.0


# ------------------------------------------------- 3-statement (lite)
_TS_FIELDS = [
    Field("revenue", _L("Latest annual revenue", "ताज़ा सालाना राजस्व"), default=1000.0),
    Field("growth_pct", _L("Revenue growth % / year", "राजस्व वृद्धि % / साल"), "percent", 10.0),
    Field("cogs_pct", _L("COGS as % of revenue", "COGS (राजस्व का %)"), "percent", 55.0),
    Field("opex_pct", _L("Operating expenses as % of revenue", "परिचालन खर्च (राजस्व का %)"), "percent", 20.0),
    Field("da_pct", _L("D&A as % of revenue", "D&A (राजस्व का %)"), "percent", 4.0),
    Field("capex_pct", _L("Capex as % of revenue", "पूंजीगत खर्च (राजस्व का %)"), "percent", 5.0),
    Field("tax_pct", _L("Tax rate %", "कर दर %"), "percent", 25.0),
    Field("interest_pct", _L("Interest rate on debt %", "क़र्ज़ पर ब्याज %"), "percent", 9.0),
    Field("debt", _L("Opening debt", "शुरुआती क़र्ज़"), default=300.0),
    Field("cash", _L("Opening cash", "शुरुआती नक़द"), default=150.0),
    Field("payout_pct", _L("Dividend payout % of profit", "लाभांश (लाभ का %)"), "percent", 20.0),
    Field("years", _L("Forecast years (2-5)", "पूर्वानुमान के साल (2-5)"), "int", 3),
]


def _ts_compute(v: dict, lang: str) -> ModelOutput:
    hi = lang == "hi"
    years = max(2, min(5, int(v["years"])))
    rev = float(v["revenue"])
    cash = float(v["cash"])
    debt = float(v["debt"])
    rows = []
    for y in range(1, years + 1):
        rev *= 1 + _pct(v["growth_pct"])
        cogs = rev * _pct(v["cogs_pct"])
        opex = rev * _pct(v["opex_pct"])
        da = rev * _pct(v["da_pct"])
        ebitda = rev - cogs - opex
        ebit = ebitda - da
        interest = debt * _pct(v["interest_pct"])
        ebt = ebit - interest
        tax = max(ebt, 0) * _pct(v["tax_pct"])
        ni = ebt - tax
        capex = rev * _pct(v["capex_pct"])
        dividends = max(ni, 0) * _pct(v["payout_pct"])
        cfo = ni + da
        cash = cash + cfo - capex - dividends
        rows.append(dict(Year=f"Y{y}", Revenue=round(rev, 1), EBITDA=round(ebitda, 1),
                         EBIT=round(ebit, 1), Interest=round(interest, 1),
                         NetIncome=round(ni, 1), Capex=round(capex, 1),
                         Dividends=round(dividends, 1), CashEnd=round(cash, 1)))
    frame = pd.DataFrame(rows)

    title1 = "Revenue vs net income" if not hi else "राजस्व बनाम शुद्ध लाभ"
    fig1 = base_figure(title1)
    fig1.add_trace(go.Bar(name="Revenue" if not hi else "राजस्व",
                          x=frame["Year"], y=frame["Revenue"], marker_color="#3D5C9E"))
    fig1.add_trace(go.Bar(name="Net income" if not hi else "शुद्ध लाभ",
                          x=frame["Year"], y=frame["NetIncome"], marker_color="#A8862F"))
    fig1.update_layout(barmode="group", showlegend=True,
                       legend=dict(orientation="h", y=1.08, x=0))
    ni_margin = frame["NetIncome"].iloc[-1] / frame["Revenue"].iloc[-1] * 100
    ins1 = (f"By Y{years}, revenue reaches {fmt(frame['Revenue'].iloc[-1])} with a "
            f"{ni_margin:.1f}% net margin." if not hi else
            f"Y{years} तक राजस्व {fmt(frame['Revenue'].iloc[-1])} पहुँचता है, "
            f"शुद्ध मार्जिन {ni_margin:.1f}%।")
    g1 = ("Blue bars = money coming in; gold bars = what's left as profit after "
          "all costs, interest and tax." if not hi else
          "नीली बार = आमदनी; सुनहरी बार = सारे खर्च, ब्याज और कर के बाद बचा लाभ।")

    title2 = "Cash balance over the plan" if not hi else "योजना के दौरान नक़द"
    fig2 = base_figure(title2)
    fig2.add_trace(go.Scatter(
        x=frame["Year"], y=frame["CashEnd"], mode="lines+markers",
        line=dict(color=PRIMARY_COLOR, width=2.5), marker=dict(size=8),
        fill="tozeroy", fillcolor="rgba(26,43,76,0.07)",
        hovertemplate="%{x}: <b>%{y:,.0f}</b><extra></extra>",
    ))
    fig2.add_hline(y=0, line_color=ACCENT_COLOR, line_width=2)
    cash_ok = (frame["CashEnd"] > 0).all()
    ins2 = (("Cash stays positive throughout the plan." if cash_ok else
             "⚠️ Cash goes negative — the plan needs funding or cost cuts.")
            if not hi else
            ("पूरी योजना में नक़द सकारात्मक रहता है।" if cash_ok else
             "⚠️ नक़द ऋणात्मक हो जाता है — योजना को funding या खर्च-कटौती चाहिए।"))
    g2 = ("If this line touches the gold zero-line, the business runs out of money."
          if not hi else "अगर यह रेखा सुनहरी शून्य-रेखा छू ले, तो पैसा ख़त्म।")

    kpis = [
        Kpi(f"Y{years} " + ("revenue" if not hi else "राजस्व"), fmt(frame["Revenue"].iloc[-1])),
        Kpi(f"Y{years} " + ("net income" if not hi else "शुद्ध लाभ"), fmt(frame["NetIncome"].iloc[-1])),
        Kpi("Net margin" if not hi else "शुद्ध मार्जिन", f"{ni_margin:.1f}%"),
        Kpi("Closing cash" if not hi else "अंतिम नक़द", fmt(frame["CashEnd"].iloc[-1])),
    ]
    verdict = ins2
    table = AnalysisResult(
        question="Projected statements (summary)" if not hi else "अनुमानित विवरण (सार)",
        kind="dataframe", dataframe=frame, priority=3)
    return ModelOutput(kpis=kpis, verdict=verdict, results=[
        chart_result(title1, fig1, ins1, g1, priority=1),
        chart_result(title2, fig2, ins2, g2, priority=2),
        table,
    ])


register(ModelSpec(
    key="three_statement", category="corpfin",
    name=_L("3-Statement Forecast (lite)", "3-विवरण पूर्वानुमान (लाइट)"),
    desc=_L("Projects profit and cash together — the foundation of every financial plan.",
            "लाभ और नक़द साथ-साथ प्रोजेक्ट करता है — हर वित्तीय योजना की नींव।"),
    fields=_TS_FIELDS, compute=_ts_compute,
))


# ------------------------------------------------------- Break-even/CVP
_BE_FIELDS = [
    Field("price", _L("Selling price per unit", "प्रति इकाई बिक्री मूल्य"), default=500.0),
    Field("var_cost", _L("Variable cost per unit", "प्रति इकाई परिवर्ती लागत"), default=300.0),
    Field("fixed_costs", _L("Fixed costs (per year)", "स्थिर लागत (सालाना)"), default=800000.0),
    Field("volume", _L("Current yearly volume (units)", "मौजूदा सालाना बिक्री (इकाई)"), default=6000.0),
]


def _be_compute(v: dict, lang: str) -> ModelOutput:
    hi = lang == "hi"
    price, vc = float(v["price"]), float(v["var_cost"])
    fc, vol = float(v["fixed_costs"]), float(v["volume"])
    contribution = price - vc
    if contribution <= 0:
        msg = ("Price must exceed variable cost — otherwise every sale loses money."
               if not hi else "क़ीमत परिवर्ती लागत से ज़्यादा होनी चाहिए — वरना हर बिक्री घाटा है।")
        return ModelOutput(kpis=[], results=[], verdict=f"⚠️ {msg}")
    be_units = fc / contribution
    be_revenue = be_units * price
    mos = (vol - be_units) / vol * 100 if vol else 0
    profit = vol * contribution - fc

    x_max = max(vol, be_units) * 1.6
    xs = np.linspace(0, x_max, 60)
    title = "Break-even chart" if not hi else "ब्रेक-ईवन चार्ट"
    fig = base_figure(title)
    fig.add_trace(go.Scatter(x=xs, y=xs * price, mode="lines",
                             name="Revenue" if not hi else "राजस्व",
                             line=dict(color="#3D5C9E", width=2.5)))
    fig.add_trace(go.Scatter(x=xs, y=fc + xs * vc, mode="lines",
                             name="Total cost" if not hi else "कुल लागत",
                             line=dict(color="#A8862F", width=2.5)))
    fig.add_trace(go.Scatter(x=[be_units], y=[be_revenue], mode="markers+text",
                             marker=dict(color=ACCENT_COLOR, size=12),
                             text=[("Break-even" if not hi else "ब्रेक-ईवन")],
                             textposition="top left",
                             textfont=dict(color=MUTED, size=12), showlegend=False))
    fig.add_vline(x=vol, line_dash="dot", line_color=MUTED)
    fig.update_layout(showlegend=True, legend=dict(orientation="h", y=1.08, x=0))

    insight = ((f"Break-even at {be_units:,.0f} units ({fmt(be_revenue)} revenue). "
                f"Current volume {vol:,.0f} gives {fmt(profit)} profit — a "
                f"{mos:.0f}% safety margin.")
               if not hi else
               (f"{be_units:,.0f} इकाई ({fmt(be_revenue)} राजस्व) पर ब्रेक-ईवन। "
                f"मौजूदा {vol:,.0f} इकाई पर {fmt(profit)} लाभ — {mos:.0f}% सुरक्षा मार्जिन।"))
    guide = ("Where the blue line crosses the gold line, you stop losing and start "
             "earning. The dotted line is where you stand today." if not hi else
             "जहाँ नीली रेखा सुनहरी को काटती है, वहाँ से कमाई शुरू। बिंदीदार रेखा "
             "आपकी आज की स्थिति है।")
    kpis = [
        Kpi("Break-even units" if not hi else "ब्रेक-ईवन इकाइयाँ", f"{be_units:,.0f}"),
        Kpi("Break-even revenue" if not hi else "ब्रेक-ईवन राजस्व", fmt(be_revenue)),
        Kpi("Safety margin" if not hi else "सुरक्षा मार्जिन", f"{mos:.0f}%"),
        Kpi("Profit at current volume" if not hi else "मौजूदा लाभ", fmt(profit)),
    ]
    verdict = (("✅ Above break-even." if vol >= be_units else
                "⚠️ Below break-even — every year at this volume loses money.")
               if not hi else
               ("✅ ब्रेक-ईवन से ऊपर।" if vol >= be_units else
                "⚠️ ब्रेक-ईवन से नीचे — इस बिक्री पर हर साल घाटा है।"))
    return ModelOutput(kpis=kpis, verdict=verdict,
                       results=[chart_result(title, fig, insight, guide, priority=1)])


register(ModelSpec(
    key="breakeven", category="corpfin",
    name=_L("Break-even / CVP", "ब्रेक-ईवन / CVP"),
    desc=_L("How many units must you sell before you start making money?",
            "कमाई शुरू होने से पहले कितनी इकाइयाँ बेचनी पड़ेंगी?"),
    fields=_BE_FIELDS, compute=_be_compute,
))


# ------------------------------------------------- Working capital / CCC
_WC_FIELDS = [
    Field("revenue", _L("Annual revenue", "सालाना राजस्व"), default=1000.0),
    Field("cogs", _L("Annual COGS", "सालाना COGS"), default=550.0),
    Field("dso", _L("Receivable days (DSO)", "वसूली के दिन (DSO)"), "int", 45),
    Field("dio", _L("Inventory days (DIO)", "स्टॉक के दिन (DIO)"), "int", 60),
    Field("dpo", _L("Payable days (DPO)", "भुगतान के दिन (DPO)"), "int", 30),
]


def _wc_compute(v: dict, lang: str) -> ModelOutput:
    hi = lang == "hi"
    rev, cogs = float(v["revenue"]), float(v["cogs"])
    dso, dio, dpo = int(v["dso"]), int(v["dio"]), int(v["dpo"])
    ar = rev * dso / 365
    inv = cogs * dio / 365
    ap = cogs * dpo / 365
    ccc = dso + dio - dpo
    tied = ar + inv - ap

    title = "Cash conversion cycle" if not hi else "नक़द चक्र (CCC)"
    fig = base_figure(title)
    fig.add_trace(go.Waterfall(
        x=(["Receivable days", "Inventory days", "Payable days", "CCC"]
           if not hi else ["वसूली के दिन", "स्टॉक के दिन", "भुगतान के दिन", "CCC"]),
        measure=["relative", "relative", "relative", "total"],
        y=[dso, dio, -dpo, 0],
        connector=dict(line=dict(color="#e8eaed")),
        increasing=dict(marker=dict(color=PRIMARY_COLOR)),
        decreasing=dict(marker=dict(color=ACCENT_COLOR)),
        totals=dict(marker=dict(color="#3D5C9E")),
        hovertemplate="%{x}: <b>%{y}</b> days<extra></extra>",
    ))
    insight = ((f"Money stays stuck for {ccc} days per cycle — {fmt(tied)} of cash "
                f"is tied up in the business.")
               if not hi else
               (f"हर चक्र में पैसा {ccc} दिन फँसा रहता है — {fmt(tied)} नक़द कारोबार "
                f"में अटका है।"))
    guide = ("Days your cash is stuck: waiting for customers to pay (+), goods "
             "sitting in stock (+), minus the days suppliers wait for you (−). "
             "Shorter cycle = healthier cash." if not hi else
             "पैसा कितने दिन फँसता है: ग्राहक के भुगतान का इंतज़ार (+), माल स्टॉक में "
             "(+), घटाएँ जितने दिन आप supplier को रुकवाते हैं (−)। छोटा चक्र = सेहतमंद नक़द।")
    kpis = [
        Kpi("CCC", f"{ccc} " + ("days" if not hi else "दिन")),
        Kpi("Cash tied up" if not hi else "फँसा नक़द", fmt(tied)),
        Kpi("Receivables" if not hi else "बक़ाया वसूली", fmt(ar)),
        Kpi("Inventory" if not hi else "स्टॉक", fmt(inv)),
    ]
    verdict = ((f"Cutting 10 days off the cycle frees roughly {fmt((rev / 365) * 10)} in cash.")
               if not hi else
               (f"चक्र से 10 दिन घटाएँ तो लगभग {fmt((rev / 365) * 10)} नक़द छूट जाता है।"))
    return ModelOutput(kpis=kpis, verdict=verdict,
                       results=[chart_result(title, fig, insight, guide, priority=1)])


register(ModelSpec(
    key="working_capital", category="corpfin",
    name=_L("Working Capital / Cash Cycle", "कार्यशील पूंजी / नक़द चक्र"),
    desc=_L("How long cash stays stuck in receivables and stock — and how much.",
            "पैसा वसूली और स्टॉक में कितने दिन और कितना फँसा रहता है।"),
    fields=_WC_FIELDS, compute=_wc_compute,
))


# --------------------------------------------------- Sensitivity tornado
_SENS_FIELDS = [
    Field("revenue", _L("Annual revenue", "सालाना राजस्व"), default=1000.0),
    Field("cogs_pct", _L("COGS as % of revenue", "COGS (राजस्व का %)"), "percent", 55.0),
    Field("fixed_costs", _L("Fixed costs", "स्थिर लागत"), default=250.0),
    Field("swing_pct", _L("Test swing ± %", "जाँच झूला ± %"), "percent", 10.0),
]


def _sens_compute(v: dict, lang: str) -> ModelOutput:
    hi = lang == "hi"
    rev, cogs_pct = float(v["revenue"]), _pct(v["cogs_pct"])
    fc, swing = float(v["fixed_costs"]), _pct(v["swing_pct"])

    def profit(r=rev, cp=cogs_pct, f=fc):
        return r * (1 - cp) - f

    base = profit()
    drivers = {
        ("Revenue" if not hi else "राजस्व"): (profit(r=rev * (1 - swing)), profit(r=rev * (1 + swing))),
        ("COGS %" if not hi else "COGS %"): (profit(cp=cogs_pct * (1 + swing)), profit(cp=cogs_pct * (1 - swing))),
        ("Fixed costs" if not hi else "स्थिर लागत"): (profit(f=fc * (1 + swing)), profit(f=fc * (1 - swing))),
    }
    order = sorted(drivers, key=lambda d: abs(drivers[d][1] - drivers[d][0]))

    title = (f"Tornado — profit sensitivity to ±{v['swing_pct']:.0f}% swings"
             if not hi else f"टोरनेडो — ±{v['swing_pct']:.0f}% बदलाव पर लाभ की संवेदनशीलता")
    fig = base_figure(title)
    for name in order:
        lo, hie = drivers[name]
        fig.add_trace(go.Bar(y=[name], x=[lo - base], base=base, orientation="h",
                             marker_color=ACCENT_COLOR, width=0.55, showlegend=False,
                             hovertemplate=f"{name} ↓: <b>{fmt(lo)}</b><extra></extra>"))
        fig.add_trace(go.Bar(y=[name], x=[hie - base], base=base, orientation="h",
                             marker_color=PRIMARY_COLOR, width=0.55, showlegend=False,
                             hovertemplate=f"{name} ↑: <b>{fmt(hie)}</b><extra></extra>"))
    fig.add_vline(x=base, line_color=MUTED, line_width=1.5)
    fig.update_layout(barmode="overlay")

    biggest = order[-1]
    worst = min(min(vals) for vals in drivers.values())
    best = max(max(vals) for vals in drivers.values())
    insight = ((f"{biggest} is the biggest lever — its swing moves profit the most. "
                f"Single-driver range: {fmt(worst)} to {fmt(best)} around base {fmt(base)}.")
               if not hi else
               (f"{biggest} सबसे बड़ा लीवर है — उसके बदलाव से लाभ सबसे ज़्यादा हिलता है। "
                f"दायरा: {fmt(worst)} से {fmt(best)}, आधार {fmt(base)}।"))
    guide = ("The widest bar is the number to watch and protect. Navy side = driver "
             "moves in your favor; gold side = against you." if not hi else
             "सबसे चौड़ी बार वही आँकड़ा है जिस पर नज़र रखनी है। नीला पक्ष = फ़ायदे में; "
             "सुनहरा = नुक़सान में।")
    kpis = [
        Kpi("Base profit" if not hi else "आधार लाभ", fmt(base)),
        Kpi("Worst case" if not hi else "सबसे बुरा", fmt(worst)),
        Kpi("Best case" if not hi else "सबसे अच्छा", fmt(best)),
        Kpi("Biggest lever" if not hi else "सबसे बड़ा लीवर", biggest),
    ]
    verdict = ((f"Protect {biggest.lower()} first — it dominates the risk.")
               if not hi else (f"सबसे पहले {biggest} सँभालें — जोखिम वहीं सबसे बड़ा है।"))
    return ModelOutput(kpis=kpis, verdict=verdict,
                       results=[chart_result(title, fig, insight, guide, priority=1)])


register(ModelSpec(
    key="sensitivity", category="corpfin",
    name=_L("Sensitivity — Tornado", "संवेदनशीलता — टोरनेडो"),
    desc=_L("Which number hurts profit most when it moves? Find your biggest lever.",
            "कौन-सा आँकड़ा हिलने पर लाभ सबसे ज़्यादा हिलता है? अपना सबसे बड़ा लीवर जानें।"),
    fields=_SENS_FIELDS, compute=_sens_compute,
))


# ------------------------------------- ⭐ Mix: Business Health Engine
_MIX_FIELDS = [
    Field("revenue", _L("Annual revenue", "सालाना राजस्व"), default=1000.0),
    Field("revenue_growth_pct", _L("Revenue growth % vs last year", "राजस्व वृद्धि % (पिछले साल से)"), "percent", 10.0),
    Field("ebitda", _L("EBITDA", "EBITDA"), default=180.0),
    Field("net_income", _L("Net income", "शुद्ध लाभ"), default=90.0),
    Field("cash", _L("Cash balance", "नक़द"), default=150.0),
    Field("debt", _L("Total debt", "कुल क़र्ज़"), default=300.0),
    Field("current_assets", _L("Current assets", "चालू संपत्तियाँ"), default=400.0),
    Field("current_liabilities", _L("Current liabilities", "चालू देनदारियाँ"), default=250.0),
    Field("dso", _L("Receivable days", "वसूली के दिन"), "int", 45),
    Field("dio", _L("Inventory days", "स्टॉक के दिन"), "int", 60),
    Field("dpo", _L("Payable days", "भुगतान के दिन"), "int", 30),
]


def _score(value, lo, hie, invert=False) -> float:
    """Map value onto 0-100 between lo (0) and hi (100)."""
    span = (value - lo) / (hie - lo) if hie != lo else 0
    score = min(max(span, 0), 1) * 100
    return 100 - score if invert else score


def _health_compute(v: dict, lang: str) -> ModelOutput:
    hi = lang == "hi"
    rev = max(float(v["revenue"]), 1e-9)
    ebitda = float(v["ebitda"])
    margin = ebitda / rev * 100
    current_ratio = float(v["current_assets"]) / max(float(v["current_liabilities"]), 1e-9)
    leverage = float(v["debt"]) / ebitda if ebitda > 0 else 99
    ccc = int(v["dso"]) + int(v["dio"]) - int(v["dpo"])
    growth = float(v["revenue_growth_pct"])

    parts = {
        ("Profitability" if not hi else "लाभप्रदता"): (_score(margin, 0, 30), 0.25),
        ("Liquidity" if not hi else "तरलता"): (_score(current_ratio, 0.5, 2.0), 0.20),
        ("Leverage" if not hi else "क़र्ज़ भार"): (_score(leverage, 0, 6, invert=True), 0.25),
        ("Efficiency" if not hi else "दक्षता"): (_score(ccc, 0, 120, invert=True), 0.15),
        ("Growth" if not hi else "वृद्धि"): (_score(growth, -10, 25), 0.15),
    }
    composite = sum(score * weight for score, weight in parts.values())

    title = "⭐ Business health scorecard" if not hi else "⭐ कारोबार सेहत स्कोरकार्ड"
    fig = base_figure(title)
    names = list(parts)
    scores = [parts[n][0] for n in names]
    weakest = names[int(np.argmin(scores))]
    colors = [ACCENT_COLOR if n == weakest else PRIMARY_COLOR for n in names]
    fig.add_trace(go.Bar(
        x=scores, y=names, orientation="h", marker_color=colors,
        text=[f"{s:.0f}" for s in scores], textposition="outside",
        textfont=dict(color=MUTED, size=12),
        hovertemplate="%{y}: <b>%{x:.0f}</b>/100<extra></extra>",
    ))
    fig.update_xaxes(range=[0, 112])

    insight = ((f"Composite health: {composite:.0f}/100. Weakest area: {weakest} "
                f"({parts[weakest][0]:.0f}/100) — fixing it moves the score most.")
               if not hi else
               (f"कुल सेहत: {composite:.0f}/100। सबसे कमज़ोर: {weakest} "
                f"({parts[weakest][0]:.0f}/100) — इसे सुधारने से स्कोर सबसे ज़्यादा बढ़ेगा।"))
    guide = ("Each bar is one pillar of the business scored out of 100 — profit, "
             "cash cushion, debt load, cash cycle, growth. The gold bar is the "
             "weakest pillar." if not hi else
             "हर बार कारोबार का एक स्तंभ है, 100 में स्कोर — लाभ, नक़द, क़र्ज़, नक़द "
             "चक्र, वृद्धि। सुनहरी बार सबसे कमज़ोर स्तंभ है।")

    band = (("Strong" if composite >= 75 else "Stable" if composite >= 50 else "Stressed")
            if not hi else
            ("मज़बूत" if composite >= 75 else "स्थिर" if composite >= 50 else "दबाव में"))
    runway = ""
    ni = float(v["net_income"])
    if ni < 0:
        months = float(v["cash"]) / (abs(ni) / 12) if ni else 0
        runway = (f" Cash runway ≈ {months:.0f} months at current losses."
                  if not hi else f" मौजूदा घाटे पर नक़द ≈ {months:.0f} महीने चलेगा।")
    verdict = ((f"Health {composite:.0f}/100 — {band}. EBITDA margin {margin:.1f}%, "
                f"debt/EBITDA {leverage:.1f}×, CCC {ccc} days.{runway}")
               if not hi else
               (f"सेहत {composite:.0f}/100 — {band}। EBITDA मार्जिन {margin:.1f}%, "
                f"क़र्ज़/EBITDA {leverage:.1f}×, CCC {ccc} दिन।{runway}"))
    kpis = [
        Kpi("Health score" if not hi else "सेहत स्कोर", f"{composite:.0f}/100", band),
        Kpi("EBITDA margin" if not hi else "EBITDA मार्जिन", f"{margin:.1f}%"),
        Kpi("Debt / EBITDA" if not hi else "क़र्ज़ / EBITDA", f"{leverage:.1f}×"),
        Kpi("CCC", f"{ccc} " + ("days" if not hi else "दिन")),
    ]
    return ModelOutput(kpis=kpis, verdict=verdict,
                       results=[chart_result(title, fig, insight, guide, priority=1)])


register(ModelSpec(
    key="mix_corpfin", category="corpfin", is_mix=True,
    name=_L("⭐ CorpFin Mix — Business Health Engine",
            "⭐ कॉर्पफ़िन मिक्स — कारोबार सेहत इंजन"),
    desc=_L("Blends profitability, liquidity, leverage, efficiency and growth into "
            "one 0-100 health score with the weakest pillar highlighted.",
            "लाभ, तरलता, क़र्ज़, दक्षता और वृद्धि मिलाकर 0-100 सेहत स्कोर — सबसे "
            "कमज़ोर स्तंभ highlight के साथ।"),
    fields=_MIX_FIELDS, compute=_health_compute,
))
