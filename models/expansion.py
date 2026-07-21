"""Expansion pack — high-value additional models across every category.
All pure math, bilingual, feeding the same report engine."""

import math

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from core.branding import ACCENT_COLOR, PRIMARY_COLOR, SERIES_PALETTE
from core.charts import MUTED, base_figure, chart_result, fmt
from core.result import AnalysisResult, Kpi
from models.base import Field, ModelOutput, ModelSpec, clean_table, register


def _L(en: str, hi: str) -> dict:
    return {"en": en, "hi": hi}


def _pct(x) -> float:
    return float(x or 0) / 100.0


def _norm_cdf(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


# =====================================================================
# 💰 VALUATION — Sum-of-the-Parts
# =====================================================================
_SOTP_COLS = [
    ("segment", _L("Segment / business", "सेगमेंट / कारोबार")),
    ("metric", _L("EBITDA (or revenue)", "EBITDA (या राजस्व)")),
    ("multiple", _L("Multiple (×)", "मल्टीपल (×)")),
]
_SOTP_FIELDS = [
    Field("segments", _L("Business segments (2-8 rows)", "कारोबार सेगमेंट (2-8 पंक्तियाँ)"),
          "table", columns=_SOTP_COLS, rows=4),
    Field("net_debt", _L("Net debt (group)", "शुद्ध क़र्ज़ (समूह)"), default=300.0),
    Field("shares", _L("Shares outstanding", "कुल शेयर"), default=100.0, min_value=0.0001),
]


def _sotp_compute(v: dict, lang: str) -> ModelOutput:
    hi = lang == "hi"
    seg = clean_table(v["segments"], ["metric", "multiple"]).dropna(subset=["metric", "multiple"])
    if len(seg) < 2:
        msg = ("Add at least 2 segments with EBITDA and a multiple." if not hi
               else "कम से कम 2 सेगमेंट भरें (EBITDA और मल्टीपल के साथ)।")
        return ModelOutput(kpis=[], results=[], verdict=f"⚠️ {msg}")
    seg = seg.copy()
    seg["ev"] = seg["metric"] * seg["multiple"]
    total_ev = seg["ev"].sum()
    equity = total_ev - float(v["net_debt"])
    per_share = equity / max(float(v["shares"]), 1e-9)

    title = "Enterprise value by segment" if not hi else "सेगमेंट के हिसाब से एंटरप्राइज़ वैल्यू"
    fig = base_figure(title)
    names = seg["segment"].fillna("—").astype(str).tolist()
    top = seg["ev"].idxmax()
    colors = [ACCENT_COLOR if i == top else PRIMARY_COLOR for i in seg.index]
    fig.add_trace(go.Bar(
        x=names, y=seg["ev"], marker_color=colors,
        text=[fmt(x) for x in seg["ev"]], textposition="outside",
        textfont=dict(color=MUTED, size=12),
        hovertemplate="%{x}: <b>%{y:,.0f}</b><extra></extra>",
    ))
    biggest = names[list(seg.index).index(top)]
    share = seg.loc[top, "ev"] / total_ev * 100 if total_ev else 0
    insight = ((f"The parts add up to {fmt(total_ev)} enterprise value → "
                f"{fmt(equity)} equity ({fmt(per_share)}/share). {biggest} is the "
                f"crown jewel at {share:.0f}% of value.")
               if not hi else
               (f"हिस्से जुड़कर {fmt(total_ev)} एंटरप्राइज़ वैल्यू बनाते हैं → "
                f"{fmt(equity)} इक्विटी ({fmt(per_share)}/शेयर)। {biggest} सबसे "
                f"क़ीमती है — कुल का {share:.0f}%।"))
    guide = ("Each segment is valued at its own fair multiple, then summed. Useful "
             "when a conglomerate's parts are worth more apart than together — the "
             "gold bar is the biggest driver." if not hi else
             "हर सेगमेंट को उसके अपने उचित मल्टीपल पर आँका जाता है, फिर जोड़ते हैं। "
             "जब समूह के हिस्से अलग-अलग ज़्यादा क़ीमती हों तब काम आता है — सुनहरी "
             "बार सबसे बड़ा हिस्सा।")
    kpis = [Kpi("Total EV" if not hi else "कुल EV", fmt(total_ev)),
            Kpi("Equity value" if not hi else "इक्विटी वैल्यू", fmt(equity)),
            Kpi("Value / share" if not hi else "प्रति शेयर मूल्य", fmt(per_share)),
            Kpi("Segments" if not hi else "सेगमेंट", str(len(seg)))]
    verdict = (f"SOTP value: {fmt(per_share)} per share." if not hi
               else f"SOTP मूल्य: {fmt(per_share)} प्रति शेयर।")
    return ModelOutput(kpis=kpis, verdict=verdict,
                       results=[chart_result(title, fig, insight, guide, priority=1)])


register(ModelSpec(
    key="sotp", category="valuation",
    name=_L("Sum-of-the-Parts (SOTP)", "सम-ऑफ़-द-पार्ट्स (SOTP)"),
    desc=_L("Value each business segment separately, then add them up.",
            "हर कारोबार सेगमेंट को अलग से आँको, फिर जोड़ो।"),
    fields=_SOTP_FIELDS, compute=_sotp_compute,
))


# =====================================================================
# 💰 VALUATION — Residual Income / EVA
# =====================================================================
_EVA_FIELDS = [
    Field("ebit", _L("EBIT (operating profit)", "EBIT (परिचालन लाभ)"), default=250.0),
    Field("tax_pct", _L("Tax rate %", "कर दर %"), "percent", 25.0),
    Field("invested_capital", _L("Invested capital", "लगाई गई पूंजी"), default=1200.0),
    Field("wacc_pct", _L("WACC %", "WACC %"), "percent", 11.0),
    Field("g_pct", _L("Long-term EVA growth %", "दीर्घकालिक EVA वृद्धि %"), "percent", 3.0),
]


def _eva_compute(v: dict, lang: str) -> ModelOutput:
    hi = lang == "hi"
    nopat = float(v["ebit"]) * (1 - _pct(v["tax_pct"]))
    ic = float(v["invested_capital"])
    wacc = _pct(v["wacc_pct"])
    g = _pct(v["g_pct"])
    roic = nopat / ic if ic else 0
    charge = wacc * ic
    eva = nopat - charge
    if wacc <= g:
        value = ic + eva * 10  # fallback if perpetuity breaks
    else:
        value = ic + eva / (wacc - g)

    title = "NOPAT vs capital charge" if not hi else "NOPAT बनाम पूंजी शुल्क"
    fig = base_figure(title)
    labels = (["NOPAT (profit)", "Capital charge", "EVA (economic profit)"]
              if not hi else ["NOPAT (लाभ)", "पूंजी शुल्क", "EVA (आर्थिक लाभ)"])
    colors = [PRIMARY_COLOR, "#A8862F", ACCENT_COLOR if eva >= 0 else "#A8862F"]
    fig.add_trace(go.Bar(
        x=labels, y=[nopat, charge, eva], marker_color=colors,
        text=[fmt(nopat), fmt(charge), fmt(eva)], textposition="outside",
        textfont=dict(color=MUTED, size=12),
        hovertemplate="%{x}: <b>%{y:,.0f}</b><extra></extra>",
    ))
    creates = eva >= 0
    insight = ((f"ROIC {roic * 100:.1f}% vs WACC {wacc * 100:.1f}% → the business "
                f"{'creates' if creates else 'destroys'} {fmt(abs(eva))} of value "
                f"per year. Intrinsic value ≈ {fmt(value)}.")
               if not hi else
               (f"ROIC {roic * 100:.1f}% बनाम WACC {wacc * 100:.1f}% → कारोबार हर "
                f"साल {fmt(abs(eva))} मूल्य {'बनाता' if creates else 'नष्ट करता'} है। "
                f"आंतरिक मूल्य ≈ {fmt(value)}।"))
    guide = ("Economic profit is the profit left AFTER charging for the capital "
             "used. If the profit bar beats the capital-charge bar, the business "
             "genuinely creates value — otherwise it's just renting money."
             if not hi else
             "आर्थिक लाभ वह है जो पूंजी का शुल्क चुकाने के बाद बचे। अगर लाभ बार "
             "पूंजी-शुल्क बार से ऊँची हो, तो कारोबार सच में मूल्य बनाता है — वरना "
             "बस पैसे किराए पर ले रहा है।")
    kpis = [Kpi("EVA / year" if not hi else "EVA / साल", fmt(eva)),
            Kpi("ROIC", f"{roic * 100:.1f}%"),
            Kpi("ROIC − WACC spread" if not hi else "ROIC − WACC", f"{(roic - wacc) * 100:+.1f}%"),
            Kpi("Intrinsic value" if not hi else "आंतरिक मूल्य", fmt(value))]
    icon = "✅" if creates else "⚠️"
    verdict = (f"{icon} EVA {fmt(eva)}/yr — " +
               (("value-creating (ROIC beats WACC)." if creates
                 else "value-destroying (ROIC below WACC).") if not hi else
                ("मूल्य बना रहा (ROIC > WACC)।" if creates
                 else "मूल्य नष्ट कर रहा (ROIC < WACC)।")))
    return ModelOutput(kpis=kpis, verdict=verdict,
                       results=[chart_result(title, fig, insight, guide, priority=1)])


register(ModelSpec(
    key="eva", category="valuation",
    name=_L("Residual Income / EVA", "अवशिष्ट आय / EVA"),
    desc=_L("Does the business earn more than the cost of the capital it uses?",
            "क्या कारोबार अपनी लगाई पूंजी की लागत से ज़्यादा कमाता है?"),
    fields=_EVA_FIELDS, compute=_eva_compute,
))


# =====================================================================
# 📊 CORPFIN — Monte Carlo simulation
# =====================================================================
_MC_FIELDS = [
    Field("revenue", _L("Base annual revenue", "आधार सालाना राजस्व"), default=1000.0),
    Field("growth_mean_pct", _L("Expected growth % / year", "अपेक्षित वृद्धि % / साल"), "percent", 8.0),
    Field("growth_vol_pct", _L("Growth uncertainty (± %)", "वृद्धि अनिश्चितता (± %)"), "percent", 12.0),
    Field("margin_pct", _L("Net margin %", "शुद्ध मार्जिन %"), "percent", 12.0),
    Field("fixed_costs", _L("Fixed costs / year", "स्थिर लागत / साल"), default=60.0),
    Field("years", _L("Years ahead", "आगे के साल"), "int", 3),
]


def _mc_compute(v: dict, lang: str) -> ModelOutput:
    hi = lang == "hi"
    rng = np.random.default_rng(7)
    sims = 12000
    years = max(1, min(8, int(v["years"])))
    mean, vol = _pct(v["growth_mean_pct"]), _pct(v["growth_vol_pct"])
    growth = rng.normal(mean, max(vol, 1e-4), size=(sims, years))
    revenue = float(v["revenue"]) * np.prod(1 + growth, axis=1)
    profit = revenue * _pct(v["margin_pct"]) - float(v["fixed_costs"])
    p10, p50, p90 = np.percentile(profit, [10, 50, 90])
    prob_loss = float((profit < 0).mean()) * 100

    title = f"Profit distribution — year {years}" if not hi else f"लाभ वितरण — साल {years}"
    fig = base_figure(title)
    fig.add_trace(go.Histogram(
        x=profit, nbinsx=60,
        marker=dict(color=PRIMARY_COLOR, line=dict(color="white", width=0.5)),
        hovertemplate="%{x}: %{y}<extra></extra>",
    ))
    fig.add_vline(x=0, line_color="#A8862F", line_width=2,
                  annotation_text=("break-even" if not hi else "बराबरी"),
                  annotation_font=dict(color="#A8862F", size=11))
    fig.add_vline(x=p50, line_color=ACCENT_COLOR, line_width=2.5,
                  annotation_text=(f"median {fmt(p50)}" if not hi else f"मध्य {fmt(p50)}"),
                  annotation_font=dict(color=ACCENT_COLOR, size=12))
    insight = ((f"Across {sims:,} simulations: most likely profit {fmt(p50)}, with "
                f"a range of {fmt(p10)} (bad) to {fmt(p90)} (good). Chance of a "
                f"loss: {prob_loss:.0f}%.")
               if not hi else
               (f"{sims:,} सिमुलेशन में: सबसे संभावित लाभ {fmt(p50)}, दायरा {fmt(p10)} "
                f"(बुरा) से {fmt(p90)} (अच्छा)। घाटे की संभावना: {prob_loss:.0f}%।"))
    guide = ("Instead of one guess, this runs thousands of possible futures. The "
             "hill shows how likely each profit level is; anything left of the "
             "gold break-even line is a loss." if not hi else
             "एक अंदाज़े की जगह यह हज़ारों संभावित भविष्य चलाता है। टीला दिखाता है "
             "हर लाभ स्तर कितना संभव है; सुनहरी बराबरी-रेखा से बाईं ओर सब घाटा है।")
    kpis = [Kpi("Median profit" if not hi else "मध्य लाभ", fmt(p50)),
            Kpi("Downside (P10)" if not hi else "निचला (P10)", fmt(p10)),
            Kpi("Upside (P90)" if not hi else "ऊपरी (P90)", fmt(p90)),
            Kpi("Chance of loss" if not hi else "घाटे की संभावना", f"{prob_loss:.0f}%")]
    icon = "✅" if prob_loss < 15 else "🟡" if prob_loss < 35 else "⚠️"
    verdict = (f"{icon} " + (f"{prob_loss:.0f}% chance of a loss; likely profit {fmt(p50)}."
               if not hi else f"{prob_loss:.0f}% घाटे की संभावना; संभावित लाभ {fmt(p50)}।"))
    return ModelOutput(kpis=kpis, verdict=verdict,
                       results=[chart_result(title, fig, insight, guide, priority=1)])


register(ModelSpec(
    key="monte_carlo", category="corpfin",
    name=_L("Monte Carlo Simulation", "मोंटे कार्लो सिमुलेशन"),
    desc=_L("Thousands of possible futures — see the full range of outcomes, not one guess.",
            "हज़ारों संभावित भविष्य — एक अंदाज़ा नहीं, पूरा दायरा देखो।"),
    fields=_MC_FIELDS, compute=_mc_compute,
))


# =====================================================================
# 📊 CORPFIN — Capital Budgeting (MIRR / PI / discounted payback)
# =====================================================================
_CB_COLS = [("year", _L("Year", "साल")), ("cash_flow", _L("Cash flow", "कैश फ्लो"))]
_CB_FIELDS = [
    Field("investment", _L("Initial investment", "शुरुआती निवेश"), default=1000.0),
    Field("flows", _L("Future cash flows", "भावी कैश फ्लो"),
          "table", columns=_CB_COLS, rows=6),
    Field("finance_pct", _L("Finance (discount) rate %", "वित्त (छूट) दर %"), "percent", 12.0),
    Field("reinvest_pct", _L("Reinvestment rate %", "पुनर्निवेश दर %"), "percent", 10.0),
]


def _cb_compute(v: dict, lang: str) -> ModelOutput:
    hi = lang == "hi"
    flows = clean_table(v["flows"], ["cash_flow"]).dropna(subset=["cash_flow"])
    if flows.empty:
        msg = ("Add at least one future cash flow." if not hi
               else "कम से कम एक भावी कैश फ्लो भरें।")
        return ModelOutput(kpis=[], results=[], verdict=f"⚠️ {msg}")
    cfs = flows["cash_flow"].tolist()
    invest = float(v["investment"])
    fin, rei = _pct(v["finance_pct"]), _pct(v["reinvest_pct"])
    n = len(cfs)

    npv = -invest + sum(cf / (1 + fin) ** (i + 1) for i, cf in enumerate(cfs))
    pv_inflows = sum(cf / (1 + fin) ** (i + 1) for i, cf in enumerate(cfs) if cf > 0)
    pi = pv_inflows / invest if invest else 0
    fv_pos = sum(cf * (1 + rei) ** (n - (i + 1)) for i, cf in enumerate(cfs) if cf > 0)
    pv_neg = invest + sum(-cf / (1 + fin) ** (i + 1) for i, cf in enumerate(cfs) if cf < 0)
    mirr = (fv_pos / pv_neg) ** (1 / n) - 1 if pv_neg > 0 and fv_pos > 0 else None

    disc_cum = np.cumsum([-invest] + [cf / (1 + fin) ** (i + 1) for i, cf in enumerate(cfs)])
    dpayback = next((i for i, c in enumerate(disc_cum) if c >= 0), None)

    title = "Discounted cumulative cash" if not hi else "छूट-सहित संचयी कैश"
    fig = base_figure(title)
    xs = ([("Today" if not hi else "आज")] + [f"Y{i}" for i in range(1, n + 1)])
    fig.add_trace(go.Scatter(x=xs, y=disc_cum, mode="lines+markers",
                             line=dict(color=PRIMARY_COLOR, width=2.5), marker=dict(size=8),
                             hovertemplate="%{x}: <b>%{y:,.0f}</b><extra></extra>"))
    fig.add_hline(y=0, line_color=ACCENT_COLOR, line_width=2)
    pay = (f"Y{dpayback}" if dpayback else "—")
    insight = ((f"NPV {fmt(npv)}, MIRR {mirr * 100:.1f}% (more realistic than plain "
                f"IRR), profitability index {pi:.2f}× (>1 is good), discounted "
                f"payback {pay}.") if not hi and mirr is not None else
               (f"NPV {fmt(npv)}, MIRR {mirr * 100:.1f}%, PI {pi:.2f}×, छूट-सहित "
                f"वापसी {pay}।") if mirr is not None else
               (f"NPV {fmt(npv)}, PI {pi:.2f}×."))
    guide = ("MIRR fixes IRR's flaw by assuming realistic reinvestment; PI shows "
             "value created per rupee invested; discounted payback is when you "
             "truly recover your money." if not hi else
             "MIRR, IRR की ख़ामी को असल पुनर्निवेश मानकर ठीक करता है; PI हर रुपये पर "
             "बनी क़ीमत; छूट-सहित वापसी वह समय जब पैसा सच में वसूल।")
    kpis = [Kpi("NPV", fmt(npv)),
            Kpi("MIRR", f"{mirr * 100:.1f}%" if mirr is not None else "—"),
            Kpi("Profitability index" if not hi else "लाभप्रदता सूचकांक", f"{pi:.2f}×"),
            Kpi("Disc. payback" if not hi else "छूट-सहित वापसी", pay)]
    good = npv > 0 and pi > 1
    verdict = ("✅ Value-creating investment." if good else "⚠️ Does not create value.") \
        if not hi else ("✅ मूल्य बनाने वाला निवेश।" if good else "⚠️ मूल्य नहीं बनाता।")
    return ModelOutput(kpis=kpis, verdict=verdict,
                       results=[chart_result(title, fig, insight, guide, priority=1)])


register(ModelSpec(
    key="capital_budget", category="corpfin",
    name=_L("Capital Budgeting — MIRR / PI", "पूंजी बजटिंग — MIRR / PI"),
    desc=_L("Deeper project appraisal: MIRR, profitability index, discounted payback.",
            "गहरी प्रोजेक्ट जाँच: MIRR, लाभप्रदता सूचकांक, छूट-सहित वापसी।"),
    fields=_CB_FIELDS, compute=_cb_compute,
))


# =====================================================================
# 🤝 M&A — Purchase Price Allocation (PPA)
# =====================================================================
_PPA_FIELDS = [
    Field("purchase_price", _L("Purchase price (equity)", "ख़रीद मूल्य (इक्विटी)"), default=1800.0),
    Field("book_equity", _L("Target book equity", "टार्गेट बही इक्विटी"), default=700.0),
    Field("ppe_stepup", _L("Fair-value step-up on assets", "संपत्तियों पर उचित-मूल्य step-up"), default=200.0),
    Field("intangibles", _L("Identifiable intangibles (brand, IP)", "पहचान योग्य अमूर्त (ब्रांड, IP)"), default=350.0),
    Field("tax_pct", _L("Tax rate % (for deferred tax)", "कर दर % (deferred tax हेतु)"), "percent", 25.0),
]


def _ppa_compute(v: dict, lang: str) -> ModelOutput:
    hi = lang == "hi"
    price = float(v["purchase_price"])
    book = float(v["book_equity"])
    stepup = float(v["ppe_stepup"])
    intang = float(v["intangibles"])
    dtl = _pct(v["tax_pct"]) * (stepup + intang)
    goodwill = price - book - stepup - intang + dtl

    title = "Purchase price allocation" if not hi else "ख़रीद मूल्य आवंटन"
    fig = base_figure(title)
    fig.add_trace(go.Waterfall(
        x=(["Purchase price", "− Book equity", "− Asset step-up", "− Intangibles",
            "+ Deferred tax", "Goodwill"] if not hi else
           ["ख़रीद मूल्य", "− बही इक्विटी", "− संपत्ति step-up", "− अमूर्त",
            "+ Deferred tax", "गुडविल"]),
        measure=["absolute", "relative", "relative", "relative", "relative", "total"],
        y=[price, -book, -stepup, -intang, dtl, 0],
        connector=dict(line=dict(color="#e8eaed")),
        increasing=dict(marker=dict(color=PRIMARY_COLOR)),
        decreasing=dict(marker=dict(color="#A8862F")),
        totals=dict(marker=dict(color=ACCENT_COLOR)),
        hovertemplate="%{x}: <b>%{y:,.0f}</b><extra></extra>",
    ))
    gw_pct = goodwill / price * 100 if price else 0
    insight = ((f"After marking up assets ({fmt(stepup)}) and booking intangibles "
                f"({fmt(intang)}), goodwill is {fmt(goodwill)} — {gw_pct:.0f}% of "
                f"the price. High goodwill means you paid mostly for future "
                f"promise, not tangible assets.")
               if not hi else
               (f"संपत्तियाँ ({fmt(stepup)}) और अमूर्त ({fmt(intang)}) दर्ज करने के "
                f"बाद गुडविल {fmt(goodwill)} है — क़ीमत का {gw_pct:.0f}%। ज़्यादा "
                f"गुडविल यानी आपने ठोस संपत्ति से ज़्यादा भविष्य के वादे के पैसे दिए।"))
    guide = ("When you buy a company, the price is split across its real assets, "
             "identified intangibles, and whatever is left over — goodwill. Big "
             "goodwill is fine, but it's the first thing that gets written off if "
             "the deal disappoints." if not hi else
             "कंपनी ख़रीदते समय क़ीमत उसकी असली संपत्ति, पहचाने अमूर्त, और बाक़ी बचे "
             "— गुडविल — में बँटती है। ज़्यादा गुडविल ठीक है, पर डील बिगड़ने पर सबसे "
             "पहले यही बट्टे खाते जाती है।")
    kpis = [Kpi("Goodwill" if not hi else "गुडविल", fmt(goodwill)),
            Kpi("Goodwill % of price" if not hi else "गुडविल % क़ीमत", f"{gw_pct:.0f}%"),
            Kpi("Deferred tax liab." if not hi else "Deferred tax", fmt(dtl)),
            Kpi("Intangibles" if not hi else "अमूर्त", fmt(intang))]
    verdict = ((f"Goodwill {fmt(goodwill)} ({gw_pct:.0f}% of price).") if not hi
               else f"गुडविल {fmt(goodwill)} (क़ीमत का {gw_pct:.0f}%)।")
    return ModelOutput(kpis=kpis, verdict=verdict,
                       results=[chart_result(title, fig, insight, guide, priority=1)])


register(ModelSpec(
    key="ppa", category="ma",
    name=_L("Purchase Price Allocation (PPA)", "ख़रीद मूल्य आवंटन (PPA)"),
    desc=_L("Split the deal price into assets, intangibles and goodwill.",
            "डील मूल्य को संपत्ति, अमूर्त और गुडविल में बाँटो।"),
    fields=_PPA_FIELDS, compute=_ppa_compute,
))


# =====================================================================
# 🏦 LBO/PE — Cap Table & Dilution
# =====================================================================
_CAP_COLS = [
    ("round", _L("Round", "राउंड")),
    ("investment", _L("Investment", "निवेश")),
    ("pre_money", _L("Pre-money valuation", "प्री-मनी मूल्यांकन")),
]
_CAPTABLE_FIELDS = [
    Field("founder_shares", _L("Founder shares (start)", "फ़ाउंडर शेयर (शुरुआत)"), default=1000000.0),
    Field("rounds", _L("Funding rounds", "फ़ंडिंग राउंड"),
          "table", columns=_CAP_COLS, rows=3),
]


def _captable_compute(v: dict, lang: str) -> ModelOutput:
    hi = lang == "hi"
    rounds = clean_table(v["rounds"], ["investment", "pre_money"]).dropna(
        subset=["investment", "pre_money"])
    if rounds.empty:
        msg = ("Add at least one funding round." if not hi
               else "कम से कम एक फ़ंडिंग राउंड भरें।")
        return ModelOutput(kpis=[], results=[], verdict=f"⚠️ {msg}")
    founder_shares = float(v["founder_shares"])
    total_shares = founder_shares
    founder_own = [100.0]
    labels = [("Founding" if not hi else "शुरुआत")]
    price_hist = []
    for _, r in rounds.iterrows():
        pre, inv = float(r["pre_money"]), float(r["investment"])
        price = pre / total_shares if total_shares else 0
        new_shares = inv / price if price else 0
        total_shares += new_shares
        price_hist.append(price)
        founder_own.append(founder_shares / total_shares * 100)
        labels.append(str(r["round"]) if pd.notna(r["round"]) else f"Round {len(labels)}")

    title = "Founder ownership through rounds" if not hi else "राउंड-दर-राउंड फ़ाउंडर हिस्सा"
    fig = base_figure(title)
    fig.add_trace(go.Scatter(
        x=labels, y=founder_own, mode="lines+markers+text",
        line=dict(color=PRIMARY_COLOR, width=2.5), marker=dict(size=9),
        text=[f"{o:.0f}%" for o in founder_own], textposition="top center",
        textfont=dict(color=MUTED, size=11),
        hovertemplate="%{x}: <b>%{y:.1f}%</b><extra></extra>",
    ))
    final_own = founder_own[-1]
    final_val = founder_shares * price_hist[-1] if price_hist else 0
    insight = ((f"After {len(rounds)} round(s), founders hold {final_own:.0f}% "
                f"(down from 100%), but their stake is now worth {fmt(final_val)} at "
                f"the latest round price. Dilution is fine if the pie grows faster.")
               if not hi else
               (f"{len(rounds)} राउंड के बाद फ़ाउंडर के पास {final_own:.0f}% है "
                f"(100% से घटकर), पर उनका हिस्सा अब ताज़ा राउंड भाव पर {fmt(final_val)} "
                f"का है। dilution ठीक है अगर पाई तेज़ी से बढ़े।"))
    guide = ("Each funding round issues new shares, so founders own a smaller "
             "slice — but of a bigger pie. Falling % with rising value is the "
             "healthy startup path." if not hi else
             "हर राउंड नए शेयर देता है, तो फ़ाउंडर का हिस्सा घटता है — पर बड़ी पाई "
             "का। घटता % पर बढ़ती क़ीमत ही सेहतमंद स्टार्टअप राह है।")
    table_rows = pd.DataFrame({
        (("Round" if not hi else "राउंड")): labels,
        (("Founder %" if not hi else "फ़ाउंडर %")): [f"{o:.1f}%" for o in founder_own],
    })
    kpis = [Kpi("Founder ownership" if not hi else "फ़ाउंडर हिस्सा", f"{final_own:.0f}%"),
            Kpi("Total dilution" if not hi else "कुल dilution", f"{100 - final_own:.0f}%"),
            Kpi("Founder stake value" if not hi else "फ़ाउंडर हिस्सा मूल्य", fmt(final_val)),
            Kpi("Rounds" if not hi else "राउंड", str(len(rounds)))]
    verdict = ((f"Founders retain {final_own:.0f}% after {len(rounds)} round(s).")
               if not hi else f"{len(rounds)} राउंड बाद फ़ाउंडर के पास {final_own:.0f}%।")
    return ModelOutput(kpis=kpis, verdict=verdict, results=[
        chart_result(title, fig, insight, guide, priority=1),
        AnalysisResult(question="Cap table" if not hi else "कैप टेबल",
                       kind="dataframe", dataframe=table_rows, priority=2),
    ])


register(ModelSpec(
    key="captable", category="lbo",
    name=_L("Cap Table & Dilution", "कैप टेबल व Dilution"),
    desc=_L("How founder ownership dilutes across funding rounds — and its value.",
            "फ़ंडिंग राउंड में फ़ाउंडर हिस्सा कैसे घटता है — और उसकी क़ीमत।"),
    fields=_CAPTABLE_FIELDS, compute=_captable_compute,
))


# =====================================================================
# 💳 CREDIT — Bank Metrics (NIM / CAMELS-lite)
# =====================================================================
_BANK_FIELDS = [
    Field("interest_income", _L("Interest income", "ब्याज आय"), default=900.0),
    Field("interest_expense", _L("Interest expense", "ब्याज खर्च"), default=480.0),
    Field("other_income", _L("Fee & other income", "फ़ीस व अन्य आय"), default=150.0),
    Field("opex", _L("Operating expenses", "परिचालन खर्च"), default=340.0),
    Field("provisions", _L("Loan loss provisions", "ऋण हानि प्रावधान"), default=90.0),
    Field("tax_pct", _L("Tax rate %", "कर दर %"), "percent", 25.0),
    Field("earning_assets", _L("Earning assets", "कमाऊ संपत्तियाँ"), default=12000.0),
    Field("total_assets", _L("Total assets", "कुल संपत्तियाँ"), default=14000.0),
    Field("equity", _L("Shareholder equity", "शेयरधारक इक्विटी"), default=1400.0),
    Field("npa_pct", _L("Gross NPA %", "सकल NPA %"), "percent", 4.5),
    Field("cet1_pct", _L("CET1 capital ratio %", "CET1 पूंजी अनुपात %"), "percent", 13.0),
]


def _bank_compute(v: dict, lang: str) -> ModelOutput:
    hi = lang == "hi"
    ii, ie = float(v["interest_income"]), float(v["interest_expense"])
    nii = ii - ie
    ea = max(float(v["earning_assets"]), 1e-9)
    ta = max(float(v["total_assets"]), 1e-9)
    eq = max(float(v["equity"]), 1e-9)
    total_income = nii + float(v["other_income"])
    pre_prov = total_income - float(v["opex"])
    pbt = pre_prov - float(v["provisions"])
    ni = pbt * (1 - _pct(v["tax_pct"]))
    nim = nii / ea * 100
    roa = ni / ta * 100
    roe = ni / eq * 100
    cost_income = float(v["opex"]) / total_income * 100 if total_income else 0

    def clamp(x):
        return min(max(x, 0), 100)
    parts = {
        ("Capital (CET1)" if not hi else "पूंजी (CET1)"):
            clamp((float(v["cet1_pct"]) - 8) / 8 * 100),
        ("Asset quality" if not hi else "संपत्ति गुणवत्ता"):
            clamp((8 - float(v["npa_pct"])) / 8 * 100),
        ("Earnings (ROA)" if not hi else "कमाई (ROA)"): clamp(roa / 2 * 100),
        ("Efficiency" if not hi else "दक्षता"): clamp((70 - cost_income) / 45 * 100),
        ("Margin (NIM)" if not hi else "मार्जिन (NIM)"): clamp(nim / 5 * 100),
    }
    composite = float(np.mean(list(parts.values())))
    band = (("Strong" if composite >= 70 else "Satisfactory" if composite >= 45 else "Weak")
            if not hi else
            ("मज़बूत" if composite >= 70 else "संतोषजनक" if composite >= 45 else "कमज़ोर"))

    title = f"Bank health (CAMELS-lite) — {band}" if not hi else f"बैंक सेहत (CAMELS-lite) — {band}"
    fig = base_figure(title)
    names = list(parts)
    scores = [parts[n] for n in names]
    weakest = names[int(np.argmin(scores))]
    colors = [ACCENT_COLOR if n == weakest else PRIMARY_COLOR for n in names]
    fig.add_trace(go.Bar(x=scores, y=names, orientation="h", marker_color=colors,
                         text=[f"{s:.0f}" for s in scores], textposition="outside",
                         textfont=dict(color=MUTED, size=12),
                         hovertemplate="%{y}: <b>%{x:.0f}</b>/100<extra></extra>"))
    fig.update_xaxes(range=[0, 112])
    insight = ((f"NIM {nim:.2f}%, ROA {roa:.2f}%, ROE {roe:.1f}%, cost-to-income "
                f"{cost_income:.0f}%. CAMELS-lite composite {composite:.0f}/100 → "
                f"{band}. Weakest pillar: {weakest}.")
               if not hi else
               (f"NIM {nim:.2f}%, ROA {roa:.2f}%, ROE {roe:.1f}%, cost-to-income "
                f"{cost_income:.0f}%। CAMELS-lite {composite:.0f}/100 → {band}। "
                f"सबसे कमज़ोर: {weakest}।"))
    guide = ("Banks are scored on Capital, Asset quality, Earnings, Efficiency and "
             "Margin — the CAMELS lens. Each bar is /100; the gold bar is the "
             "supervisor's first worry." if not hi else
             "बैंक को पूंजी, संपत्ति गुणवत्ता, कमाई, दक्षता और मार्जिन पर आँका जाता "
             "है — CAMELS नज़रिया। हर बार /100; सुनहरी बार पर्यवेक्षक की पहली चिंता।")
    kpis = [Kpi("Bank score" if not hi else "बैंक स्कोर", f"{composite:.0f}/100", band),
            Kpi("NIM", f"{nim:.2f}%"),
            Kpi("ROA", f"{roa:.2f}%"),
            Kpi("Cost-to-income" if not hi else "cost-to-income", f"{cost_income:.0f}%")]
    icon = "✅" if composite >= 45 else "⚠️"
    verdict = f"{icon} {composite:.0f}/100 — {band}. NIM {nim:.2f}%, ROE {roe:.1f}%."
    return ModelOutput(kpis=kpis, verdict=verdict,
                       results=[chart_result(title, fig, insight, guide, priority=1)])


register(ModelSpec(
    key="bank_metrics", category="credit",
    name=_L("Bank Metrics — NIM & CAMELS-lite", "बैंक मेट्रिक्स — NIM व CAMELS-lite"),
    desc=_L("Net interest margin, returns and a bank health score the CAMELS way.",
            "नेट इंटरेस्ट मार्जिन, रिटर्न और CAMELS तरीक़े से बैंक सेहत स्कोर।"),
    fields=_BANK_FIELDS, compute=_bank_compute,
))


# =====================================================================
# 💳 CREDIT — Merton Distance-to-Default
# =====================================================================
_MERTON_FIELDS = [
    Field("asset_value", _L("Market value of assets", "संपत्तियों का बाज़ार मूल्य"), default=1500.0),
    Field("asset_vol_pct", _L("Asset volatility % (annual)", "संपत्ति अस्थिरता % (सालाना)"), "percent", 22.0),
    Field("debt", _L("Debt (default point)", "क़र्ज़ (डिफ़ॉल्ट बिंदु)"), default=900.0),
    Field("rf_pct", _L("Risk-free rate %", "जोखिम-मुक्त दर %"), "percent", 7.0),
    Field("horizon", _L("Horizon (years)", "अवधि (साल)"), default=1.0),
]


def _merton_compute(v: dict, lang: str) -> ModelOutput:
    hi = lang == "hi"
    va = float(v["asset_value"])
    sig = max(_pct(v["asset_vol_pct"]), 1e-4)
    debt = max(float(v["debt"]), 1e-9)
    r = _pct(v["rf_pct"])
    t = max(float(v["horizon"]), 1e-3)
    dd = (math.log(va / debt) + (r - 0.5 * sig ** 2) * t) / (sig * math.sqrt(t))
    pd_ = _norm_cdf(-dd) * 100

    title = "Asset value distribution at horizon" if not hi else "अवधि पर संपत्ति मूल्य वितरण"
    fig = base_figure(title)
    mu = math.log(va) + (r - 0.5 * sig ** 2) * t
    sd = sig * math.sqrt(t)
    xs = np.linspace(math.exp(mu - 3.5 * sd), math.exp(mu + 3.5 * sd), 200)
    pdf = (1 / (xs * sd * math.sqrt(2 * math.pi))) * np.exp(-(np.log(xs) - mu) ** 2 / (2 * sd ** 2))
    fig.add_trace(go.Scatter(x=xs, y=pdf, mode="lines", line=dict(color=PRIMARY_COLOR, width=2.5),
                             fill="tozeroy", fillcolor="rgba(26,43,76,0.07)",
                             hovertemplate="%{x:,.0f}<extra></extra>"))
    fig.add_vline(x=debt, line_color=ACCENT_COLOR, line_width=2.5,
                  annotation_text=(f"Default point {fmt(debt)}" if not hi
                                   else f"डिफ़ॉल्ट बिंदु {fmt(debt)}"),
                  annotation_font=dict(color=ACCENT_COLOR, size=12))
    insight = ((f"The firm sits {dd:.2f} standard deviations above its default "
                f"point → about {pd_:.1f}% chance of default within {t:.0f} year(s). "
                f"Higher distance = safer.")
               if not hi else
               (f"कंपनी अपने डिफ़ॉल्ट बिंदु से {dd:.2f} मानक विचलन ऊपर है → लगभग "
                f"{pd_:.1f}% डिफ़ॉल्ट संभावना ({t:.0f} साल में)। ज़्यादा दूरी = ज़्यादा "
                f"सुरक्षित।"))
    guide = ("A market-based default probability: how many 'bad-luck steps' it "
             "takes for asset value to crash through the debt line. The gold line "
             "is that danger point; the more of the hill sits above it, the safer."
             if not hi else
             "बाज़ार-आधारित डिफ़ॉल्ट संभावना: संपत्ति मूल्य को क़र्ज़ रेखा तक गिरने "
             "में कितने 'बुरे क़दम' लगें। सुनहरी रेखा ख़तरा बिंदु; टीले का जितना "
             "हिस्सा उसके ऊपर, उतना सुरक्षित।")
    safe = pd_ < 2
    kpis = [Kpi("Distance-to-default" if not hi else "डिफ़ॉल्ट-दूरी", f"{dd:.2f}σ"),
            Kpi("Default probability" if not hi else "डिफ़ॉल्ट संभावना", f"{pd_:.1f}%"),
            Kpi("Asset / debt" if not hi else "संपत्ति / क़र्ज़", f"{va / debt:.2f}×")]
    icon = "✅" if safe else "🟡" if pd_ < 8 else "❌"
    verdict = (f"{icon} " + (f"{pd_:.1f}% default probability over {t:.0f}y ({dd:.2f}σ safe)."
               if not hi else f"{t:.0f} साल में {pd_:.1f}% डिफ़ॉल्ट संभावना ({dd:.2f}σ)।"))
    return ModelOutput(kpis=kpis, verdict=verdict,
                       results=[chart_result(title, fig, insight, guide, priority=1)])


register(ModelSpec(
    key="merton", category="credit",
    name=_L("Merton — Distance to Default", "मर्टन — डिफ़ॉल्ट दूरी"),
    desc=_L("Market-based probability that a firm defaults on its debt.",
            "कंपनी के क़र्ज़ डिफ़ॉल्ट की बाज़ार-आधारित संभावना।"),
    fields=_MERTON_FIELDS, compute=_merton_compute,
))


# =====================================================================
# 📈 MARKETS — Binomial Option Tree (American)
# =====================================================================
_BINOM_FIELDS = [
    Field("spot", _L("Spot price (S)", "मौजूदा भाव (S)"), default=100.0),
    Field("strike", _L("Strike (K)", "स्ट्राइक (K)"), default=100.0),
    Field("vol_pct", _L("Volatility % (annual)", "अस्थिरता % (सालाना)"), "percent", 30.0),
    Field("rf_pct", _L("Risk-free rate %", "जोखिम-मुक्त दर %"), "percent", 7.0),
    Field("t_years", _L("Time to expiry (years)", "एक्सपायरी तक समय (साल)"), default=1.0),
    Field("steps", _L("Tree steps", "ट्री steps"), "int", 50),
    Field("is_call", _L("Call (untick for put)", "Call (put के लिए हटाएँ)"), "bool", False),
]


def _binomial_price(s, k, vol, r, t, steps, is_call, american):
    dt = t / steps
    u = math.exp(vol * math.sqrt(dt))
    d = 1 / u
    p = (math.exp(r * dt) - d) / (u - d)
    disc = math.exp(-r * dt)
    prices = [s * u ** j * d ** (steps - j) for j in range(steps + 1)]
    values = [max((pr - k) if is_call else (k - pr), 0) for pr in prices]
    for step in range(steps - 1, -1, -1):
        for j in range(step + 1):
            cont = disc * (p * values[j + 1] + (1 - p) * values[j])
            if american:
                spot_now = s * u ** j * d ** (step - j)
                exercise = max((spot_now - k) if is_call else (k - spot_now), 0)
                values[j] = max(cont, exercise)
            else:
                values[j] = cont
    return values[0]


def _binom_compute(v: dict, lang: str) -> ModelOutput:
    hi = lang == "hi"
    s, k = float(v["spot"]), float(v["strike"])
    vol, r, t = _pct(v["vol_pct"]), _pct(v["rf_pct"]), max(float(v["t_years"]), 1e-3)
    steps = max(5, min(400, int(v["steps"])))
    is_call = bool(v["is_call"])
    american = _binomial_price(s, k, vol, r, t, steps, is_call, True)
    european = _binomial_price(s, k, vol, r, t, steps, is_call, False)
    premium = american - european

    step_range = [5, 10, 20, 40, 80, 160, min(steps, 320)]
    conv = [_binomial_price(s, k, vol, r, t, n, is_call, True) for n in step_range]
    title = "Price convergence as the tree grows" if not hi else "ट्री बढ़ने पर क़ीमत का स्थिर होना"
    fig = base_figure(title)
    fig.add_trace(go.Scatter(x=[str(n) for n in step_range], y=conv, mode="lines+markers",
                             line=dict(color=PRIMARY_COLOR, width=2.5), marker=dict(size=8),
                             hovertemplate="%{x} steps: <b>%{y:.3f}</b><extra></extra>"))
    fig.add_hline(y=american, line_dash="dot", line_color=ACCENT_COLOR)
    opt = ("American call" if is_call else "American put") if not hi \
        else ("अमेरिकन call" if is_call else "अमेरिकन put")
    insight = ((f"{opt} fair value {american:.3f}. Early-exercise premium over the "
                f"European version: {premium:.3f} "
                f"({'meaningful' if premium > 0.05 else 'negligible'} — puts and "
                f"dividend-bearing calls benefit most from early exercise).")
               if not hi else
               (f"{opt} उचित मूल्य {american:.3f}। European से early-exercise premium: "
                f"{premium:.3f} ({'सार्थक' if premium > 0.05 else 'नगण्य'})।"))
    guide = ("A binomial tree prices options that CAN be exercised early (American "
             "style), which Black-Scholes cannot. The curve shows the price settling "
             "as we add more branches." if not hi else
             "बाइनॉमियल ट्री उन ऑप्शनों को आँकता है जो जल्दी exercise हो सकते हैं "
             "(अमेरिकन), जो Black-Scholes नहीं कर सकता। curve दिखाता है ज़्यादा "
             "शाखाओं पर क़ीमत कैसे स्थिर होती है।")
    kpis = [Kpi("American price" if not hi else "अमेरिकन क़ीमत", f"{american:.3f}"),
            Kpi("European price" if not hi else "European क़ीमत", f"{european:.3f}"),
            Kpi("Early-exercise premium" if not hi else "early-exercise premium", f"{premium:.3f}"),
            Kpi("Steps" if not hi else "Steps", str(steps))]
    return ModelOutput(kpis=kpis, verdict=insight,
                       results=[chart_result(title, fig, insight, guide, priority=1)])


register(ModelSpec(
    key="binomial", category="markets",
    name=_L("Binomial Tree — American Options", "बाइनॉमियल ट्री — अमेरिकन ऑप्शन"),
    desc=_L("Price options that can be exercised early — where Black-Scholes stops.",
            "जल्दी exercise होने वाले ऑप्शन आँको — जहाँ Black-Scholes रुक जाता है।"),
    fields=_BINOM_FIELDS, compute=_binom_compute,
))


# =====================================================================
# 🌍 ECONOMICS — Phillips Curve
# =====================================================================
_PHIL_FIELDS = [
    Field("natural_unemp_pct", _L("Natural unemployment rate %", "प्राकृतिक बेरोज़गारी दर %"), "percent", 5.0),
    Field("current_unemp_pct", _L("Current unemployment %", "मौजूदा बेरोज़गारी %"), "percent", 4.0),
    Field("expected_inflation_pct", _L("Expected inflation %", "अपेक्षित महँगाई %"), "percent", 4.0),
    Field("sensitivity", _L("Trade-off sensitivity (β)", "अदला-बदली संवेदनशीलता (β)"), default=0.5),
    Field("supply_shock_pct", _L("Supply shock % (oil, food)", "आपूर्ति झटका % (तेल, भोजन)"), "percent", 0.0),
]


def _phillips_compute(v: dict, lang: str) -> ModelOutput:
    hi = lang == "hi"
    nat = float(v["natural_unemp_pct"])
    cur = float(v["current_unemp_pct"])
    exp_inf = float(v["expected_inflation_pct"])
    beta = float(v["sensitivity"])
    shock = float(v["supply_shock_pct"])
    inflation = exp_inf - beta * (cur - nat) + shock

    title = "Phillips curve — inflation vs unemployment" if not hi \
        else "फिलिप्स curve — महँगाई बनाम बेरोज़गारी"
    fig = base_figure(title)
    unemp_range = np.linspace(max(nat - 4, 0.5), nat + 4, 50)
    curve = exp_inf - beta * (unemp_range - nat) + shock
    fig.add_trace(go.Scatter(x=unemp_range, y=curve, mode="lines",
                             line=dict(color=PRIMARY_COLOR, width=2.5),
                             hovertemplate="Unemp %{x:.1f}%: <b>%{y:.1f}%</b><extra></extra>"))
    fig.add_trace(go.Scatter(x=[cur], y=[inflation], mode="markers+text",
                             marker=dict(color=ACCENT_COLOR, size=13),
                             text=[(f" now: {inflation:.1f}%" if not hi else f" अभी: {inflation:.1f}%")],
                             textposition="top right", textfont=dict(color=MUTED, size=12),
                             hoverinfo="skip"))
    fig.add_vline(x=nat, line_dash="dot", line_color=MUTED,
                  annotation_text=("natural rate" if not hi else "प्राकृतिक दर"),
                  annotation_font=dict(color=MUTED, size=11))
    fig.update_xaxes(ticksuffix="%")
    fig.update_yaxes(ticksuffix="%")
    gap = cur - nat
    heat = (("hot — jobs plentiful, wages and prices push up" if gap < 0
             else "slack — spare workers cool inflation") if not hi else
            ("गरम — नौकरियाँ भरपूर, मज़दूरी-क़ीमतें ऊपर" if gap < 0
             else "ढीला — बेकार श्रमिक महँगाई ठंडी करते हैं"))
    insight = ((f"With unemployment at {cur:.1f}% vs a {nat:.1f}% natural rate, the "
                f"economy is {heat}. Implied inflation ≈ {inflation:.1f}%"
                + (f", lifted by a {shock:.1f}% supply shock." if shock else "."))
               if not hi else
               (f"बेरोज़गारी {cur:.1f}% बनाम {nat:.1f}% प्राकृतिक दर पर अर्थव्यवस्था "
                f"{heat}। संभावित महँगाई ≈ {inflation:.1f}%"
                + (f", {shock:.1f}% आपूर्ति झटके से बढ़ी।" if shock else "।")))
    guide = ("The classic trade-off: push unemployment below its natural rate and "
             "inflation tends to rise. The gold dot is today; supply shocks shift "
             "the whole curve up." if not hi else
             "क्लासिक अदला-बदली: बेरोज़गारी प्राकृतिक दर से नीचे धकेलो तो महँगाई बढ़ती "
             "है। सुनहरा बिंदु आज; आपूर्ति झटके पूरी curve ऊपर खिसकाते हैं।")
    kpis = [Kpi("Implied inflation" if not hi else "संभावित महँगाई", f"{inflation:.1f}%"),
            Kpi("Unemployment gap" if not hi else "बेरोज़गारी अंतर", f"{gap:+.1f} pp"),
            Kpi("Supply shock" if not hi else "आपूर्ति झटका", f"{shock:+.1f}%")]
    return ModelOutput(kpis=kpis, verdict=insight,
                       results=[chart_result(title, fig, insight, guide, priority=1)])


register(ModelSpec(
    key="phillips", category="econ",
    name=_L("Phillips Curve", "फिलिप्स Curve"),
    desc=_L("The inflation vs unemployment trade-off, with supply shocks.",
            "महँगाई बनाम बेरोज़गारी की अदला-बदली, आपूर्ति झटकों के साथ।"),
    fields=_PHIL_FIELDS, compute=_phillips_compute,
))
