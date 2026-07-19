"""LBO / Private Equity models — returns model with value-creation bridge,
GP/LP distribution waterfall, and the Returns Composite mix."""

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


# ------------------------------------------------------ LBO returns
_LBO_FIELDS = [
    Field("ebitda", _L("Entry EBITDA", "एंट्री EBITDA"), default=100.0),
    Field("entry_mult", _L("Entry multiple (× EBITDA)", "एंट्री मल्टीपल (× EBITDA)"), default=9.0),
    Field("leverage_pct", _L("Debt % of purchase price", "ख़रीद में क़र्ज़ %"), "percent", 60.0),
    Field("interest_pct", _L("Interest rate on debt %", "क़र्ज़ पर ब्याज %"), "percent", 9.0),
    Field("growth_pct", _L("EBITDA growth % / year", "EBITDA वृद्धि % / साल"), "percent", 8.0),
    Field("conv_pct", _L("EBITDA converted to debt paydown %", "क़र्ज़ चुकाने में गया EBITDA %"), "percent", 40.0),
    Field("exit_mult", _L("Exit multiple (× EBITDA)", "एग्ज़िट मल्टीपल (× EBITDA)"), default=9.5),
    Field("years", _L("Holding period (years)", "होल्डिंग अवधि (साल)"), "int", 5),
]


def _lbo_core(v: dict) -> dict:
    ebitda0 = float(v["ebitda"])
    ev0 = ebitda0 * float(v["entry_mult"])
    debt = ev0 * _pct(v["leverage_pct"])
    debt0 = debt
    equity0 = ev0 - debt
    years = max(3, min(7, int(v["years"])))
    ebitda = ebitda0
    debt_path, ebitda_path = [debt], [ebitda0]
    for _ in range(years):
        ebitda *= 1 + _pct(v["growth_pct"])
        interest = debt * _pct(v["interest_pct"])
        paydown = max(ebitda * _pct(v["conv_pct"]) - interest, 0)
        debt = max(debt - paydown, 0)
        debt_path.append(debt)
        ebitda_path.append(ebitda)
    ev_exit = ebitda * float(v["exit_mult"])
    equity_exit = max(ev_exit - debt, 0)
    moic = equity_exit / equity0 if equity0 else 0
    irr = (moic ** (1 / years) - 1) * 100 if moic > 0 else -100.0
    return dict(ev0=ev0, debt0=debt0, equity0=equity0, years=years,
                debt_path=debt_path, ebitda_path=ebitda_path, ebitda_exit=ebitda,
                ev_exit=ev_exit, debt_exit=debt, equity_exit=equity_exit,
                moic=moic, irr=irr)


def _lbo_compute(v: dict, lang: str) -> ModelOutput:
    hi = lang == "hi"
    d = _lbo_core(v)
    if d["equity0"] <= 0:
        msg = ("Equity check-in must be positive — lower the leverage." if not hi
               else "इक्विटी सकारात्मक होनी चाहिए — leverage घटाएँ।")
        return ModelOutput(kpis=[], results=[], verdict=f"⚠️ {msg}")

    title1 = "Debt paydown over the hold" if not hi else "होल्डिंग के दौरान क़र्ज़ घटना"
    fig1 = base_figure(title1)
    xs = [f"Y{y}" for y in range(0, d["years"] + 1)]
    fig1.add_trace(go.Scatter(
        x=xs, y=d["debt_path"], mode="lines+markers",
        line=dict(color=ACCENT_COLOR, width=2.5), marker=dict(size=7),
        fill="tozeroy", fillcolor="rgba(201,169,77,0.12)",
        name="Debt" if not hi else "क़र्ज़",
        hovertemplate="%{x}: <b>%{y:,.0f}</b><extra></extra>",
    ))
    ins1 = ((f"Debt falls from {fmt(d['debt0'])} to {fmt(d['debt_exit'])} as the "
             f"business pays it down from cash flow.")
            if not hi else
            (f"कारोबार के कैश से क़र्ज़ {fmt(d['debt0'])} से घटकर "
             f"{fmt(d['debt_exit'])} रह जाता है।"))
    g1 = ("The lower this line ends, the more of the exit price belongs to the "
          "investor instead of the bank." if not hi else
          "यह रेखा जितनी नीचे ख़त्म हो, बिक्री की क़ीमत में investor का हिस्सा उतना "
          "बड़ा — बैंक का उतना छोटा।")

    growth_effect = (d["ebitda_exit"] - float(v["ebitda"])) * float(v["entry_mult"])
    mult_effect = d["ebitda_exit"] * (float(v["exit_mult"]) - float(v["entry_mult"]))
    delever_effect = d["debt0"] - d["debt_exit"]
    title2 = "Value creation bridge" if not hi else "मूल्य निर्माण सेतु"
    fig2 = base_figure(title2)
    fig2.add_trace(go.Waterfall(
        x=(["Equity in", "EBITDA growth", "Multiple change", "Debt paydown", "Equity out"]
           if not hi else
           ["लगाई इक्विटी", "EBITDA वृद्धि", "मल्टीपल बदलाव", "क़र्ज़ चुकौती", "निकली इक्विटी"]),
        measure=["absolute", "relative", "relative", "relative", "total"],
        y=[d["equity0"], growth_effect, mult_effect, delever_effect, 0],
        connector=dict(line=dict(color="#e8eaed")),
        increasing=dict(marker=dict(color=PRIMARY_COLOR)),
        decreasing=dict(marker=dict(color=ACCENT_COLOR)),
        totals=dict(marker=dict(color="#3D5C9E")),
        hovertemplate="%{x}: <b>%{y:,.0f}</b><extra></extra>",
    ))
    biggest = max([("growth", growth_effect), ("multiple", mult_effect),
                   ("deleveraging", delever_effect)], key=lambda t: t[1])
    biggest_name = ({"growth": "EBITDA growth", "multiple": "multiple change",
                     "deleveraging": "debt paydown"}[biggest[0]] if not hi else
                    {"growth": "EBITDA वृद्धि", "multiple": "मल्टीपल बदलाव",
                     "deleveraging": "क़र्ज़ चुकौती"}[biggest[0]])
    ins2 = ((f"Equity grows {fmt(d['equity0'])} → {fmt(d['equity_exit'])}; the "
             f"biggest driver is {biggest_name} (+{fmt(biggest[1])}).")
            if not hi else
            (f"इक्विटी {fmt(d['equity0'])} → {fmt(d['equity_exit'])}; सबसे बड़ा "
             f"कारण {biggest_name} (+{fmt(biggest[1])})।"))
    g2 = ("Reads left to right: money in, the three ways an LBO makes money, "
          "money out. Healthy deals rely on growth more than on multiple luck."
          if not hi else
          "बाएँ से दाएँ: लगाया पैसा, LBO के कमाई के तीन रास्ते, निकला पैसा। अच्छी "
          "डील growth पर टिकती है, मल्टीपल की क़िस्मत पर नहीं।")

    band = (("Strong" if d["irr"] >= 25 else "OK" if d["irr"] >= 18 else "Weak")
            if not hi else
            ("मज़बूत" if d["irr"] >= 25 else "ठीक" if d["irr"] >= 18 else "कमज़ोर"))
    kpis = [
        Kpi("IRR", f"{d['irr']:.1f}%", band),
        Kpi("MOIC", f"{d['moic']:.2f}×"),
        Kpi("Equity in → out" if not hi else "इक्विटी अंदर → बाहर",
            f"{fmt(d['equity0'])} → {fmt(d['equity_exit'])}"),
        Kpi("Exit debt" if not hi else "एग्ज़िट क़र्ज़", fmt(d["debt_exit"])),
    ]
    verdict = ((f"{d['moic']:.2f}× money, {d['irr']:.1f}% IRR over {d['years']} years — {band}.")
               if not hi else
               (f"{d['years']} साल में {d['moic']:.2f}× पैसा, {d['irr']:.1f}% IRR — {band}।"))
    return ModelOutput(kpis=kpis, verdict=verdict, results=[
        chart_result(title2, fig2, ins2, g2, priority=1),
        chart_result(title1, fig1, ins1, g1, priority=2),
    ])


register(ModelSpec(
    key="lbo", category="lbo",
    name=_L("LBO Returns Model", "LBO रिटर्न मॉडल"),
    desc=_L("Buy with debt, grow, pay down, sell — what IRR and multiple of money?",
            "क़र्ज़ से ख़रीदो, बढ़ाओ, क़र्ज़ चुकाओ, बेचो — कितना IRR और कितने गुना पैसा?"),
    fields=_LBO_FIELDS, compute=_lbo_compute,
))


# --------------------------------------------- GP/LP waterfall
_WF_FIELDS = [
    Field("invested", _L("LP capital invested", "LP का लगाया पैसा"), default=100.0),
    Field("proceeds", _L("Total exit proceeds", "कुल निकासी रक़म"), default=250.0),
    Field("hurdle_pct", _L("Preferred return (hurdle) %", "पसंदीदा रिटर्न (hurdle) %"), "percent", 8.0),
    Field("carry_pct", _L("GP carry %", "GP carry %"), "percent", 20.0),
    Field("catchup", _L("GP catch-up clause", "GP catch-up शर्त"), "bool", True),
]


def _wf_compute(v: dict, lang: str) -> ModelOutput:
    hi = lang == "hi"
    invested = float(v["invested"])
    proceeds = float(v["proceeds"])
    hurdle = invested * _pct(v["hurdle_pct"])
    carry = _pct(v["carry_pct"])

    remaining = proceeds
    lp_capital = min(remaining, invested); remaining -= lp_capital
    lp_pref = min(remaining, hurdle); remaining -= lp_pref
    gp_catchup = 0.0
    if v.get("catchup") and remaining > 0 and carry < 1:
        target = carry / (1 - carry) * lp_pref
        gp_catchup = min(remaining, target); remaining -= gp_catchup
    gp_carry = remaining * carry
    lp_split = remaining * (1 - carry)
    lp_total = lp_capital + lp_pref + lp_split
    gp_total = gp_catchup + gp_carry
    profits = max(proceeds - invested, 1e-9)
    eff_carry = gp_total / profits * 100

    title = "Distribution waterfall — LP vs GP" if not hi else "बँटवारा — LP बनाम GP"
    fig = base_figure(title)
    stages = (["Capital back", "Preferred", "Catch-up", "80/20 split"]
              if not hi else ["पूंजी वापसी", "पसंदीदा रिटर्न", "Catch-up", "80/20 बँटवारा"])
    lp_vals = [lp_capital, lp_pref, 0, lp_split]
    gp_vals = [0, 0, gp_catchup, gp_carry]
    fig.add_trace(go.Bar(name="LP", x=stages, y=lp_vals, marker_color="#3D5C9E",
                         hovertemplate="LP · %{x}: <b>%{y:,.1f}</b><extra></extra>"))
    fig.add_trace(go.Bar(name="GP", x=stages, y=gp_vals, marker_color="#A8862F",
                         hovertemplate="GP · %{x}: <b>%{y:,.1f}</b><extra></extra>"))
    fig.update_layout(barmode="stack", showlegend=True,
                      legend=dict(orientation="h", y=1.08, x=0))

    insight = ((f"Of {fmt(proceeds)} proceeds, LPs receive {fmt(lp_total)} "
                f"({lp_total / invested:.2f}× their money) and the GP earns "
                f"{fmt(gp_total)} — an effective {eff_carry:.0f}% of profits.")
               if not hi else
               (f"{fmt(proceeds)} में से LP को {fmt(lp_total)} मिलता है "
                f"({lp_total / invested:.2f}× पैसा) और GP को {fmt(gp_total)} — "
                f"लाभ का असरदार {eff_carry:.0f}%।"))
    guide = ("Money flows left to right: investors get their capital back first, "
             "then a promised minimum return; only after that does the fund "
             "manager start earning a share." if not hi else
             "पैसा बाएँ से दाएँ बहता है: पहले investor की पूंजी वापस, फिर वादा "
             "किया न्यूनतम रिटर्न; उसके बाद ही fund manager की कमाई शुरू।")
    kpis = [
        Kpi("LP receives" if not hi else "LP को", fmt(lp_total),
            f"{lp_total / invested:.2f}×"),
        Kpi("GP receives" if not hi else "GP को", fmt(gp_total)),
        Kpi("Effective carry" if not hi else "असरदार carry", f"{eff_carry:.0f}%"),
    ]
    verdict = ((f"LP net multiple {lp_total / invested:.2f}×; GP takes "
                f"{eff_carry:.0f}% of profits.")
               if not hi else
               (f"LP का नेट {lp_total / invested:.2f}×; GP लाभ का {eff_carry:.0f}% "
                f"लेता है।"))
    return ModelOutput(kpis=kpis, verdict=verdict,
                       results=[chart_result(title, fig, insight, guide, priority=1)])


register(ModelSpec(
    key="waterfall", category="lbo",
    name=_L("Returns Waterfall — GP/LP split", "रिटर्न waterfall — GP/LP बँटवारा"),
    desc=_L("Who gets what when the fund exits: investors first, manager's carry after.",
            "निकासी पर किसे क्या मिलता है: पहले investor, बाद में manager का carry।"),
    fields=_WF_FIELDS, compute=_wf_compute,
))


# ------------------------------------------- ⭐ Returns Composite mix
_MIX_FIELDS = _LBO_FIELDS + [
    Field("bull_bear_mult", _L("Scenario swing on exit multiple (±×)",
                               "एग्ज़िट मल्टीपल पर परिदृश्य झूला (±×)"), default=1.0),
    Field("bull_bear_growth", _L("Scenario swing on growth (± % points)",
                                 "growth पर परिदृश्य झूला (± % अंक)"), default=3.0),
]

WEIGHTS = {"bear": 0.25, "base": 0.50, "bull": 0.25}


def _lbo_mix_compute(v: dict, lang: str) -> ModelOutput:
    hi = lang == "hi"
    dm = float(v["bull_bear_mult"])
    dg = float(v["bull_bear_growth"])
    scenarios = {
        "bear": {**v, "exit_mult": float(v["exit_mult"]) - dm,
                 "growth_pct": float(v["growth_pct"]) - dg},
        "base": dict(v),
        "bull": {**v, "exit_mult": float(v["exit_mult"]) + dm,
                 "growth_pct": float(v["growth_pct"]) + dg},
    }
    runs = {name: _lbo_core(s) for name, s in scenarios.items()}
    if runs["base"]["equity0"] <= 0:
        msg = ("Equity check-in must be positive — lower the leverage." if not hi
               else "इक्विटी सकारात्मक होनी चाहिए — leverage घटाएँ।")
        return ModelOutput(kpis=[], results=[], verdict=f"⚠️ {msg}")
    w_irr = sum(runs[n]["irr"] * WEIGHTS[n] for n in runs)
    w_moic = sum(runs[n]["moic"] * WEIGHTS[n] for n in runs)

    # IRR grid: exit multiple x growth
    mults = [float(v["exit_mult"]) + step for step in (-dm, -dm / 2, 0, dm / 2, dm)]
    growths = [float(v["growth_pct"]) + step for step in (-dg, -dg / 2, 0, dg / 2, dg)]
    grid = [[_lbo_core({**v, "exit_mult": m, "growth_pct": g})["irr"]
             for m in mults] for g in growths]

    title = ("⭐ IRR grid — exit multiple × growth" if not hi
             else "⭐ IRR ग्रिड — एग्ज़िट मल्टीपल × growth")
    fig = base_figure(title)
    fig.add_trace(go.Heatmap(
        z=grid, x=[f"{m:.1f}×" for m in mults], y=[f"{g:.0f}%" for g in growths],
        colorscale=[[0.0, "#f6f7f9"], [1.0, PRIMARY_COLOR]],
        text=np.round(np.array(grid), 0), texttemplate="%{text:.0f}%",
        textfont=dict(size=11),
        hovertemplate=("Exit %{x} · growth %{y}: <b>%{z:.1f}%</b><extra></extra>"),
        colorbar=dict(tickfont=dict(color=MUTED), ticksuffix="%"),
    ))
    fig.update_layout(height=470)
    fig.update_yaxes(title_text=("EBITDA growth" if not hi else "EBITDA वृद्धि"))

    insight = ((f"Probability-weighted (25/50/25): IRR {w_irr:.1f}%, MOIC "
                f"{w_moic:.2f}×. Range: bear {runs['bear']['irr']:.1f}% → bull "
                f"{runs['bull']['irr']:.1f}%.")
               if not hi else
               (f"संभावना-भारित (25/50/25): IRR {w_irr:.1f}%, MOIC {w_moic:.2f}×। "
                f"दायरा: मंदी {runs['bear']['irr']:.1f}% → तेज़ी "
                f"{runs['bull']['irr']:.1f}%।"))
    guide = ("Each cell is the deal's IRR under one combination of exit price and "
             "growth. Darker = better. If even the light corner clears your "
             "target, the deal is robust." if not hi else
             "हर खाना एक exit-क़ीमत और growth के जोड़ पर IRR है। गहरा = बेहतर। अगर "
             "हल्का कोना भी आपके लक्ष्य से ऊपर है, तो डील मज़बूत है।")
    band = (("Strong" if w_irr >= 25 else "OK" if w_irr >= 18 else "Weak") if not hi
            else ("मज़बूत" if w_irr >= 25 else "ठीक" if w_irr >= 18 else "कमज़ोर"))
    kpis = [
        Kpi("Weighted IRR" if not hi else "भारित IRR", f"{w_irr:.1f}%", band),
        Kpi("Weighted MOIC" if not hi else "भारित MOIC", f"{w_moic:.2f}×"),
        Kpi("Bear IRR" if not hi else "मंदी IRR", f"{runs['bear']['irr']:.1f}%"),
        Kpi("Bull IRR" if not hi else "तेज़ी IRR", f"{runs['bull']['irr']:.1f}%"),
    ]
    downside_ok = runs["bear"]["irr"] >= 10
    verdict = ((f"{'✅' if downside_ok else '⚠️'} Weighted IRR {w_irr:.1f}% ({band}); "
                f"downside {'holds at' if downside_ok else 'breaks to'} "
                f"{runs['bear']['irr']:.1f}%.")
               if not hi else
               (f"{'✅' if downside_ok else '⚠️'} भारित IRR {w_irr:.1f}% ({band}); "
                f"मंदी में {runs['bear']['irr']:.1f}%।"))
    return ModelOutput(kpis=kpis, verdict=verdict,
                       results=[chart_result(title, fig, insight, guide, priority=1)])


register(ModelSpec(
    key="mix_lbo", category="lbo", is_mix=True,
    name=_L("⭐ LBO Mix — Returns Composite", "⭐ LBO मिक्स — रिटर्न कम्पोज़िट"),
    desc=_L("Bear/base/bull scenarios probability-weighted into one IRR range, "
            "plus a full exit-multiple × growth IRR grid.",
            "मंदी/आधार/तेज़ी परिदृश्य संभावना-भार से एक IRR दायरे में, साथ में पूरा "
            "एग्ज़िट-मल्टीपल × growth IRR ग्रिड।"),
    fields=_MIX_FIELDS, compute=_lbo_mix_compute,
))
