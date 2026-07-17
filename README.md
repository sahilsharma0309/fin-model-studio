# FinModel Studio

Financial modeling platform: pick a model from the category list, fill in
the inputs manually, and get an instant branded analysis — charts, plain-
language insights and reading guides (English/हिंदी), and a signed PDF/Word
report. No AI calls — every model is pure, auditable math.

## Live models (Phase 1 — Valuation)

- **DCF** — Discounted Cash Flow (FCFF, 5-year, Gordon terminal value)
- **Trading Comps** — peer median multiples (EV/EBITDA, P/E, EV/Revenue)
- **Precedent Transactions** — deal multiples incl. control premium
- **DDM** — two-stage Dividend Discount Model
- **NAV** — asset-based valuation (book vs market)
- **NPV / IRR** — investment appraisal with payback
- ⭐ **Valuation Mix — Triangulated Valuation**: runs the methods together
  and blends them with transparent, evidence-based weights into one
  defendable value range (football-field chart), the way fairness
  opinions are built.

## Roadmap

Phase 2 — Corporate Finance/FP&A · Phase 3 — M&A + LBO/PE ·
Phase 4 — Credit & Banking · Phase 5 — Markets & Portfolio ·
Phase 6 — Real Estate + Economics. Every category ends with its own
⭐ Mix model.

## Setup

> Requires Python 3.10–3.11.

```bash
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

WeasyPrint needs system libraries — on Streamlit Community Cloud
`packages.txt` handles it automatically; on Windows install the
[GTK3 runtime](https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases).

## Adding a model

Each model is a `ModelSpec` in `models/` — a list of input fields plus a
pure compute function returning KPIs, charts, and a verdict. Register it
and it appears in the picker automatically.
