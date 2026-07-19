"""Markets & Portfolio models — bond pricing with duration, CAPM,
Black-Scholes options, Markowitz frontier, parametric VaR, and the
Portfolio Intelligence mix."""

import math

import numpy as np
import plotly.graph_objects as go

from core.branding import ACCENT_COLOR, PRIMARY_COLOR, SERIES_PALETTE
from core.charts import MUTED, base_figure, chart_result, fmt
from core.result import Kpi
from models.base import Field, ModelOutput, ModelSpec, clean_table, register


def _L(en: str, hi: str) -> dict:
    return {"en": en, "hi": hi}


def _pct(x) -> float:
    return float(x or 0) / 100.0


def _norm_cdf(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def _norm_pdf(x: float) -> float:
    return math.exp(-x * x / 2) / math.sqrt(2 * math.pi)


# ------------------------------------------------------- Bond pricing
_BOND_FIELDS = [
    Field("face", _L("Face value", "अंकित मूल्य"), default=1000.0),
    Field("coupon_pct", _L("Coupon rate % (annual)", "कूपन दर % (सालाना)"), "percent", 7.5),
    Field("ytm_pct", _L("Market yield (YTM) %", "बाज़ार यील्ड (YTM) %"), "percent", 8.2),
    Field("years", _L("Years to maturity", "परिपक्वता के साल"), "int", 10),
]


def _bond_compute(v: dict, lang: str) -> ModelOutput:
    hi = lang == "hi"
    face = float(v["face"])
    coupon = face * _pct(v["coupon_pct"])
    y = _pct(v["ytm_pct"])
    n = max(1, int(v["years"]))
    pvs = [coupon / (1 + y) ** t for t in range(1, n + 1)]
    pvs[-1] += face / (1 + y) ** n
    price = sum(pvs)
    weighted = sum(t * pv for t, pv in zip(range(1, n + 1), pvs))
    macaulay = weighted / price if price else 0
    modified = macaulay / (1 + y)
    dv_1pct = -modified * price * 0.01

    title = "Bond cash flows (present value)" if not hi else "बॉन्ड कैश फ्लो (वर्तमान मूल्य)"
    fig = base_figure(title)
    colors = [PRIMARY_COLOR] * n
    colors[-1] = ACCENT_COLOR
    fig.add_trace(go.Bar(x=[f"Y{t}" for t in range(1, n + 1)], y=pvs,
                         marker_color=colors,
                         hovertemplate="%{x}: <b>%{y:,.1f}</b><extra></extra>"))
    premium = ((f"a discount (yield {v['ytm_pct']:.1f}% > coupon {v['coupon_pct']:.1f}%)"
                if price < face else
                f"a premium (coupon {v['coupon_pct']:.1f}% > yield {v['ytm_pct']:.1f}%)")
               if not hi else
               (f"छूट पर (यील्ड {v['ytm_pct']:.1f}% > कूपन {v['coupon_pct']:.1f}%)"
                if price < face else
                f"प्रीमियम पर (कूपन {v['coupon_pct']:.1f}% > यील्ड {v['ytm_pct']:.1f}%)"))
    insight = ((f"The bond is worth {fmt(price)} — trading at {premium}. If rates "
                f"rise 1%, the price falls about {fmt(-dv_1pct)}.")
               if not hi else
               (f"बॉन्ड की क़ीमत {fmt(price)} है — {premium}। दरें 1% बढ़ें तो "
                f"क़ीमत लगभग {fmt(-dv_1pct)} गिरती है।"))
    guide = ("Each bar is one future payment valued in today's money; the gold "
             "bar includes the face value at maturity. Duration says how hard "
             "rate moves hit the price." if not hi else
             "हर बार भविष्य का एक भुगतान आज की क़ीमत में; सुनहरी बार में परिपक्वता "
             "का अंकित मूल्य भी शामिल है। Duration बताता है दरों के झटके क़ीमत पर "
             "कितने भारी पड़ते हैं।")
    kpis = [
        Kpi("Price" if not hi else "क़ीमत", fmt(price)),
        Kpi("Macaulay duration" if not hi else "Macaulay duration", f"{macaulay:.2f}y"),
        Kpi("Modified duration", f"{modified:.2f}"),
        Kpi("Price if rates +1%" if not hi else "दरें +1% पर क़ीमत", fmt(price + dv_1pct)),
    ]
    verdict = insight
    return ModelOutput(kpis=kpis, verdict=verdict,
                       results=[chart_result(title, fig, insight, guide, priority=1)])


register(ModelSpec(
    key="bond", category="markets",
    name=_L("Bond Pricing & Duration", "बॉन्ड मूल्यांकन व Duration"),
    desc=_L("What a bond is worth today, and how badly rate moves hurt it.",
            "बॉन्ड आज कितने का है, और दरों के झटके कितना नुक़सान करते हैं।"),
    fields=_BOND_FIELDS, compute=_bond_compute,
))


# ----------------------------------------------------------- CAPM
_CAPM_FIELDS = [
    Field("rf_pct", _L("Risk-free rate %", "जोखिम-मुक्त दर %"), "percent", 7.0),
    Field("beta", _L("Equity beta", "इक्विटी बीटा"), default=1.2),
    Field("mkt_pct", _L("Expected market return %", "बाज़ार का अपेक्षित रिटर्न %"), "percent", 13.0),
    Field("debt_equity", _L("Debt / equity ratio (for unlevered beta)", "क़र्ज़/इक्विटी (unlevered बीटा हेतु)"), default=0.6),
    Field("tax_pct", _L("Tax rate %", "कर दर %"), "percent", 25.0),
]


def _capm_compute(v: dict, lang: str) -> ModelOutput:
    hi = lang == "hi"
    rf, beta, mkt = _pct(v["rf_pct"]), float(v["beta"]), _pct(v["mkt_pct"])
    ke = rf + beta * (mkt - rf)
    unlevered = beta / (1 + (1 - _pct(v["tax_pct"])) * float(v["debt_equity"]))

    title = "Security market line" if not hi else "सिक्योरिटी मार्केट लाइन"
    fig = base_figure(title)
    betas = np.linspace(0, 2.2, 40)
    fig.add_trace(go.Scatter(x=betas, y=(rf + betas * (mkt - rf)) * 100, mode="lines",
                             line=dict(color=PRIMARY_COLOR, width=2.5),
                             hovertemplate="β %{x:.2f}: <b>%{y:.1f}%</b><extra></extra>"))
    fig.add_trace(go.Scatter(x=[beta], y=[ke * 100], mode="markers+text",
                             marker=dict(color=ACCENT_COLOR, size=12),
                             text=[f" β {beta:.2f} → {ke * 100:.1f}%"],
                             textposition="middle right",
                             textfont=dict(color=MUTED, size=12), hoverinfo="skip"))
    fig.update_yaxes(ticksuffix="%")
    fig.update_xaxes(title_text="Beta" if not hi else "बीटा")

    insight = ((f"Cost of equity = {ke * 100:.1f}%: investors demand this return "
                f"for a stock {beta:.2f}× as volatile as the market. Business-only "
                f"(unlevered) beta is {unlevered:.2f}.")
               if not hi else
               (f"इक्विटी लागत = {ke * 100:.1f}%: बाज़ार से {beta:.2f}× ज़्यादा "
                f"हिलने वाले शेयर पर निवेशक इतना रिटर्न माँगते हैं। सिर्फ़-कारोबार "
                f"(unlevered) बीटा {unlevered:.2f} है।"))
    guide = ("The line is the fair return for each level of risk; the gold dot is "
             "this stock. Use the cost of equity as the discount rate in DCF/DDM."
             if not hi else
             "रेखा हर जोखिम स्तर का उचित रिटर्न है; सुनहरा बिंदु यह शेयर। इक्विटी "
             "लागत को DCF/DDM में छूट दर की तरह इस्तेमाल करें।")
    kpis = [
        Kpi("Cost of equity" if not hi else "इक्विटी लागत", f"{ke * 100:.1f}%"),
        Kpi("Unlevered beta" if not hi else "Unlevered बीटा", f"{unlevered:.2f}"),
        Kpi("Risk premium" if not hi else "जोखिम प्रीमियम", f"{(mkt - rf) * 100:.1f}%"),
    ]
    return ModelOutput(kpis=kpis, verdict=insight,
                       results=[chart_result(title, fig, insight, guide, priority=1)])


register(ModelSpec(
    key="capm", category="markets",
    name=_L("CAPM — Cost of Equity", "CAPM — इक्विटी लागत"),
    desc=_L("The return investors demand for a stock's risk — your DCF discount rate.",
            "शेयर के जोखिम पर निवेशकों की माँग — आपकी DCF छूट दर।"),
    fields=_CAPM_FIELDS, compute=_capm_compute,
))


# ------------------------------------------------- Black-Scholes
_BS_FIELDS = [
    Field("spot", _L("Spot price (S)", "मौजूदा भाव (S)"), default=100.0),
    Field("strike", _L("Strike price (K)", "स्ट्राइक भाव (K)"), default=105.0),
    Field("vol_pct", _L("Volatility % (annual)", "अस्थिरता % (सालाना)"), "percent", 30.0),
    Field("rf_pct", _L("Risk-free rate %", "जोखिम-मुक्त दर %"), "percent", 7.0),
    Field("t_years", _L("Time to expiry (years)", "एक्सपायरी तक समय (साल)"), default=0.5),
    Field("is_call", _L("Call option (untick for put)", "Call ऑप्शन (put के लिए हटाएँ)"), "bool", True),
]


def _bs_compute(v: dict, lang: str) -> ModelOutput:
    hi = lang == "hi"
    s, k = float(v["spot"]), float(v["strike"])
    vol, r, t = _pct(v["vol_pct"]), _pct(v["rf_pct"]), max(float(v["t_years"]), 1e-6)
    is_call = bool(v["is_call"])
    d1 = (math.log(s / k) + (r + vol ** 2 / 2) * t) / (vol * math.sqrt(t))
    d2 = d1 - vol * math.sqrt(t)
    if is_call:
        price = s * _norm_cdf(d1) - k * math.exp(-r * t) * _norm_cdf(d2)
        delta = _norm_cdf(d1)
    else:
        price = k * math.exp(-r * t) * _norm_cdf(-d2) - s * _norm_cdf(-d1)
        delta = _norm_cdf(d1) - 1
    vega = s * _norm_pdf(d1) * math.sqrt(t) / 100
    theta_day = (-(s * _norm_pdf(d1) * vol / (2 * math.sqrt(t)))
                 - (1 if is_call else -1) * r * k * math.exp(-r * t)
                 * _norm_cdf(d2 if is_call else -d2)) / 365

    spots = np.linspace(s * 0.6, s * 1.4, 60)
    payoff = np.maximum(spots - k, 0) if is_call else np.maximum(k - spots, 0)
    opt_name = ("Call" if is_call else "Put")
    title = (f"{opt_name} option — payoff at expiry" if not hi
             else f"{opt_name} ऑप्शन — एक्सपायरी पर मुनाफ़ा")
    fig = base_figure(title)
    fig.add_trace(go.Scatter(x=spots, y=payoff - price, mode="lines",
                             line=dict(color=PRIMARY_COLOR, width=2.5),
                             hovertemplate="Spot %{x:,.0f}: <b>%{y:,.1f}</b><extra></extra>"))
    fig.add_hline(y=0, line_color=ACCENT_COLOR, line_width=2)
    fig.add_vline(x=s, line_dash="dot", line_color=MUTED,
                  annotation_text=("today" if not hi else "आज"),
                  annotation_font=dict(color=MUTED, size=11))
    breakeven = k + price if is_call else k - price
    insight = ((f"Fair value {price:.2f}. Break-even at expiry: {breakeven:,.1f}. "
                f"Delta {delta:+.2f} (moves {abs(delta):.2f} per 1 of spot); loses "
                f"{abs(theta_day):.3f}/day to time decay.")
               if not hi else
               (f"उचित क़ीमत {price:.2f}। एक्सपायरी पर बराबरी: {breakeven:,.1f}। "
                f"Delta {delta:+.2f}; समय-क्षय से रोज़ {abs(theta_day):.3f} घटता है।"))
    guide = ("The line is your profit at expiry after paying the premium; below "
             "the gold zero-line you lose (at most the premium). The dotted line "
             "is today's price." if not hi else
             "रेखा = प्रीमियम चुकाने के बाद एक्सपायरी पर मुनाफ़ा; सुनहरी शून्य-रेखा "
             "से नीचे घाटा (ज़्यादा से ज़्यादा प्रीमियम)। बिंदीदार रेखा आज का भाव।")
    kpis = [
        Kpi(f"{opt_name} " + ("price" if not hi else "क़ीमत"), f"{price:.2f}"),
        Kpi("Delta", f"{delta:+.2f}"),
        Kpi("Vega (per 1% vol)", f"{vega:.3f}"),
        Kpi("Theta/day", f"{theta_day:.3f}"),
    ]
    return ModelOutput(kpis=kpis, verdict=insight,
                       results=[chart_result(title, fig, insight, guide, priority=1)])


register(ModelSpec(
    key="black_scholes", category="markets",
    name=_L("Black-Scholes — Option Pricing", "Black-Scholes — ऑप्शन मूल्यांकन"),
    desc=_L("Fair value and Greeks for a call or put option.",
            "Call/put ऑप्शन की उचित क़ीमत और Greeks।"),
    fields=_BS_FIELDS, compute=_bs_compute,
))


# ------------------------------------------------- Markowitz frontier
_MKW_COLS = [
    ("asset", _L("Asset", "एसेट")),
    ("weight", _L("Weight %", "वज़न %")),
    ("ret", _L("Expected return %", "अपेक्षित रिटर्न %")),
    ("vol", _L("Volatility %", "अस्थिरता %")),
]

_MKW_FIELDS = [
    Field("assets", _L("Portfolio assets (2-6 rows)", "पोर्टफ़ोलियो एसेट (2-6 पंक्तियाँ)"),
          "table", columns=_MKW_COLS, rows=3),
    Field("corr", _L("Average correlation between assets (0-1)", "एसेट्स के बीच औसत सह-संबंध (0-1)"), default=0.35),
    Field("rf_pct", _L("Risk-free rate %", "जोखिम-मुक्त दर %"), "percent", 7.0),
]


def _portfolio_stats(weights, rets, vols, corr):
    weights = np.asarray(weights, dtype=float)
    port_ret = float(weights @ rets)
    cov = np.outer(vols, vols) * corr
    np.fill_diagonal(cov, vols ** 2)
    port_vol = float(np.sqrt(weights @ cov @ weights))
    return port_ret, port_vol


def _mkw_compute(v: dict, lang: str) -> ModelOutput:
    hi = lang == "hi"
    table = clean_table(v["assets"], ["weight", "ret", "vol"])
    table = table.dropna(subset=["ret", "vol"])
    if len(table) < 2:
        msg = ("Add at least 2 assets with return and volatility." if not hi
               else "कम से कम 2 एसेट भरें (रिटर्न और अस्थिरता के साथ)।")
        return ModelOutput(kpis=[], results=[], verdict=f"⚠️ {msg}")
    names = table["asset"].fillna("—").astype(str).tolist()
    rets = table["ret"].to_numpy() / 100
    vols = table["vol"].to_numpy() / 100
    corr = min(max(float(v["corr"]), -0.5), 1.0)
    rf = _pct(v["rf_pct"])

    rng = np.random.default_rng(7)
    n = len(table)
    sims = []
    for _ in range(3000):
        w = rng.dirichlet(np.ones(n))
        r, s = _portfolio_stats(w, rets, vols, corr)
        sims.append((s, r, w))
    sharpe = [(r - rf) / s if s else 0 for s, r, _ in sims]
    best = int(np.argmax(sharpe))
    minv = int(np.argmin([s for s, _, _ in sims]))
    bs_, br_, bw = sims[best]
    ms_, mr_, _ = sims[minv]

    title = "Efficient frontier" if not hi else "एफ़िशिएंट फ़्रंटियर"
    fig = base_figure(title)
    fig.add_trace(go.Scatter(
        x=[s * 100 for s, _, _ in sims[::6]], y=[r * 100 for _, r, _ in sims[::6]],
        mode="markers", marker=dict(color="#b9c3d6", size=4, opacity=0.5),
        hoverinfo="skip", showlegend=False,
    ))
    for i, name in enumerate(names):
        fig.add_trace(go.Scatter(
            x=[vols[i] * 100], y=[rets[i] * 100], mode="markers+text",
            marker=dict(color=SERIES_PALETTE[i % len(SERIES_PALETTE)], size=10),
            text=[f" {name}"], textposition="middle right",
            textfont=dict(color=MUTED, size=11), showlegend=False,
            hovertemplate=f"{name}: vol %{{x:.1f}}%, ret %{{y:.1f}}%<extra></extra>",
        ))
    fig.add_trace(go.Scatter(
        x=[bs_ * 100], y=[br_ * 100], mode="markers+text",
        marker=dict(color=ACCENT_COLOR, size=14, symbol="star"),
        text=[" Max Sharpe" if not hi else " सर्वोत्तम"], textposition="top left",
        textfont=dict(color=ACCENT_COLOR, size=12), showlegend=False,
        hovertemplate=f"vol {bs_ * 100:.1f}%, ret {br_ * 100:.1f}%<extra></extra>",
    ))
    fig.update_xaxes(title_text=("Risk (volatility %)" if not hi else "जोखिम (अस्थिरता %)"),
                     ticksuffix="%")
    fig.update_yaxes(title_text=("Return %" if not hi else "रिटर्न %"), ticksuffix="%")

    weights_text = ", ".join(f"{names[i]} {bw[i] * 100:.0f}%" for i in range(n))
    insight = ((f"Best risk-adjusted mix: {weights_text} → {br_ * 100:.1f}% return "
                f"at {bs_ * 100:.1f}% risk (Sharpe {(br_ - rf) / bs_:.2f}). Min-risk "
                f"mix sits at {ms_ * 100:.1f}% risk.")
               if not hi else
               (f"सबसे अच्छा मिश्रण: {weights_text} → {bs_ * 100:.1f}% जोखिम पर "
                f"{br_ * 100:.1f}% रिटर्न (Sharpe {(br_ - rf) / bs_:.2f})। न्यूनतम "
                f"जोखिम {ms_ * 100:.1f}% पर।"))
    guide = ("Every grey dot is a possible mix of your assets. Up = more return, "
             "left = less risk — so up-and-left is better. The gold star is the "
             "best deal per unit of risk." if not hi else
             "हर धूसर बिंदु आपके एसेट्स का एक संभावित मिश्रण है। ऊपर = ज़्यादा "
             "रिटर्न, बाएँ = कम जोखिम — यानी ऊपर-बाएँ बेहतर। सुनहरा सितारा प्रति "
             "जोखिम सबसे अच्छा सौदा।")
    kpis = [
        Kpi("Max-Sharpe return" if not hi else "सर्वोत्तम रिटर्न", f"{br_ * 100:.1f}%"),
        Kpi("At risk" if not hi else "जोखिम पर", f"{bs_ * 100:.1f}%"),
        Kpi("Sharpe", f"{(br_ - rf) / bs_:.2f}"),
    ]
    return ModelOutput(kpis=kpis, verdict=insight,
                       results=[chart_result(title, fig, insight, guide, priority=1)])


register(ModelSpec(
    key="markowitz", category="markets",
    name=_L("Markowitz — Efficient Frontier", "Markowitz — एफ़िशिएंट फ़्रंटियर"),
    desc=_L("The best possible mixes of your assets, and the single best one.",
            "आपके एसेट्स के सबसे अच्छे संभव मिश्रण, और उनमें सर्वोत्तम।"),
    fields=_MKW_FIELDS, compute=_mkw_compute,
))


# ------------------------------------------------------------- VaR
_VAR_FIELDS = [
    Field("value", _L("Portfolio value", "पोर्टफ़ोलियो मूल्य"), default=10000000.0),
    Field("ret_pct", _L("Expected annual return %", "अपेक्षित सालाना रिटर्न %"), "percent", 12.0),
    Field("vol_pct", _L("Annual volatility %", "सालाना अस्थिरता %"), "percent", 18.0),
    Field("days", _L("Horizon (days)", "अवधि (दिन)"), "int", 10),
    Field("conf", _L("Confidence % (95 or 99)", "विश्वास % (95 या 99)"), "int", 95),
]


def _var_compute(v: dict, lang: str) -> ModelOutput:
    hi = lang == "hi"
    value = float(v["value"])
    mu_d = _pct(v["ret_pct"]) / 252
    sig_d = _pct(v["vol_pct"]) / math.sqrt(252)
    days = max(1, int(v["days"]))
    conf = 99 if int(v["conf"]) >= 97 else 95
    z = 2.3263 if conf == 99 else 1.6449
    mu_h = mu_d * days
    sig_h = sig_d * math.sqrt(days)
    var = value * (z * sig_h - mu_h)
    es_factor = _norm_pdf(z) / (1 - conf / 100)
    cvar = value * (es_factor * sig_h - mu_h)

    rng = np.random.default_rng(7)
    pnl = value * (mu_h + sig_h * rng.standard_normal(6000))
    title = (f"{days}-day P&L distribution — {conf}% VaR" if not hi
             else f"{days}-दिन लाभ-हानि वितरण — {conf}% VaR")
    fig = base_figure(title)
    fig.add_trace(go.Histogram(x=pnl, nbinsx=60,
                               marker=dict(color=PRIMARY_COLOR,
                                           line=dict(color="white", width=0.5)),
                               hovertemplate="%{x}: %{y}<extra></extra>"))
    fig.add_vline(x=-var, line_color=ACCENT_COLOR, line_width=2.5,
                  annotation_text=f"VaR {fmt(var)}",
                  annotation_font=dict(color=ACCENT_COLOR, size=12))
    insight = ((f"With {conf}% confidence, losses over {days} days should not "
                f"exceed {fmt(var)} ({var / value * 100:.1f}% of the portfolio). "
                f"If that tail is hit, the average loss is {fmt(cvar)} (CVaR).")
               if not hi else
               (f"{conf}% विश्वास से, {days} दिनों का घाटा {fmt(var)} "
                f"({var / value * 100:.1f}%) से ज़्यादा नहीं होना चाहिए। अगर वही "
                f"बुरा दिन आए, तो औसत घाटा {fmt(cvar)} (CVaR)।"))
    guide = ("The hill shows possible profit/loss outcomes; the gold line marks "
             "the bad day that should only happen " +
             ("1-in-20" if conf == 95 else "1-in-100") + " times. Money left of "
             "it is tail risk." if not hi else
             "टीला संभावित लाभ-हानि दिखाता है; सुनहरी रेखा वह बुरा दिन है जो सिर्फ़ " +
             ("20 में 1" if conf == 95 else "100 में 1") + " बार आना चाहिए। उससे "
             "बाईं ओर का पैसा tail risk है।")
    kpis = [
        Kpi(f"VaR {conf}%", fmt(var), f"{var / value * 100:.1f}%"),
        Kpi("CVaR", fmt(cvar)),
        Kpi("Horizon" if not hi else "अवधि", f"{days}d"),
    ]
    return ModelOutput(kpis=kpis, verdict=insight,
                       results=[chart_result(title, fig, insight, guide, priority=1)])


register(ModelSpec(
    key="var", category="markets",
    name=_L("Value at Risk (VaR)", "वैल्यू एट रिस्क (VaR)"),
    desc=_L("How much could you lose on a bad day — with numbers, not vibes.",
            "बुरे दिन कितना डूब सकता है — अंदाज़े से नहीं, आँकड़ों से।"),
    fields=_VAR_FIELDS, compute=_var_compute,
))


# ------------------------------------------- ⭐ Portfolio Intelligence
_MIXP_FIELDS = [
    Field("value", _L("Portfolio value", "पोर्टफ़ोलियो मूल्य"), default=10000000.0),
    Field("assets", _L("Assets (2-6 rows)", "एसेट (2-6 पंक्तियाँ)"),
          "table", columns=_MKW_COLS, rows=3),
    Field("corr", _L("Average correlation (0-1)", "औसत सह-संबंध (0-1)"), default=0.35),
    Field("rf_pct", _L("Risk-free rate %", "जोखिम-मुक्त दर %"), "percent", 7.0),
]


def _mixp_compute(v: dict, lang: str) -> ModelOutput:
    hi = lang == "hi"
    table = clean_table(v["assets"], ["weight", "ret", "vol"])
    table = table.dropna(subset=["weight", "ret", "vol"])
    if len(table) < 2 or table["weight"].sum() <= 0:
        msg = ("Add at least 2 assets with weight, return and volatility." if not hi
               else "कम से कम 2 एसेट भरें (वज़न, रिटर्न, अस्थिरता के साथ)।")
        return ModelOutput(kpis=[], results=[], verdict=f"⚠️ {msg}")
    w = table["weight"].to_numpy(dtype=float)
    w = w / w.sum()
    rets = table["ret"].to_numpy() / 100
    vols = table["vol"].to_numpy() / 100
    corr = min(max(float(v["corr"]), -0.5), 1.0)
    rf = _pct(v["rf_pct"])
    value = float(v["value"])

    port_ret, port_vol = _portfolio_stats(w, rets, vols, corr)
    sharpe = (port_ret - rf) / port_vol if port_vol else 0
    weighted_vol = float(w @ vols)
    div_benefit = (1 - port_vol / weighted_vol) * 100 if weighted_vol else 0
    hhi = float((w ** 2).sum())
    z95 = 1.6449
    var_1y = value * (z95 * port_vol - port_ret)

    def clamp(x):
        return min(max(x, 0), 100)

    parts = {
        ("Risk-adjusted return" if not hi else "जोखिम-सापेक्ष रिटर्न"):
            (clamp(sharpe / 1.2 * 100), 0.35),
        ("Diversification" if not hi else "विविधीकरण"):
            (clamp(div_benefit / 30 * 100), 0.25),
        ("Concentration" if not hi else "एकाग्रता"):
            (clamp((1 - (hhi - 1 / len(w)) / (1 - 1 / len(w))) * 100 if len(w) > 1 else 0), 0.20),
        ("Risk level" if not hi else "जोखिम स्तर"):
            (clamp((0.30 - port_vol) / 0.25 * 100), 0.20),
    }
    composite = sum(score * weight for score, weight in parts.values())

    title = "⭐ Portfolio intelligence scorecard" if not hi else "⭐ पोर्टफ़ोलियो इंटेलिजेंस स्कोरकार्ड"
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

    insight = ((f"Score {composite:.0f}/100. Portfolio: {port_ret * 100:.1f}% return "
                f"at {port_vol * 100:.1f}% risk (Sharpe {sharpe:.2f}); mixing saves "
                f"{div_benefit:.0f}% of risk; 1-year 95% VaR {fmt(var_1y)}. "
                f"Weakest: {weakest}.")
               if not hi else
               (f"स्कोर {composite:.0f}/100। पोर्टफ़ोलियो: {port_vol * 100:.1f}% जोखिम "
                f"पर {port_ret * 100:.1f}% रिटर्न (Sharpe {sharpe:.2f}); मिश्रण से "
                f"{div_benefit:.0f}% जोखिम बचता है; 1-साल 95% VaR {fmt(var_1y)}। "
                f"सबसे कमज़ोर: {weakest}।"))
    guide = ("Four professional lenses on one portfolio: does return justify risk, "
             "does mixing actually reduce risk, is money spread or piled up, and "
             "is total risk sane. Gold bar = fix this first." if not hi else
             "एक पोर्टफ़ोलियो पर चार पेशेवर नज़रिए: रिटर्न जोखिम के लायक़ है? मिश्रण "
             "सच में जोखिम घटाता है? पैसा फैला है या ढेर है? कुल जोखिम ठीक है? "
             "सुनहरी बार = पहले यही सुधारें।")
    band = (("Strong" if composite >= 70 else "Balanced" if composite >= 45 else "Review")
            if not hi else
            ("मज़बूत" if composite >= 70 else "संतुलित" if composite >= 45 else "पुनर्विचार"))
    kpis = [
        Kpi("Portfolio score" if not hi else "पोर्टफ़ोलियो स्कोर", f"{composite:.0f}/100", band),
        Kpi("Sharpe", f"{sharpe:.2f}"),
        Kpi("Return / risk" if not hi else "रिटर्न / जोखिम",
            f"{port_ret * 100:.1f}% / {port_vol * 100:.1f}%"),
        Kpi("1y VaR 95%", fmt(var_1y)),
    ]
    verdict = f"{'✅' if composite >= 45 else '⚠️'} {composite:.0f}/100 — {band}."
    return ModelOutput(kpis=kpis, verdict=verdict,
                       results=[chart_result(title, fig, insight, guide, priority=1)])


register(ModelSpec(
    key="mix_markets", category="markets", is_mix=True,
    name=_L("⭐ Markets Mix — Portfolio Intelligence",
            "⭐ मार्केट्स मिक्स — पोर्टफ़ोलियो इंटेलिजेंस"),
    desc=_L("Sharpe, diversification, concentration and risk level blended into "
            "one portfolio verdict with VaR attached.",
            "Sharpe, विविधीकरण, एकाग्रता और जोखिम स्तर मिलाकर एक पोर्टफ़ोलियो "
            "फ़ैसला — VaR के साथ।"),
    fields=_MIXP_FIELDS, compute=_mixp_compute,
))
