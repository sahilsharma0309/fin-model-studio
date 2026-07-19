"""Economics models — GDP growth decomposition, Taylor rule, price
elasticity, and the Macro Pulse mix."""

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


# ------------------------------------------- GDP decomposition
_GDP_FIELDS = [
    Field("c0", _L("Consumption — last year", "उपभोग — पिछला साल"), default=6000.0),
    Field("c1", _L("Consumption — this year", "उपभोग — इस साल"), default=6350.0),
    Field("i0", _L("Investment — last year", "निवेश — पिछला साल"), default=3100.0),
    Field("i1", _L("Investment — this year", "निवेश — इस साल"), default=3320.0),
    Field("g0", _L("Government — last year", "सरकारी खर्च — पिछला साल"), default=1100.0),
    Field("g1", _L("Government — this year", "सरकारी खर्च — इस साल"), default=1160.0),
    Field("x0", _L("Exports — last year", "निर्यात — पिछला साल"), default=2200.0),
    Field("x1", _L("Exports — this year", "निर्यात — इस साल"), default=2290.0),
    Field("m0", _L("Imports — last year", "आयात — पिछला साल"), default=2400.0),
    Field("m1", _L("Imports — this year", "आयात — इस साल"), default=2540.0),
]


def _gdp_compute(v: dict, lang: str) -> ModelOutput:
    hi = lang == "hi"
    gdp0 = float(v["c0"]) + float(v["i0"]) + float(v["g0"]) + float(v["x0"]) - float(v["m0"])
    gdp1 = float(v["c1"]) + float(v["i1"]) + float(v["g1"]) + float(v["x1"]) - float(v["m1"])
    if gdp0 <= 0:
        return ModelOutput(kpis=[], results=[], verdict="⚠️ GDP must be positive.")
    growth = (gdp1 / gdp0 - 1) * 100
    contrib = {
        ("Consumption" if not hi else "उपभोग"): (float(v["c1"]) - float(v["c0"])) / gdp0 * 100,
        ("Investment" if not hi else "निवेश"): (float(v["i1"]) - float(v["i0"])) / gdp0 * 100,
        ("Government" if not hi else "सरकारी खर्च"): (float(v["g1"]) - float(v["g0"])) / gdp0 * 100,
        ("Net exports" if not hi else "शुद्ध निर्यात"):
            ((float(v["x1"]) - float(v["m1"])) - (float(v["x0"]) - float(v["m0"]))) / gdp0 * 100,
    }

    title = f"GDP growth {growth:.1f}% — what drove it" if not hi \
        else f"GDP वृद्धि {growth:.1f}% — किसने बढ़ाई"
    fig = base_figure(title)
    names = list(contrib)
    fig.add_trace(go.Waterfall(
        x=names + [("Growth" if not hi else "वृद्धि")],
        measure=["relative"] * 4 + ["total"],
        y=[contrib[n] for n in names] + [0],
        connector=dict(line=dict(color="#e8eaed")),
        increasing=dict(marker=dict(color=PRIMARY_COLOR)),
        decreasing=dict(marker=dict(color=ACCENT_COLOR)),
        totals=dict(marker=dict(color="#3D5C9E")),
        hovertemplate="%{x}: <b>%{y:+.2f} pp</b><extra></extra>",
    ))
    fig.update_yaxes(ticksuffix=" pp")
    biggest = max(contrib, key=lambda k: contrib[k])
    insight = ((f"Growth of {growth:.1f}% was driven mainly by {biggest} "
                f"(+{contrib[biggest]:.1f} points of it).")
               if not hi else
               (f"{growth:.1f}% की वृद्धि मुख्यतः {biggest} से आई "
                f"(+{contrib[biggest]:.1f} अंक)।"))
    guide = ("GDP = C + I + G + (X − M). Each bar shows how many points of growth "
             "that engine contributed; gold bars pulled growth down." if not hi else
             "GDP = C + I + G + (X − M)। हर बार बताती है उस इंजन ने वृद्धि में कितने "
             "अंक जोड़े; सुनहरी बार ने वृद्धि घटाई।")
    kpis = [Kpi("GDP growth" if not hi else "GDP वृद्धि", f"{growth:.1f}%"),
            Kpi("Main engine" if not hi else "मुख्य इंजन", biggest),
            Kpi("GDP (this year)" if not hi else "GDP (इस साल)", fmt(gdp1))]
    return ModelOutput(kpis=kpis, verdict=insight,
                       results=[chart_result(title, fig, insight, guide, priority=1)])


register(ModelSpec(
    key="gdp", category="econ",
    name=_L("GDP Growth Decomposition", "GDP वृद्धि विश्लेषण"),
    desc=_L("Which engine — consumption, investment, government or trade — drove growth.",
            "वृद्धि किस इंजन से आई — उपभोग, निवेश, सरकार या व्यापार।"),
    fields=_GDP_FIELDS, compute=_gdp_compute,
))


# ------------------------------------------------- Taylor rule
_TAYLOR_FIELDS = [
    Field("inflation_pct", _L("Current inflation %", "मौजूदा महँगाई %"), "percent", 5.4),
    Field("target_pct", _L("Inflation target %", "महँगाई लक्ष्य %"), "percent", 4.0),
    Field("gap_pct", _L("Output gap % (actual − potential GDP)", "आउटपुट गैप % (वास्तविक − संभावित GDP)"), "percent", -0.5),
    Field("neutral_pct", _L("Neutral real rate %", "तटस्थ वास्तविक दर %"), "percent", 1.5),
    Field("policy_pct", _L("Actual policy rate today %", "आज की वास्तविक नीति दर %"), "percent", 6.5),
]


def _taylor_compute(v: dict, lang: str) -> ModelOutput:
    hi = lang == "hi"
    pi, target = float(v["inflation_pct"]), float(v["target_pct"])
    gap, neutral = float(v["gap_pct"]), float(v["neutral_pct"])
    implied = neutral + pi + 0.5 * (pi - target) + 0.5 * gap
    actual = float(v["policy_pct"])
    diff = actual - implied

    title = "Taylor rule vs actual policy rate" if not hi else "टेलर नियम बनाम वास्तविक नीति दर"
    fig = base_figure(title)
    names = (["Taylor-implied rate", "Actual rate"] if not hi
             else ["टेलर-सुझाई दर", "वास्तविक दर"])
    fig.add_trace(go.Bar(x=names, y=[implied, actual],
                         marker_color=[PRIMARY_COLOR, ACCENT_COLOR],
                         text=[f"{implied:.2f}%", f"{actual:.2f}%"],
                         textposition="outside", textfont=dict(color=MUTED, size=12),
                         hovertemplate="%{x}: <b>%{y:.2f}%</b><extra></extra>"))
    fig.update_yaxes(ticksuffix="%")
    stance = (("tighter than" if diff > 0.25 else "looser than" if diff < -0.25 else "in line with")
              if not hi else
              ("से सख़्त" if diff > 0.25 else "से नरम" if diff < -0.25 else "के अनुरूप"))
    insight = ((f"The rule suggests {implied:.2f}% given {pi:.1f}% inflation and a "
                f"{gap:+.1f}% output gap; the actual {actual:.2f}% is {stance} the "
                f"rule by {abs(diff):.2f} points.")
               if not hi else
               (f"{pi:.1f}% महँगाई और {gap:+.1f}% गैप पर नियम {implied:.2f}% कहता "
                f"है; वास्तविक {actual:.2f}% नियम {stance} है ({abs(diff):.2f} अंक)।"))
    guide = ("A century-old central-banking rule of thumb: raise rates when "
             "inflation runs above target, cut when the economy runs cold. The "
             "gap between bars is the policy stance." if not hi else
             "केंद्रीय बैंकिंग का आज़माया नियम: महँगाई लक्ष्य से ऊपर हो तो दरें "
             "बढ़ाओ, अर्थव्यवस्था ठंडी हो तो घटाओ। बारों का अंतर ही नीति का रुख़ है।")
    kpis = [Kpi("Implied rate" if not hi else "सुझाई दर", f"{implied:.2f}%"),
            Kpi("Actual rate" if not hi else "वास्तविक दर", f"{actual:.2f}%"),
            Kpi("Stance" if not hi else "रुख़", f"{diff:+.2f} pp")]
    return ModelOutput(kpis=kpis, verdict=insight,
                       results=[chart_result(title, fig, insight, guide, priority=1)])


register(ModelSpec(
    key="taylor", category="econ",
    name=_L("Taylor Rule — policy rate check", "टेलर नियम — नीति दर जाँच"),
    desc=_L("Is the central bank's rate tight, loose, or about right?",
            "केंद्रीय बैंक की दर सख़्त है, नरम है, या ठीक?"),
    fields=_TAYLOR_FIELDS, compute=_taylor_compute,
))


# ------------------------------------------------- Elasticity
_ELAS_FIELDS = [
    Field("p0", _L("Old price", "पुरानी क़ीमत"), default=100.0),
    Field("p1", _L("New price", "नई क़ीमत"), default=110.0),
    Field("q0", _L("Old quantity sold", "पुरानी बिक्री (मात्रा)"), default=1000.0),
    Field("q1", _L("New quantity sold", "नई बिक्री (मात्रा)"), default=940.0),
]


def _elas_compute(v: dict, lang: str) -> ModelOutput:
    hi = lang == "hi"
    p0, p1 = float(v["p0"]), float(v["p1"])
    q0, q1 = float(v["q0"]), float(v["q1"])
    if p0 == p1:
        return ModelOutput(kpis=[], results=[], verdict="⚠️ Prices must differ.")
    # arc (midpoint) elasticity
    e = ((q1 - q0) / ((q0 + q1) / 2)) / ((p1 - p0) / ((p0 + p1) / 2))
    rev0, rev1 = p0 * q0, p1 * q1
    rev_change = (rev1 / rev0 - 1) * 100 if rev0 else 0

    prices = np.linspace(p0 * 0.7, p0 * 1.4, 50)
    quantities = q0 * (prices / p0) ** e
    revenues = prices * quantities
    title = "Revenue vs price (at this elasticity)" if not hi \
        else "क़ीमत बनाम राजस्व (इसी लोच पर)"
    fig = base_figure(title)
    fig.add_trace(go.Scatter(x=prices, y=revenues, mode="lines",
                             line=dict(color=PRIMARY_COLOR, width=2.5),
                             hovertemplate="Price %{x:,.0f}: <b>%{y:,.0f}</b><extra></extra>"))
    best_price = prices[int(np.argmax(revenues))]
    fig.add_vline(x=p1, line_dash="dot", line_color=MUTED,
                  annotation_text=("new price" if not hi else "नई क़ीमत"),
                  annotation_font=dict(color=MUTED, size=11))
    fig.add_trace(go.Scatter(x=[best_price], y=[revenues.max()], mode="markers",
                             marker=dict(color=ACCENT_COLOR, size=11),
                             hovertemplate=f"<b>{best_price:,.0f}</b><extra></extra>"))
    kind = (("elastic — buyers are price-sensitive" if abs(e) > 1
             else "inelastic — buyers stay put") if not hi else
            ("लोचदार — ग्राहक क़ीमत से भागते हैं" if abs(e) > 1
             else "बेलोच — ग्राहक टिके रहते हैं"))
    insight = ((f"Elasticity {e:.2f}: demand is {kind}. This price move changed "
                f"revenue {rev_change:+.1f}%. Revenue peaks near price "
                f"{best_price:,.0f} (gold dot).")
               if not hi else
               (f"लोच {e:.2f}: माँग {kind}। इस बदलाव से राजस्व {rev_change:+.1f}% "
                f"बदला। राजस्व {best_price:,.0f} के पास चरम पर (सुनहरा बिंदु)।"))
    guide = ("If demand is inelastic (|e|<1), raising price raises revenue; if "
             "elastic, cutting price can earn more. The curve shows your sweet "
             "spot." if not hi else
             "माँग बेलोच हो (|e|<1) तो दाम बढ़ाने से कमाई बढ़ती है; लोचदार हो तो दाम "
             "घटाकर ज़्यादा कमा सकते हैं। curve आपका sweet spot दिखाता है।")
    kpis = [Kpi("Elasticity" if not hi else "लोच", f"{e:.2f}"),
            Kpi("Revenue change" if not hi else "राजस्व बदलाव", f"{rev_change:+.1f}%"),
            Kpi("Revenue-max price" if not hi else "अधिकतम-राजस्व क़ीमत", f"{best_price:,.0f}")]
    return ModelOutput(kpis=kpis, verdict=insight,
                       results=[chart_result(title, fig, insight, guide, priority=1)])


register(ModelSpec(
    key="elasticity", category="econ",
    name=_L("Price Elasticity of Demand", "माँग की क़ीमत-लोच"),
    desc=_L("Should you raise or cut prices? Measure how customers react.",
            "दाम बढ़ाएँ या घटाएँ? ग्राहक कैसे react करते हैं, नापिए।"),
    fields=_ELAS_FIELDS, compute=_elas_compute,
))


# ------------------------------------------- ⭐ Macro Pulse mix
_MIX_FIELDS = [
    Field("gdp_pct", _L("GDP growth %", "GDP वृद्धि %"), "percent", 6.2),
    Field("trend_pct", _L("Trend/potential growth %", "संभावित (trend) वृद्धि %"), "percent", 6.5),
    Field("inflation_pct", _L("Inflation %", "महँगाई %"), "percent", 5.4),
    Field("target_pct", _L("Inflation target %", "महँगाई लक्ष्य %"), "percent", 4.0),
    Field("unemp_pct", _L("Unemployment %", "बेरोज़गारी %"), "percent", 7.8),
    Field("credit_pct", _L("Bank credit growth %", "बैंक ऋण वृद्धि %"), "percent", 14.0),
    Field("policy_pct", _L("Policy rate %", "नीति दर %"), "percent", 6.5),
    Field("neutral_pct", _L("Neutral real rate %", "तटस्थ वास्तविक दर %"), "percent", 1.5),
]


def _pulse_compute(v: dict, lang: str) -> ModelOutput:
    hi = lang == "hi"
    gdp, trend = float(v["gdp_pct"]), float(v["trend_pct"])
    pi, target = float(v["inflation_pct"]), float(v["target_pct"])
    unemp = float(v["unemp_pct"])
    credit = float(v["credit_pct"])
    real_rate = float(v["policy_pct"]) - pi
    neutral = float(v["neutral_pct"])

    def clamp(x):
        return min(max(x, 0), 100)

    parts = {
        ("Growth" if not hi else "वृद्धि"): (clamp((gdp - (trend - 4)) / 8 * 100), 0.30),
        ("Price stability" if not hi else "मूल्य स्थिरता"):
            (clamp(100 - abs(pi - target) / 4 * 100), 0.25),
        ("Jobs" if not hi else "रोज़गार"): (clamp((12 - unemp) / 8 * 100), 0.20),
        ("Credit pulse" if not hi else "ऋण गति"): (clamp(credit / 20 * 100), 0.15),
        ("Policy room" if not hi else "नीति गुंजाइश"):
            (clamp(50 + (real_rate - neutral) / 4 * 50), 0.10),
    }
    composite = sum(score * weight for score, weight in parts.values())
    band = (("Expansion" if composite >= 65 else "Neutral" if composite >= 45 else "Slowdown")
            if not hi else
            ("विस्तार" if composite >= 65 else "तटस्थ" if composite >= 45 else "मंदी की ओर"))

    title = f"⭐ Macro pulse — {band}" if not hi else f"⭐ मैक्रो पल्स — {band}"
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

    insight = ((f"Pulse {composite:.0f}/100 → {band}. Growth {gdp:.1f}% vs trend "
                f"{trend:.1f}%; inflation {pi:.1f}% vs {target:.1f}% target; real "
                f"policy rate {real_rate:+.1f}%. Softest reading: {weakest}.")
               if not hi else
               (f"पल्स {composite:.0f}/100 → {band}। वृद्धि {gdp:.1f}% बनाम trend "
                f"{trend:.1f}%; महँगाई {pi:.1f}% बनाम लक्ष्य {target:.1f}%; वास्तविक "
                f"नीति दर {real_rate:+.1f}%। सबसे नरम: {weakest}।"))
    guide = ("Five dials of an economy on one gauge — growth, prices, jobs, "
             "credit, and how much room the central bank has. Gold bar = the "
             "dial flashing first." if not hi else
             "अर्थव्यवस्था के पाँच डायल एक गेज पर — वृद्धि, क़ीमतें, रोज़गार, ऋण, और "
             "केंद्रीय बैंक की गुंजाइश। सुनहरी बार = जो डायल पहले चेतावनी दे रहा है।")
    kpis = [Kpi("Macro pulse" if not hi else "मैक्रो पल्स", f"{composite:.0f}/100", band),
            Kpi("Growth vs trend" if not hi else "वृद्धि बनाम trend",
                f"{gdp - trend:+.1f} pp"),
            Kpi("Inflation gap" if not hi else "महँगाई अंतर", f"{pi - target:+.1f} pp"),
            Kpi("Real rate" if not hi else "वास्तविक दर", f"{real_rate:+.1f}%")]
    verdict = f"{'✅' if composite >= 45 else '⚠️'} {composite:.0f}/100 — {band}."
    return ModelOutput(kpis=kpis, verdict=verdict,
                       results=[chart_result(title, fig, insight, guide, priority=1)])


register(ModelSpec(
    key="mix_econ", category="econ", is_mix=True,
    name=_L("⭐ Econ Mix — Macro Pulse", "⭐ इकॉन मिक्स — मैक्रो पल्स"),
    desc=_L("Growth, inflation, jobs, credit and policy room blended into one "
            "expansion/slowdown gauge.",
            "वृद्धि, महँगाई, रोज़गार, ऋण और नीति गुंजाइश मिलाकर एक "
            "विस्तार/मंदी गेज।"),
    fields=_MIX_FIELDS, compute=_pulse_compute,
))
