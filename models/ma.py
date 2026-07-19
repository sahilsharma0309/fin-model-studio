"""M&A models — accretion/dilution, synergy NPV, contribution analysis,
and the Deal Scorecard mix. Pure formulas, bilingual output."""

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


# ------------------------------------------- Accretion / dilution
_AD_FIELDS = [
    Field("acq_ni", _L("Acquirer: net income", "ख़रीदार: शुद्ध लाभ"), default=500.0),
    Field("acq_shares", _L("Acquirer: shares outstanding", "ख़रीदार: कुल शेयर"), default=200.0),
    Field("acq_price", _L("Acquirer: share price", "ख़रीदार: शेयर भाव"), default=60.0),
    Field("tgt_ni", _L("Target: net income", "टार्गेट: शुद्ध लाभ"), default=120.0),
    Field("deal_value", _L("Deal value (equity purchase price)", "डील मूल्य (इक्विटी ख़रीद)"), default=1800.0),
    Field("pct_stock", _L("% paid in stock", "% स्टॉक से"), "percent", 40.0),
    Field("pct_debt", _L("% paid with new debt", "% नए क़र्ज़ से"), "percent", 40.0),
    Field("debt_rate_pct", _L("Interest on new debt %", "नए क़र्ज़ पर ब्याज %"), "percent", 8.0),
    Field("cash_rate_pct", _L("Yield lost on cash used %", "इस्तेमाल हुए नक़द पर छूटा ब्याज %"), "percent", 4.0),
    Field("synergies", _L("Annual pre-tax synergies", "सालाना कर-पूर्व synergy"), default=60.0),
    Field("tax_pct", _L("Tax rate %", "कर दर %"), "percent", 25.0),
]


def _ad_core(v: dict) -> dict:
    deal = float(v["deal_value"])
    stock_part = deal * _pct(v["pct_stock"])
    debt_part = deal * _pct(v["pct_debt"])
    cash_part = max(deal - stock_part - debt_part, 0)
    tax = _pct(v["tax_pct"])
    new_shares = stock_part / max(float(v["acq_price"]), 1e-9)
    after_tax_adj = (float(v["synergies"])
                     - debt_part * _pct(v["debt_rate_pct"])
                     - cash_part * _pct(v["cash_rate_pct"])) * (1 - tax)
    pf_ni = float(v["acq_ni"]) + float(v["tgt_ni"]) + after_tax_adj
    pf_shares = float(v["acq_shares"]) + new_shares
    eps0 = float(v["acq_ni"]) / max(float(v["acq_shares"]), 1e-9)
    eps1 = pf_ni / max(pf_shares, 1e-9)
    return dict(eps0=eps0, eps1=eps1, accretion=(eps1 / eps0 - 1) * 100 if eps0 else 0,
                new_shares=new_shares, cash_part=cash_part, debt_part=debt_part,
                stock_part=stock_part)


def _ad_compute(v: dict, lang: str) -> ModelOutput:
    hi = lang == "hi"
    if _pct(v["pct_stock"]) + _pct(v["pct_debt"]) > 1.0001:
        msg = ("Stock % + debt % cannot exceed 100." if not hi
               else "स्टॉक % + क़र्ज़ % मिलाकर 100 से ज़्यादा नहीं हो सकते।")
        return ModelOutput(kpis=[], results=[], verdict=f"⚠️ {msg}")
    d = _ad_core(v)

    title = "EPS: standalone vs pro-forma" if not hi else "EPS: अकेले बनाम डील के बाद"
    fig = base_figure(title)
    labels = (["Standalone", "Pro-forma"] if not hi else ["अकेले", "डील के बाद"])
    colors = [PRIMARY_COLOR, ACCENT_COLOR if d["eps1"] >= d["eps0"] else "#A8862F"]
    fig.add_trace(go.Bar(
        x=labels, y=[d["eps0"], d["eps1"]], marker_color=colors,
        text=[f"{d['eps0']:.2f}", f"{d['eps1']:.2f}"], textposition="outside",
        textfont=dict(color=MUTED, size=12),
        hovertemplate="%{x}: <b>%{y:.2f}</b><extra></extra>",
    ))
    word = (("accretive" if d["accretion"] > 0 else "dilutive") if not hi
            else ("बढ़ाने वाली (accretive)" if d["accretion"] > 0 else "घटाने वाली (dilutive)"))
    insight = ((f"The deal is {word}: EPS moves {d['accretion']:+.1f}% "
                f"({d['eps0']:.2f} → {d['eps1']:.2f}) after {fmt(d['new_shares'])} "
                f"new shares and financing costs.")
               if not hi else
               (f"डील EPS {word} है: {d['accretion']:+.1f}% "
                f"({d['eps0']:.2f} → {d['eps1']:.2f}), {fmt(d['new_shares'])} नए शेयर "
                f"और financing लागत के बाद।"))
    guide = ("If the second bar is taller, each existing share earns more after the "
             "deal — shareholders usually cheer. Shorter = they're paying for it."
             if not hi else
             "दूसरी बार ऊँची हो तो डील के बाद हर पुराना शेयर ज़्यादा कमाता है — "
             "शेयरधारक ख़ुश। छोटी हो तो क़ीमत वही चुका रहे हैं।")
    kpis = [
        Kpi("EPS accretion" if not hi else "EPS बदलाव", f"{d['accretion']:+.1f}%"),
        Kpi("Pro-forma EPS" if not hi else "डील के बाद EPS", f"{d['eps1']:.2f}"),
        Kpi("New shares" if not hi else "नए शेयर", fmt(d["new_shares"])),
        Kpi("Financing (C/D/S)" if not hi else "वित्त (नक़द/क़र्ज़/स्टॉक)",
            f"{fmt(d['cash_part'])}/{fmt(d['debt_part'])}/{fmt(d['stock_part'])}"),
    ]
    verdict = ((f"{'✅' if d['accretion'] > 0 else '⚠️'} Deal is {word} "
                f"({d['accretion']:+.1f}% EPS).")
               if not hi else
               (f"{'✅' if d['accretion'] > 0 else '⚠️'} डील EPS को {d['accretion']:+.1f}% "
                f"{'बढ़ाती' if d['accretion'] > 0 else 'घटाती'} है।"))
    return ModelOutput(kpis=kpis, verdict=verdict,
                       results=[chart_result(title, fig, insight, guide, priority=1)])


register(ModelSpec(
    key="accretion", category="ma",
    name=_L("Merger Model — EPS Accretion/Dilution", "मर्जर मॉडल — EPS बढ़त/घटत"),
    desc=_L("Does the acquisition raise or lower the buyer's earnings per share?",
            "क्या यह अधिग्रहण ख़रीदार का प्रति-शेयर लाभ बढ़ाता है या घटाता है?"),
    fields=_AD_FIELDS, compute=_ad_compute,
))


# ------------------------------------------------- Synergy NPV
_SYN_FIELDS = [
    Field("cost_syn", _L("Annual cost synergies (pre-tax)", "सालाना लागत synergy (कर-पूर्व)"), default=50.0),
    Field("rev_syn", _L("Annual revenue synergies (pre-tax)", "सालाना राजस्व synergy (कर-पूर्व)"), default=30.0),
    Field("rev_margin_pct", _L("Margin on revenue synergies %", "राजस्व synergy पर मार्जिन %"), "percent", 30.0),
    Field("onetime", _L("One-time integration cost", "एक-बार की integration लागत"), default=40.0),
    Field("tax_pct", _L("Tax rate %", "कर दर %"), "percent", 25.0),
    Field("rate_pct", _L("Discount rate %", "छूट दर %"), "percent", 10.0),
    Field("years", _L("Horizon (years)", "अवधि (साल)"), "int", 5),
    Field("premium", _L("Premium paid over market value", "बाज़ार भाव से ऊपर चुकाया premium"), default=250.0),
]

PHASE_IN = [0.5, 0.75, 1.0]  # year 1, 2, 3+


def _syn_compute(v: dict, lang: str) -> ModelOutput:
    hi = lang == "hi"
    tax = _pct(v["tax_pct"])
    rate = _pct(v["rate_pct"])
    years = max(2, min(10, int(v["years"])))
    run_rate = (float(v["cost_syn"])
                + float(v["rev_syn"]) * _pct(v["rev_margin_pct"])) * (1 - tax)
    pv_total, cumulative, path = -float(v["onetime"]), [], []
    for y in range(1, years + 1):
        realized = run_rate * PHASE_IN[min(y - 1, len(PHASE_IN) - 1)]
        pv_total += realized / (1 + rate) ** y
        cumulative.append(pv_total)
        path.append(f"Y{y}")
    premium = float(v["premium"])

    title = ("Synergy value vs premium paid" if not hi
             else "Synergy की क़ीमत बनाम चुकाया premium")
    fig = base_figure(title)
    fig.add_trace(go.Scatter(
        x=path, y=cumulative, mode="lines+markers",
        line=dict(color=PRIMARY_COLOR, width=2.5), marker=dict(size=8),
        fill="tozeroy", fillcolor="rgba(26,43,76,0.07)",
        hovertemplate="%{x}: <b>%{y:,.0f}</b><extra></extra>",
    ))
    fig.add_hline(y=premium, line_color=ACCENT_COLOR, line_width=2,
                  annotation_text=("Premium " + fmt(premium)) if not hi
                  else ("Premium " + fmt(premium)),
                  annotation_font=dict(color=ACCENT_COLOR, size=12))
    coverage = pv_total / premium if premium else float("inf")
    insight = ((f"Synergies are worth {fmt(pv_total)} (NPV, net of integration "
                f"costs) vs a premium of {fmt(premium)} — {coverage:.1f}× coverage.")
               if not hi else
               (f"Synergy की NPV {fmt(pv_total)} है (integration लागत घटाकर) बनाम "
                f"premium {fmt(premium)} — {coverage:.1f}× कवरेज।"))
    guide = ("The line is the value the deal-savings build up over time; the gold "
             "line is the extra price paid. Deal logic works when the line climbs "
             "past the gold." if not hi else
             "रेखा = डील की बचत से बनती क़ीमत; सुनहरी रेखा = चुकाया गया अतिरिक्त दाम। "
             "रेखा सुनहरी से ऊपर निकले तो डील का तर्क सही।")
    kpis = [
        Kpi("Synergy NPV", fmt(pv_total)),
        Kpi("Premium", fmt(premium)),
        Kpi("Coverage" if not hi else "कवरेज", f"{coverage:.1f}×"),
        Kpi("Run-rate (after tax)" if not hi else "सालाना (कर-बाद)", fmt(run_rate)),
    ]
    verdict = ((f"{'✅ Synergies justify the premium.' if coverage >= 1 else '⚠️ Synergies do NOT cover the premium — the deal overpays unless strategic value fills the gap.'}")
               if not hi else
               (f"{'✅ Synergy premium को सही ठहराती हैं।' if coverage >= 1 else '⚠️ Synergy premium को कवर नहीं करतीं — रणनीतिक वजह न हो तो दाम ज़्यादा है।'}"))
    return ModelOutput(kpis=kpis, verdict=verdict,
                       results=[chart_result(title, fig, insight, guide, priority=1)])


register(ModelSpec(
    key="synergy", category="ma",
    name=_L("Synergy Analysis — NPV vs premium", "Synergy विश्लेषण — NPV बनाम premium"),
    desc=_L("Are the promised savings worth more than the extra price paid?",
            "जो बचत बताई जा रही है, क्या वह चुकाए गए अतिरिक्त दाम से ज़्यादा है?"),
    fields=_SYN_FIELDS, compute=_syn_compute,
))


# --------------------------------------------- Contribution analysis
_CONTRIB_FIELDS = [
    Field("acq_rev", _L("Acquirer: revenue", "ख़रीदार: राजस्व"), default=2000.0),
    Field("tgt_rev", _L("Target: revenue", "टार्गेट: राजस्व"), default=800.0),
    Field("acq_ebitda", _L("Acquirer: EBITDA", "ख़रीदार: EBITDA"), default=400.0),
    Field("tgt_ebitda", _L("Target: EBITDA", "टार्गेट: EBITDA"), default=200.0),
    Field("acq_ni", _L("Acquirer: net income", "ख़रीदार: शुद्ध लाभ"), default=220.0),
    Field("tgt_ni", _L("Target: net income", "टार्गेट: शुद्ध लाभ"), default=110.0),
    Field("tgt_own_pct", _L("Target shareholders' ownership after deal %",
                            "डील के बाद टार्गेट शेयरधारकों का हिस्सा %"), "percent", 28.0),
]


def _contrib_compute(v: dict, lang: str) -> ModelOutput:
    hi = lang == "hi"
    metrics = {
        ("Revenue" if not hi else "राजस्व"): (float(v["acq_rev"]), float(v["tgt_rev"])),
        "EBITDA": (float(v["acq_ebitda"]), float(v["tgt_ebitda"])),
        ("Net income" if not hi else "शुद्ध लाभ"): (float(v["acq_ni"]), float(v["tgt_ni"])),
    }
    own = float(v["tgt_own_pct"])
    shares = {name: tgt / (acq + tgt) * 100 if acq + tgt else 0
              for name, (acq, tgt) in metrics.items()}

    title = ("Target's contribution vs ownership received" if not hi
             else "टार्गेट का योगदान बनाम मिला हिस्सा")
    fig = base_figure(title)
    names = list(shares)
    fig.add_trace(go.Bar(
        x=names, y=[shares[n] for n in names], marker_color=PRIMARY_COLOR,
        text=[f"{shares[n]:.0f}%" for n in names], textposition="outside",
        textfont=dict(color=MUTED, size=12),
        hovertemplate="%{x}: <b>%{y:.0f}%</b><extra></extra>",
    ))
    fig.add_hline(y=own, line_color=ACCENT_COLOR, line_width=2.5,
                  annotation_text=(f"Ownership {own:.0f}%" if not hi
                                   else f"हिस्सा {own:.0f}%"),
                  annotation_font=dict(color=ACCENT_COLOR, size=12))
    fig.update_yaxes(ticksuffix="%")

    avg_contrib = float(np.mean(list(shares.values())))
    gap = own - avg_contrib
    who = (("target shareholders" if gap > 0 else "acquirer shareholders") if not hi
           else ("टार्गेट शेयरधारकों" if gap > 0 else "ख़रीदार शेयरधारकों"))
    insight = ((f"Target contributes ~{avg_contrib:.0f}% of the combined business "
                f"but receives {own:.0f}% ownership — the split favors {who} "
                f"by {abs(gap):.0f} points.")
               if not hi else
               (f"टार्गेट मिले-जुले कारोबार में ~{avg_contrib:.0f}% देता है पर हिस्सा "
                f"{own:.0f}% मिला — बँटवारा {who} के पक्ष में {abs(gap):.0f} अंक झुका है।"))
    guide = ("Bars = how much of the combined company the target brings on each "
             "measure. The gold line = the ownership its shareholders actually get. "
             "Bars above the line mean they gave more than they got." if not hi else
             "बार = टार्गेट हर पैमाने पर मिली-जुली कंपनी में कितना लाता है। सुनहरी "
             "रेखा = उसके शेयरधारकों को मिला असली हिस्सा। बार रेखा से ऊपर = जितना "
             "दिया उससे कम पाया।")
    kpis = [
        Kpi("Avg contribution" if not hi else "औसत योगदान", f"{avg_contrib:.0f}%"),
        Kpi("Ownership received" if not hi else "मिला हिस्सा", f"{own:.0f}%"),
        Kpi("Gap" if not hi else "अंतर", f"{gap:+.0f} pts"),
    ]
    fair = abs(gap) <= 5
    verdict = (("✅ Split looks fair (within 5 points)." if fair else
                f"⚠️ Split is tilted — {abs(gap):.0f} points off contribution.")
               if not hi else
               ("✅ बँटवारा उचित दिखता है (5 अंक के भीतर)।" if fair else
                f"⚠️ बँटवारा झुका हुआ है — योगदान से {abs(gap):.0f} अंक दूर।"))
    return ModelOutput(kpis=kpis, verdict=verdict,
                       results=[chart_result(title, fig, insight, guide, priority=1)])


register(ModelSpec(
    key="contribution", category="ma",
    name=_L("Contribution Analysis", "योगदान विश्लेषण"),
    desc=_L("Is ownership split fairly versus what each side brings to the table?",
            "जो जितना लाया, क्या उसे उतना ही हिस्सा मिला?"),
    fields=_CONTRIB_FIELDS, compute=_contrib_compute,
))


# ------------------------------------------- ⭐ Deal Scorecard mix
_MIX_FIELDS = (
    _AD_FIELDS
    + [f for f in _SYN_FIELDS if f.key not in ("tax_pct",)]
    + [Field("acq_rev", _L("Acquirer: revenue", "ख़रीदार: राजस्व"), default=2000.0),
       Field("tgt_rev", _L("Target: revenue", "टार्गेट: राजस्व"), default=800.0),
       Field("acq_ebitda", _L("Acquirer: EBITDA", "ख़रीदार: EBITDA"), default=400.0),
       Field("tgt_ebitda", _L("Target: EBITDA", "टार्गेट: EBITDA"), default=200.0)]
)


def _deal_mix_compute(v: dict, lang: str) -> ModelOutput:
    hi = lang == "hi"
    if _pct(v["pct_stock"]) + _pct(v["pct_debt"]) > 1.0001:
        msg = ("Stock % + debt % cannot exceed 100." if not hi
               else "स्टॉक % + क़र्ज़ % मिलाकर 100 से ज़्यादा नहीं हो सकते।")
        return ModelOutput(kpis=[], results=[], verdict=f"⚠️ {msg}")

    ad = _ad_core(v)
    accretion_score = min(max((ad["accretion"] + 5) / 10 * 100, 0), 100)

    tax = _pct(v["tax_pct"])
    rate = _pct(v["rate_pct"])
    years = max(2, min(10, int(v["years"])))
    run_rate = (float(v["cost_syn"])
                + float(v["rev_syn"]) * _pct(v["rev_margin_pct"])) * (1 - tax)
    pv = -float(v["onetime"])
    for y in range(1, years + 1):
        pv += run_rate * PHASE_IN[min(y - 1, len(PHASE_IN) - 1)] / (1 + rate) ** y
    premium = max(float(v["premium"]), 1e-9)
    coverage = pv / premium
    synergy_score = min(max((coverage - 0.5) / 0.7 * 100, 0), 100)

    ebitda_contrib = (float(v["tgt_ebitda"])
                      / max(float(v["acq_ebitda"]) + float(v["tgt_ebitda"]), 1e-9) * 100)
    own = ad["stock_part"] / max(float(v["deal_value"]), 1e-9)  # rough proxy share
    stock_own_pct = (ad["new_shares"]
                     / max(float(v["acq_shares"]) + ad["new_shares"], 1e-9) * 100)
    fairness_gap = abs(ebitda_contrib - stock_own_pct)
    fairness_score = min(max(100 - fairness_gap * 3, 0), 100)

    parts = {
        ("EPS impact" if not hi else "EPS असर"): (accretion_score, 0.40),
        ("Synergy vs premium" if not hi else "Synergy बनाम premium"): (synergy_score, 0.35),
        ("Fair split" if not hi else "उचित बँटवारा"): (fairness_score, 0.25),
    }
    composite = sum(score * weight for score, weight in parts.values())

    title = "⭐ Deal scorecard" if not hi else "⭐ डील स्कोरकार्ड"
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

    insight = ((f"Deal score {composite:.0f}/100 — EPS {ad['accretion']:+.1f}%, "
                f"synergy coverage {coverage:.1f}×, contribution-ownership gap "
                f"{fairness_gap:.0f} pts. Weakest: {weakest}.")
               if not hi else
               (f"डील स्कोर {composite:.0f}/100 — EPS {ad['accretion']:+.1f}%, "
                f"synergy कवरेज {coverage:.1f}×, योगदान-हिस्सा अंतर {fairness_gap:.0f} "
                f"अंक। सबसे कमज़ोर: {weakest}।"))
    guide = ("Three tests every banker runs on a deal, each scored /100: does it "
             "raise EPS, do savings beat the premium, is the share split fair. "
             "The gold bar is where the deal is weakest." if not hi else
             "हर डील पर banker के तीन इम्तिहान, हर एक /100: EPS बढ़ता है? बचत premium "
             "से बड़ी है? बँटवारा उचित है? सुनहरी बार वहाँ है जहाँ डील कमज़ोर है।")
    band = (("Go" if composite >= 70 else "Caution" if composite >= 45 else "No-go")
            if not hi else
            ("आगे बढ़ें" if composite >= 70 else "सावधानी" if composite >= 45 else "रुकें"))
    kpis = [
        Kpi("Deal score" if not hi else "डील स्कोर", f"{composite:.0f}/100", band),
        Kpi("EPS impact" if not hi else "EPS असर", f"{ad['accretion']:+.1f}%"),
        Kpi("Synergy coverage" if not hi else "Synergy कवरेज", f"{coverage:.1f}×"),
        Kpi("Split gap" if not hi else "बँटवारा अंतर", f"{fairness_gap:.0f} pts"),
    ]
    verdict = (f"{'✅' if composite >= 70 else '⚠️' if composite >= 45 else '❌'} "
               f"{band} — {composite:.0f}/100.")
    return ModelOutput(kpis=kpis, verdict=verdict,
                       results=[chart_result(title, fig, insight, guide, priority=1)])


register(ModelSpec(
    key="mix_ma", category="ma", is_mix=True,
    name=_L("⭐ M&A Mix — Deal Scorecard", "⭐ M&A मिक्स — डील स्कोरकार्ड"),
    desc=_L("Runs accretion, synergy-vs-premium and fairness together into one "
            "Go / Caution / No-go verdict.",
            "EPS असर, synergy बनाम premium और बँटवारे की जाँच एक साथ — एक ही "
            "आगे बढ़ें / सावधानी / रुकें फ़ैसला।"),
    fields=_MIX_FIELDS, compute=_deal_mix_compute,
))
