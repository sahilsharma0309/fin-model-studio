"""FinModel Studio — pick a model, fill the inputs, get a branded analysis.

Run with:  streamlit run app.py
"""

import re
from datetime import date

import pandas as pd
import streamlit as st

import models.corpfin  # noqa: F401 — registers corpfin models
import models.lbo  # noqa: F401 — registers LBO models
import models.ma  # noqa: F401 — registers M&A models
import models.valuation  # noqa: F401 — registers valuation models
from core.branding import ACCENT_COLOR, BRAND_NAME, MONOGRAM, PRIMARY_COLOR
from core.i18n import LANGUAGES
from core.report_docx import export_docx
from core.result import Kpi
from models.base import REGISTRY, table_default

try:
    from core.report_pdf import export_pdf
except OSError:
    export_pdf = None

CATEGORIES = {
    "valuation": {"en": "💰 Valuation", "hi": "💰 मूल्यांकन"},
    "corpfin": {"en": "📊 Corporate Finance / FP&A", "hi": "📊 कॉर्पोरेट फ़ाइनेंस / FP&A"},
    "ma": {"en": "🤝 M&A", "hi": "🤝 M&A"},
    "lbo": {"en": "🏦 LBO / Private Equity", "hi": "🏦 LBO / प्राइवेट इक्विटी"},
    "credit": {"en": "💳 Credit & Banking (Phase 4)", "hi": "💳 क्रेडिट व बैंकिंग (चरण 4)"},
    "markets": {"en": "📈 Markets & Portfolio (Phase 5)", "hi": "📈 मार्केट्स व पोर्टफ़ोलियो (चरण 5)"},
    "realestate": {"en": "🏢 Real Estate (Phase 6)", "hi": "🏢 रियल एस्टेट (चरण 6)"},
    "econ": {"en": "🌍 Economics (Phase 6)", "hi": "🌍 अर्थशास्त्र (चरण 6)"},
}

st.set_page_config(page_title="FinModel Studio", page_icon="🏛️", layout="wide")

st.markdown(
    f"""<style>
    #MainMenu, footer {{visibility: hidden;}}
    div[data-testid="stMetric"] {{
        background: #ffffff; border: 1px solid #e3e5e8;
        border-top: 3px solid {ACCENT_COLOR};
        padding: 14px 18px; border-radius: 8px;
        box-shadow: 0 1px 3px rgba(26,43,76,0.06);
    }}
    div[data-testid="stMetric"] label {{ color: #6a707a; }}
    </style>""",
    unsafe_allow_html=True,
)
st.markdown(
    f"""<div style="display:flex;align-items:center;gap:14px;padding:6px 0 14px 0;
         border-bottom:3px solid {ACCENT_COLOR};margin-bottom:16px">
      <div style="width:46px;height:46px;border-radius:50%;background:{PRIMARY_COLOR};
           color:{ACCENT_COLOR};display:flex;align-items:center;justify-content:center;
           font-weight:700;font-size:20px">{MONOGRAM}</div>
      <div>
        <div style="font-size:25px;font-weight:700;color:{PRIMARY_COLOR};line-height:1.15">
          FinModel Studio</div>
        <div style="color:#6a707a;font-size:14px">{BRAND_NAME} · Valuation, M&A,
          credit &amp; market models — pick, fill, analyze, export</div>
      </div>
    </div>""",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------- sidebar
with st.sidebar:
    st.header("Settings")
    lang_label = st.radio("Report language / रिपोर्ट की भाषा",
                          list(LANGUAGES), horizontal=True)
    lang = LANGUAGES[lang_label]

    st.header("Model")
    cat_key = st.selectbox(
        "Category" if lang != "hi" else "श्रेणी",
        list(CATEGORIES),
        format_func=lambda k: CATEGORIES[k].get(lang, CATEGORIES[k]["en"]),
    )
    specs = REGISTRY.get(cat_key, [])
    if not specs:
        st.info("Coming in a later phase — Valuation is live now."
                if lang != "hi" else "अगले चरण में आ रहा है — अभी Valuation चालू है।")
        spec = None
    else:
        spec = st.selectbox(
            "Model" if lang != "hi" else "मॉडल",
            specs, format_func=lambda s: s.name.get(lang, s.name["en"]),
        )

if spec is None:
    st.stop()

# ---------------------------------------------------------------- form
st.subheader(spec.name.get(lang, spec.name["en"]))
st.caption(spec.desc.get(lang, spec.desc["en"]))

values: dict = {}
with st.form(key=f"form_{spec.key}"):
    columns = st.columns(2)
    slot = 0
    for field in spec.fields:
        label = field.label.get(lang, field.label["en"])
        help_text = (field.help or {}).get(lang) if field.help else None
        if field.kind == "table":
            st.markdown(f"**{label}**")
            default = table_default(field.columns, field.rows)
            renamed = {key: col_label.get(lang, col_label["en"])
                       for key, col_label in field.columns}
            edited = st.data_editor(
                default.rename(columns=renamed), num_rows="dynamic",
                use_container_width=True, key=f"{spec.key}_{field.key}",
            )
            back = {v: k for k, v in renamed.items()}
            values[field.key] = edited.rename(columns=back)
        elif field.kind == "bool":
            values[field.key] = st.checkbox(label, value=bool(field.default),
                                            help=help_text)
        else:
            with columns[slot % 2]:
                if field.kind == "int":
                    values[field.key] = st.number_input(
                        label, value=int(field.default), step=1, help=help_text)
                else:
                    values[field.key] = st.number_input(
                        label, value=float(field.default),
                        min_value=field.min_value, help=help_text,
                        format="%.2f",
                    )
            slot += 1
    submitted = st.form_submit_button(
        "🔎 Analyze" if lang != "hi" else "🔎 विश्लेषण करें", type="primary")

if submitted:
    with st.spinner("Calculating..." if lang != "hi" else "गणना हो रही है..."):
        st.session_state.output = spec.compute(values, lang)
        st.session_state.output_model = spec.name.get(lang, spec.name["en"])
        st.session_state.pop("report_files", None)

# ---------------------------------------------------------------- results
output = st.session_state.get("output")
if output is not None:
    if output.verdict:
        (st.warning if output.verdict.startswith("⚠️") else st.success)(output.verdict)
    if output.kpis:
        cols = st.columns(len(output.kpis))
        for slot_col, kpi in zip(cols, output.kpis):
            slot_col.metric(kpi.label, kpi.value, kpi.delta or None)
    for item in output.results:
        st.markdown(f"**{item.question}**")
        if item.figure is not None:
            st.plotly_chart(item.figure, use_container_width=True)
        if item.kind == "dataframe" and item.dataframe is not None:
            st.dataframe(item.dataframe, use_container_width=True, hide_index=True)
        if item.text:
            st.markdown(f"💡 {item.text}")
        if item.guide:
            st.caption(f"📖 {item.guide}")
        st.divider()

    # ------------------------------------------------------------ export
    if output.results:
        st.subheader("Export Report" if lang != "hi" else "रिपोर्ट निर्यात करें")
        col_title, col_client = st.columns(2)
        with col_title:
            report_title = st.text_input(
                "Report title" if lang != "hi" else "रिपोर्ट शीर्षक",
                value=st.session_state.get("output_model", "Analysis Report"))
        with col_client:
            client_name = st.text_input(
                "Prepared for (client, optional)" if lang != "hi"
                else "किसके लिए (क्लाइंट, वैकल्पिक)", value="")

        if st.button("🧾 Generate report files" if lang != "hi"
                     else "🧾 रिपोर्ट फ़ाइलें बनाएँ", type="primary"):
            extra = list(output.results)
            if output.verdict and not output.verdict.startswith("⚠️"):
                from core.result import AnalysisResult
                extra.append(AnalysisResult(
                    question="Verdict" if lang != "hi" else "निष्कर्ष",
                    kind="text", text=output.verdict, priority=99))
            parts = [report_title.strip() or "report"]
            if client_name.strip():
                parts.append(client_name.strip())
            parts.append(f"{date.today():%Y-%m-%d}")
            stem = "_".join(
                re.sub(r"[^A-Za-z0-9-]+", "_", p).strip("_") or "x" for p in parts)
            files = {"stem": stem}
            with st.spinner("Building..."):
                if export_pdf is not None:
                    try:
                        files["pdf"] = export_pdf(
                            extra, report_title, st.session_state.get("output_model", ""),
                            kpis=output.kpis, client_name=client_name.strip(), lang=lang)
                    except Exception as exc:
                        st.error(f"PDF export failed: {exc}")
                try:
                    files["docx"] = export_docx(
                        extra, report_title, st.session_state.get("output_model", ""),
                        kpis=output.kpis, client_name=client_name.strip(), lang=lang)
                except Exception as exc:
                    st.error(f"Word export failed: {exc}")
            st.session_state.report_files = files

        files = st.session_state.get("report_files")
        if files:
            col_pdf, col_docx = st.columns(2)
            with col_pdf:
                if "pdf" in files:
                    st.download_button(
                        "⬇️ Download PDF", files["pdf"], file_name=f"{files['stem']}.pdf",
                        mime="application/pdf", use_container_width=True)
            with col_docx:
                if "docx" in files:
                    st.download_button(
                        "⬇️ Download Word", files["docx"],
                        file_name=f"{files['stem']}.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        use_container_width=True)
else:
    st.info("Fill the inputs above and press Analyze."
            if lang != "hi" else "ऊपर इनपुट भरें और 'विश्लेषण करें' दबाएँ।")
