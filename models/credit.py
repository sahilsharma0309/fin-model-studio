"""Credit & Banking models — debt capacity, debt schedule with cash sweep,
Altman Z-score, loan amortization (EMI), project-finance DSCR, and the
Credit Risk Composite mix with an indicative rating band."""

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


# ----------------------------------------------------- Debt capacity
_CAP_FIELDS = [
    Field("ebitda", _L("EBITDA", "EBITDA"), default=200.0),
    Field("current_debt", _L("Current total debt", "मौजूदा कुल क़र्ज़"), default=450.0),
    Field("max_leverage", _L("Max Debt/EBITDA lenders allow (×)", "अधिकतम क़र्ज़/EBITDA (×)"), default=4.0),
    Field("interest_pct", _L("Interest rate on new debt %", "नए क़र्ज़ पर ब्याज %"), "percent", 9.5),
    Field("min_coverage", _L("Min EBITDA/interest coverage (×)", "न्यूनतम EBITDA/ब्याज कवरेज (×)"), default=3.0),
]


def _cap_compute(v: dict, lang: str) -> ModelOutput:
    hi = lang == "hi"
    ebitda = float(v["ebitda"])
    by_leverage = ebitda * float(v["max_leverage"])
    rate = _pct(v["interest_pct"])
    by_coverage = (ebitda / float(v["min_coverage"])) / rate if rate else by_leverage
    capacity = min(by_leverage, by_coverage)
    binding = ("Leverage cap" if by_leverage <= by_coverage else "Coverage test") \
        if not hi else ("Leverage सीमा" if by_leverage <= by_coverage else "कवरेज परीक्षा")
    headroom = capacity - float(v["current_debt"])

    title = "Debt capacity vs current debt" if not hi else "क़र्ज़ क्षमता बनाम मौजूदा क़र्ज़"
    fig = base_figure(title)
    names = ([f"Leverage cap ({v['max_leverage']:.1f}×)", f"Coverage cap ({v['min_coverage']:.1f}×)",
              "Current debt"] if not hi else
             [f"Leverage सीमा ({v['max_leverage']:.1f}×)", f"कवरेज सीमा ({v['min_coverage']:.1f}×)",
              "मौजूदा क़र्ज़"])
    vals = [by_leverage, by_coverage, float(v["current_debt"])]
    colors = [PRIMARY_COLOR, PRIMARY_COLOR, ACCENT_COLOR]
    fig.add_trace(go.Bar(x=names, y=vals, marker_color=colors,
                         text=[fmt(x) for x in vals], textposition="outside",
                         textfont=dict(color=MUTED, size=12),
                         hovertemplate="%{x}: <b>%{y:,.0f}</b><extra></extra>"))
    insight = ((f"The business can carry up to {fmt(capacity)} of debt "
                f"(binding constraint: {binding}). Headroom vs today: {fmt(headroom)}.")
               if not hi else
               (f"कारोबार अधिकतम {fmt(capacity)} क़र्ज़ उठा सकता है (बाधा: {binding})। "
                f"आज से गुंजाइश: {fmt(headroom)}।"))
    guide = ("Lenders test two limits — total debt vs profit, and profit vs "
             "interest bill. The lower navy bar is your real ceiling; the gold "
             "bar is where you stand." if not hi else
             "क़र्ज़दाता दो सीमाएँ देखते हैं — कुल क़र्ज़ बनाम कमाई, और कमाई बनाम "
             "ब्याज। नीची नीली बार असली छत है; सुनहरी बार आपकी आज की जगह।")
    kpis = [
        Kpi("Debt capacity" if not hi else "क़र्ज़ क्षमता", fmt(capacity)),
        Kpi("Headroom" if not hi else "गुंजाइश", fmt(headroom)),
        Kpi("Binding limit" if not hi else "असली बाधा", binding),
    ]
    verdict = ((f"{'✅ Room to borrow ' + fmt(headroom) if headroom > 0 else '⚠️ Over capacity by ' + fmt(-headroom)}.")
               if not hi else
               (f"{'✅ ' + fmt(headroom) + ' और उधार की गुंजाइश' if headroom > 0 else '⚠️ क्षमता से ' + fmt(-headroom) + ' ज़्यादा क़र्ज़'}।"))
    return ModelOutput(kpis=kpis, verdict=verdict,
                       results=[chart_result(title, fig, insight, guide, priority=1)])


register(ModelSpec(
    key="debt_capacity", category="credit",
    name=_L("Debt Capacity & Headroom", "क़र्ज़ क्षमता व गुंजाइश"),
    desc=_L("How much debt can the business safely carry, and how much room is left?",
            "कारोबार कितना क़र्ज़ सुरक्षित उठा सकता है, और कितनी जगह बची है?"),
    fields=_CAP_FIELDS, compute=_cap_compute,
))


# ------------------------------------------- Debt schedule (cash sweep)
_SCHED_FIELDS = [
    Field("debt", _L("Opening debt", "शुरुआती क़र्ज़"), default=500.0),
    Field("interest_pct", _L("Interest rate %", "ब्याज दर %"), "percent", 9.0),
    Field("ebitda", _L("EBITDA (year 1)", "EBITDA (साल 1)"), default=180.0),
    Field("growth_pct", _L("EBITDA growth % / year", "EBITDA वृद्धि % / साल"), "percent", 6.0),
    Field("conv_pct", _L("EBITDA available for debt service %", "क़र्ज़ सेवा के लिए EBITDA %"), "percent", 50.0),
    Field("years", _L("Years to model (3-8)", "साल (3-8)"), "int", 6),
]


def _sched_compute(v: dict, lang: str) -> ModelOutput:
    hi = lang == "hi"
    debt = float(v["debt"])
    ebitda = float(v["ebitda"])
    years = max(3, min(8, int(v["years"])))
    rate = _pct(v["interest_pct"])
    rows, payoff_year, total_interest = [], None, 0.0
    for y in range(1, years + 1):
        interest = debt * rate
        total_interest += interest
        available = ebitda * _pct(v["conv_pct"])
        paydown = min(max(available - interest, 0), debt)
        closing = debt - paydown
        coverage = ebitda / interest if interest else float("inf")
        rows.append(dict(Year=f"Y{y}", Opening=round(debt, 1), Interest=round(interest, 1),
                         Paydown=round(paydown, 1), Closing=round(closing, 1),
                         Coverage=round(coverage, 1)))
        if closing <= 0 and payoff_year is None:
            payoff_year = y
        debt = closing
        ebitda *= 1 + _pct(v["growth_pct"])
    frame = pd.DataFrame(rows)

    title = "Debt schedule with cash sweep" if not hi else "क़र्ज़ अनुसूची (cash sweep)"
    fig = base_figure(title)
    fig.add_trace(go.Bar(x=frame["Year"], y=frame["Closing"], marker_color=PRIMARY_COLOR,
                         name="Debt" if not hi else "क़र्ज़",
                         text=[fmt(x) for x in frame["Closing"]], textposition="outside",
                         textfont=dict(color=MUTED, size=11),
                         hovertemplate="%{x}: <b>%{y:,.0f}</b><extra></extra>"))
    insight = ((f"Debt falls to {fmt(frame['Closing'].iloc[-1])} by Y{years}; "
                f"{'fully repaid in Y' + str(payoff_year) if payoff_year else 'not fully repaid in the window'}; "
                f"total interest paid {fmt(total_interest)}.")
               if not hi else
               (f"Y{years} तक क़र्ज़ {fmt(frame['Closing'].iloc[-1])} रह जाता है; "
                f"{'Y' + str(payoff_year) + ' में पूरा चुकता' if payoff_year else 'इस अवधि में पूरा नहीं चुकता'}; "
                f"कुल ब्याज {fmt(total_interest)}।"))
    guide = ("Each bar is the loan left at year-end after the business sweeps its "
             "spare cash into repayment. Falling fast = healthy." if not hi else
             "हर बार साल के अंत में बचा क़र्ज़ है, जब कारोबार फ़ालतू कैश चुकौती में "
             "लगा देता है। तेज़ी से गिरे = सेहतमंद।")
    kpis = [
        Kpi(f"Y{years} " + ("debt" if not hi else "क़र्ज़"), fmt(frame["Closing"].iloc[-1])),
        Kpi("Payoff" if not hi else "पूरा चुकता", f"Y{payoff_year}" if payoff_year else "—"),
        Kpi("Total interest" if not hi else "कुल ब्याज", fmt(total_interest)),
        Kpi("Y1 coverage" if not hi else "Y1 कवरेज", f"{frame['Coverage'].iloc[0]:.1f}×"),
    ]
    verdict = insight
    table = AnalysisResult(question="Schedule" if not hi else "अनुसूची",
                           kind="dataframe", dataframe=frame, priority=2)
    return ModelOutput(kpis=kpis, verdict=verdict,
                       results=[chart_result(title, fig, insight, guide, priority=1), table])


register(ModelSpec(
    key="debt_schedule", category="credit",
    name=_L("Debt Schedule — cash sweep", "क़र्ज़ अनुसूची — cash sweep"),
    desc=_L("Year-by-year loan paydown from the business's spare cash.",
            "कारोबार के फ़ालतू कैश से साल-दर-साल क़र्ज़ चुकौती।"),
    fields=_SCHED_FIELDS, compute=_sched_compute,
))


# ----------------------------------------------------- Altman Z-score
_Z_FIELDS = [
    Field("wc", _L("Working capital (CA − CL)", "कार्यशील पूंजी (CA − CL)"), default=150.0),
    Field("re", _L("Retained earnings", "संचित लाभ"), default=300.0),
    Field("ebit", _L("EBIT", "EBIT"), default=160.0),
    Field("mktcap", _L("Market value of equity", "इक्विटी का बाज़ार मूल्य"), default=900.0),
    Field("sales", _L("Annual sales", "सालाना बिक्री"), default=1200.0),
    Field("assets", _L("Total assets", "कुल संपत्तियाँ"), default=1000.0),
    Field("liabilities", _L("Total liabilities", "कुल देनदारियाँ"), default=600.0),
]


def _z_core(v: dict) -> dict:
    assets = max(float(v["assets"]), 1e-9)
    liab = max(float(v["liabilities"]), 1e-9)
    parts = {
        "A": 1.2 * float(v["wc"]) / assets,
        "B": 1.4 * float(v["re"]) / assets,
        "C": 3.3 * float(v["ebit"]) / assets,
        "D": 0.6 * float(v["mktcap"]) / liab,
        "E": 1.0 * float(v["sales"]) / assets,
    }
    return dict(parts=parts, z=sum(parts.values()))


def _z_compute(v: dict, lang: str) -> ModelOutput:
    hi = lang == "hi"
    d = _z_core(v)
    z = d["z"]
    zone = (("Safe" if z > 2.99 else "Grey zone" if z >= 1.81 else "Distress") if not hi
            else ("सुरक्षित" if z > 2.99 else "धूसर क्षेत्र" if z >= 1.81 else "संकट"))

    labels = (["Working capital", "Retained earnings", "EBIT", "Market equity", "Sales turn"]
              if not hi else
              ["कार्यशील पूंजी", "संचित लाभ", "EBIT", "बाज़ार इक्विटी", "बिक्री दक्षता"])
    title = f"Altman Z-score = {z:.2f}" if not hi else f"Altman Z-स्कोर = {z:.2f}"
    fig = base_figure(title)
    vals = list(d["parts"].values())
    weakest = int(np.argmin(vals))
    colors = [ACCENT_COLOR if i == weakest else PRIMARY_COLOR for i in range(5)]
    fig.add_trace(go.Bar(x=labels, y=vals, marker_color=colors,
                         text=[f"{x:.2f}" for x in vals], textposition="outside",
                         textfont=dict(color=MUTED, size=12),
                         hovertemplate="%{x}: <b>%{y:.2f}</b><extra></extra>"))
    insight = ((f"Z = {z:.2f} → {zone}. Thresholds: above 2.99 safe, below 1.81 "
                f"distress risk. Weakest component: {labels[weakest]}.")
               if not hi else
               (f"Z = {z:.2f} → {zone}। सीमाएँ: 2.99 से ऊपर सुरक्षित, 1.81 से नीचे "
                f"संकट का जोखिम। सबसे कमज़ोर हिस्सा: {labels[weakest]}।"))
    guide = ("A 90-year-tested bankruptcy early-warning score built from five "
             "ratios. Each bar shows how much that ratio adds; the gold bar is "
             "the weak spot." if not hi else
             "पाँच अनुपातों से बना दिवालियापन की अग्रिम चेतावनी का आज़माया हुआ "
             "स्कोर। हर बार उस अनुपात का योगदान है; सुनहरी बार कमज़ोर कड़ी।")
    kpis = [
        Kpi("Z-score" if not hi else "Z-स्कोर", f"{z:.2f}", zone),
        Kpi("Safe above" if not hi else "सुरक्षित सीमा", "2.99"),
        Kpi("Distress below" if not hi else "संकट सीमा", "1.81"),
    ]
    icon = "✅" if z > 2.99 else "🟡" if z >= 1.81 else "❌"
    verdict = f"{icon} Z = {z:.2f} — {zone}."
    return ModelOutput(kpis=kpis, verdict=verdict,
                       results=[chart_result(title, fig, insight, guide, priority=1)])


register(ModelSpec(
    key="altman_z", category="credit",
    name=_L("Altman Z-Score — bankruptcy risk", "Altman Z-स्कोर — दिवालियापन जोखिम"),
    desc=_L("Five-ratio early warning of financial distress.",
            "पाँच अनुपातों से वित्तीय संकट की अग्रिम चेतावनी।"),
    fields=_Z_FIELDS, compute=_z_compute,
))


# --------------------------------------------------- Loan amortization
_EMI_FIELDS = [
    Field("principal", _L("Loan amount", "क़र्ज़ राशि"), default=5000000.0),
    Field("rate_pct", _L("Annual interest rate %", "सालाना ब्याज दर %"), "percent", 9.0),
    Field("years", _L("Tenor (years)", "अवधि (साल)"), "int", 20),
]


def _emi_compute(v: dict, lang: str) -> ModelOutput:
    hi = lang == "hi"
    p = float(v["principal"])
    n = int(v["years"]) * 12
    r = _pct(v["rate_pct"]) / 12
    emi = p * r * (1 + r) ** n / ((1 + r) ** n - 1) if r else p / n
    balance, yearly = p, []
    for month in range(1, n + 1):
        interest = balance * r
        principal_part = emi - interest
        balance -= principal_part
        if month % 12 == 0 or month == n:
            yearly.append(dict(year=(month + 11) // 12, balance=max(balance, 0)))
    total_paid = emi * n
    total_interest = total_paid - p

    title = "Loan balance over time" if not hi else "क़र्ज़ शेष समय के साथ"
    fig = base_figure(title)
    fig.add_trace(go.Scatter(
        x=[f"Y{row['year']}" for row in yearly], y=[row["balance"] for row in yearly],
        mode="lines", line=dict(color=PRIMARY_COLOR, width=2.5),
        fill="tozeroy", fillcolor="rgba(26,43,76,0.07)",
        hovertemplate="%{x}: <b>%{y:,.0f}</b><extra></extra>",
    ))
    insight = ((f"EMI {fmt(emi)}/month. Over the full tenor you pay {fmt(total_paid)} "
                f"— of which {fmt(total_interest)} is interest "
                f"({total_interest / p * 100:.0f}% of the loan).")
               if not hi else
               (f"EMI {fmt(emi)}/महीना। पूरी अवधि में {fmt(total_paid)} चुकाते हैं — "
                f"जिसमें {fmt(total_interest)} ब्याज है (क़र्ज़ का "
                f"{total_interest / p * 100:.0f}%)।"))
    guide = ("Early years barely dent the loan because most of the EMI is "
             "interest; the curve steepens later. Prepaying early saves the most."
             if not hi else
             "शुरुआती सालों में क़र्ज़ मुश्किल से घटता है क्योंकि EMI का बड़ा हिस्सा "
             "ब्याज होता है; बाद में रफ़्तार बढ़ती है। जल्दी prepay करने पर सबसे "
             "ज़्यादा बचत।")
    kpis = [
        Kpi("EMI", fmt(emi)),
        Kpi("Total interest" if not hi else "कुल ब्याज", fmt(total_interest)),
        Kpi("Total paid" if not hi else "कुल भुगतान", fmt(total_paid)),
    ]
    verdict = insight
    return ModelOutput(kpis=kpis, verdict=verdict,
                       results=[chart_result(title, fig, insight, guide, priority=1)])


register(ModelSpec(
    key="loan_amort", category="credit",
    name=_L("Loan Amortization — EMI", "क़र्ज़ किस्त — EMI"),
    desc=_L("EMI, total interest, and how the balance actually falls.",
            "EMI, कुल ब्याज, और क़र्ज़ असल में कैसे घटता है।"),
    fields=_EMI_FIELDS, compute=_emi_compute,
))


# --------------------------------------------------- Project finance DSCR
_DSCR_FIELDS = [
    Field("debt", _L("Project debt", "प्रोजेक्ट क़र्ज़"), default=1000.0),
    Field("rate_pct", _L("Interest rate %", "ब्याज दर %"), "percent", 10.0),
    Field("tenor", _L("Debt tenor (years)", "क़र्ज़ अवधि (साल)"), "int", 10),
    Field("cfads", _L("Year-1 cash available for debt service (CFADS)",
                      "साल-1 क़र्ज़ सेवा हेतु कैश (CFADS)"), default=180.0),
    Field("growth_pct", _L("CFADS growth % / year", "CFADS वृद्धि % / साल"), "percent", 3.0),
]


def _dscr_compute(v: dict, lang: str) -> ModelOutput:
    hi = lang == "hi"
    debt = float(v["debt"])
    tenor = max(3, min(25, int(v["tenor"])))
    r = _pct(v["rate_pct"])
    annuity = debt * r * (1 + r) ** tenor / ((1 + r) ** tenor - 1) if r else debt / tenor
    cfads = float(v["cfads"])
    dscrs = []
    for y in range(1, tenor + 1):
        dscrs.append(cfads / annuity if annuity else float("inf"))
        cfads *= 1 + _pct(v["growth_pct"])
    min_dscr, avg_dscr = min(dscrs), float(np.mean(dscrs))

    title = "DSCR by year" if not hi else "साल-दर-साल DSCR"
    fig = base_figure(title)
    fig.add_trace(go.Scatter(
        x=[f"Y{y}" for y in range(1, tenor + 1)], y=dscrs, mode="lines+markers",
        line=dict(color=PRIMARY_COLOR, width=2.5), marker=dict(size=7),
        hovertemplate="%{x}: <b>%{y:.2f}×</b><extra></extra>",
    ))
    fig.add_hline(y=1.0, line_color=ACCENT_COLOR, line_width=2,
                  annotation_text="1.0×", annotation_font=dict(color=ACCENT_COLOR))
    fig.add_hline(y=1.3, line_dash="dot", line_color=MUTED,
                  annotation_text=("Typical covenant 1.3×" if not hi else "आम शर्त 1.3×"),
                  annotation_font=dict(color=MUTED, size=11))
    insight = ((f"Debt service is {fmt(annuity)}/yr. Min DSCR {min_dscr:.2f}×, "
                f"average {avg_dscr:.2f}× over {tenor} years.")
               if not hi else
               (f"सालाना क़र्ज़ सेवा {fmt(annuity)}। न्यूनतम DSCR {min_dscr:.2f}×, "
                f"औसत {avg_dscr:.2f}× ({tenor} साल में)।"))
    guide = ("DSCR = project cash ÷ loan payment. Above the gold 1.0× line the "
             "project pays its own loan; banks usually want 1.3× or better "
             "(dotted line)." if not hi else
             "DSCR = प्रोजेक्ट का कैश ÷ क़र्ज़ की किस्त। सुनहरी 1.0× रेखा से ऊपर "
             "प्रोजेक्ट अपना क़र्ज़ खुद चुकाता है; बैंक आमतौर पर 1.3× चाहते हैं "
             "(बिंदीदार रेखा)।")
    kpis = [
        Kpi("Min DSCR" if not hi else "न्यूनतम DSCR", f"{min_dscr:.2f}×"),
        Kpi("Avg DSCR" if not hi else "औसत DSCR", f"{avg_dscr:.2f}×"),
        Kpi("Annual debt service" if not hi else "सालाना क़र्ज़ सेवा", fmt(annuity)),
    ]
    icon = "✅" if min_dscr >= 1.3 else "🟡" if min_dscr >= 1.0 else "❌"
    verdict = ((f"{icon} Min DSCR {min_dscr:.2f}× — "
                f"{'bankable' if min_dscr >= 1.3 else 'tight' if min_dscr >= 1.0 else 'project cannot service its debt'}.")
               if not hi else
               (f"{icon} न्यूनतम DSCR {min_dscr:.2f}× — "
                f"{'bank-योग्य' if min_dscr >= 1.3 else 'तंग' if min_dscr >= 1.0 else 'प्रोजेक्ट क़र्ज़ नहीं चुका सकता'}।"))
    return ModelOutput(kpis=kpis, verdict=verdict,
                       results=[chart_result(title, fig, insight, guide, priority=1)])


register(ModelSpec(
    key="dscr", category="credit",
    name=_L("Project Finance — DSCR", "प्रोजेक्ट फ़ाइनेंस — DSCR"),
    desc=_L("Can the project's cash comfortably cover its loan payments each year?",
            "क्या प्रोजेक्ट का कैश हर साल क़र्ज़ की किस्तें आराम से चुका सकता है?"),
    fields=_DSCR_FIELDS, compute=_dscr_compute,
))


# ------------------------------------------- ⭐ Credit Risk Composite
_MIX_FIELDS = [
    Field("revenue", _L("Annual revenue", "सालाना राजस्व"), default=1200.0),
    Field("ebitda", _L("EBITDA", "EBITDA"), default=200.0),
    Field("interest", _L("Annual interest expense", "सालाना ब्याज खर्च"), default=45.0),
    Field("debt", _L("Total debt", "कुल क़र्ज़"), default=450.0),
    Field("current_assets", _L("Current assets", "चालू संपत्तियाँ"), default=380.0),
    Field("current_liabilities", _L("Current liabilities", "चालू देनदारियाँ"), default=260.0),
] + _Z_FIELDS


def _band(score: float) -> str:
    for cutoff, name in ((85, "AAA/AA"), (70, "A"), (55, "BBB"),
                         (40, "BB"), (25, "B"), (0, "CCC")):
        if score >= cutoff:
            return name
    return "CCC"


def _credit_mix_compute(v: dict, lang: str) -> ModelOutput:
    hi = lang == "hi"
    ebitda = max(float(v["ebitda"]), 1e-9)
    leverage = float(v["debt"]) / ebitda
    coverage = ebitda / max(float(v["interest"]), 1e-9)
    margin = ebitda / max(float(v["revenue"]), 1e-9) * 100
    current_ratio = float(v["current_assets"]) / max(float(v["current_liabilities"]), 1e-9)
    z = _z_core(v)["z"]

    def clamp(x):
        return min(max(x, 0), 100)

    parts = {
        ("Leverage" if not hi else "क़र्ज़ भार"): (clamp((6 - leverage) / 6 * 100), 0.25),
        ("Interest coverage" if not hi else "ब्याज कवरेज"): (clamp((coverage - 1) / 7 * 100), 0.25),
        ("Profitability" if not hi else "लाभप्रदता"): (clamp(margin / 30 * 100), 0.20),
        ("Liquidity" if not hi else "तरलता"): (clamp((current_ratio - 0.5) / 1.5 * 100), 0.15),
        ("Z-score" if not hi else "Z-स्कोर"): (clamp((z - 1) / 3 * 100), 0.15),
    }
    composite = sum(score * weight for score, weight in parts.values())
    rating = _band(composite)
    grade = (("Investment grade" if composite >= 55 else "Speculative") if not hi
             else ("निवेश-योग्य" if composite >= 55 else "जोखिम-भरा"))

    title = f"⭐ Credit scorecard — indicative {rating}" if not hi \
        else f"⭐ क्रेडिट स्कोरकार्ड — सांकेतिक {rating}"
    fig = base_figure(title)
    names = list(parts)
    scores = [parts[n][0] for n in names]
    weakest = names[int(np.argmin(scores))]
    colors = [ACCENT_COLOR if n == weakest else PRIMARY_COLOR for n in names]
    fig.add_trace(go.Bar(x=scores, y=names, orientation="h", marker_color=colors,
                         text=[f"{s:.0f}" for s in scores], textposition="outside",
                         textfont=dict(color=MUTED, size=12),
                         hovertemplate="%{y}: <b>%{x:.0f}</b>/100<extra></extra>"))
    fig.update_xaxes(range=[0, 112])

    insight = ((f"Composite {composite:.0f}/100 → indicative {rating} ({grade}). "
                f"Debt/EBITDA {leverage:.1f}×, coverage {coverage:.1f}×, Z {z:.2f}. "
                f"Weakest pillar: {weakest}.")
               if not hi else
               (f"कुल {composite:.0f}/100 → सांकेतिक {rating} ({grade})। "
                f"क़र्ज़/EBITDA {leverage:.1f}×, कवरेज {coverage:.1f}×, Z {z:.2f}। "
                f"सबसे कमज़ोर: {weakest}।"))
    guide = ("Five lenses a bank's credit committee uses, each scored /100 and "
             "blended the way internal rating models work. The band is indicative "
             "— a real rating needs qualitative review too." if not hi else
             "बैंक की क्रेडिट समिति के पाँच नज़रिए, हर एक /100 — जैसे असली internal "
             "rating model काम करते हैं। बैंड सांकेतिक है — असली rating में "
             "गुणात्मक समीक्षा भी होती है।")
    kpis = [
        Kpi("Credit score" if not hi else "क्रेडिट स्कोर", f"{composite:.0f}/100", rating),
        Kpi("Debt/EBITDA" if not hi else "क़र्ज़/EBITDA", f"{leverage:.1f}×"),
        Kpi("Coverage" if not hi else "कवरेज", f"{coverage:.1f}×"),
        Kpi("Z-score" if not hi else "Z-स्कोर", f"{z:.2f}"),
    ]
    icon = "✅" if composite >= 55 else "⚠️"
    verdict = f"{icon} {composite:.0f}/100 — {rating} ({grade})."
    return ModelOutput(kpis=kpis, verdict=verdict,
                       results=[chart_result(title, fig, insight, guide, priority=1)])


register(ModelSpec(
    key="mix_credit", category="credit", is_mix=True,
    name=_L("⭐ Credit Mix — Risk Composite & Rating",
            "⭐ क्रेडिट मिक्स — जोखिम कम्पोज़िट व रेटिंग"),
    desc=_L("Blends leverage, coverage, profitability, liquidity and Z-score into "
            "one credit score with an indicative rating band.",
            "क़र्ज़ भार, कवरेज, लाभ, तरलता और Z-स्कोर मिलाकर एक क्रेडिट स्कोर — "
            "सांकेतिक rating बैंड के साथ।"),
    fields=_MIX_FIELDS, compute=_credit_mix_compute,
))
