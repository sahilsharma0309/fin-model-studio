"""Report/chart language strings — English and Hindi.

Column names from the data stay as-is; everything the tool writes around
them (titles, insights, reading guides, report chrome) is translated.
Add a language by adding a dict — missing keys fall back to English.
"""

LANGUAGES = {"English": "en", "हिंदी (Hindi)": "hi"}

STRINGS: dict[str, dict[str, str]] = {
    "en": {
        # KPI labels
        "kpi_records": "Records",
        "kpi_total": "Total {col}",
        "kpi_avg": "Avg {col}",
        "kpi_latest": "{month} {col}",
        "kpi_delta": "{change} vs {month}",
        "kpi_distinct": "Distinct {col}",
        # chart titles
        "title_trend": "{col} over time ({unit})",
        "unit_monthly": "monthly",
        "unit_daily": "daily",
        "title_growth": "{col} month-over-month growth %",
        "title_comparison": "{col} by {cat} over time (top {n})",
        "title_heatmap": "{col} heatmap — {cat} × month",
        "title_weekday": "Average {col} by day of week",
        "title_bar": "{col} by {cat}",
        "title_distribution": "Distribution of {col}",
        "title_correlation": "Correlation between numeric columns",
        # insights
        "ins_trend": "{col} moved {direction} {change:.1f}% across the period "
                     "({first} → {last}), peaking at {peak} in {peak_month}.",
        "up": "up", "down": "down",
        "ins_growth": "{ups} of {total} months grew (navy = growth, gold = decline). "
                      "Best month: {best} ({best_pct:+.1f}%); toughest: {worst} ({worst_pct:+.1f}%).",
        "ins_comparison": "Comparing the top {n} {cat} groups by {col}.",
        "ins_comparison_growth": " {fastest} grew fastest across the period "
                                 "({fastest_pct:+.1f}%), while {slowest} moved {slowest_pct:+.1f}%.",
        "ins_heatmap": "The single strongest cell is {cat} in {month} ({value}).",
        "ins_weekday": "{best} is the strongest day on average ({best_val}); "
                       "{worst} is the quietest ({worst_val}).",
        "ins_bar": "{top} leads with {value} — {share:.1f}% of all {col} across "
                   "{n} {cat} groups{note}.",
        "ins_bar_note": " (top {shown} of {total} shown)",
        "ins_distribution": "{col} ranges {vmin}–{vmax} with a median of {median} "
                            "and mean of {mean} across {n:,} records.",
        "ins_correlation": "The strongest relationship is between {a} and {b} "
                           "({value:+.2f}), which move {word} together "
                           "(navy = positive, gold = negative).",
        "positively": "positively", "negatively": "negatively",
        # reading guides
        "guide_trend": "Read left to right — each point is one period's total. Line "
                       "going up means business is growing. The gold dot marks the latest figure.",
        "guide_growth": "Each bar compares one month with the month before it. A navy bar "
                        "above the line means better than last month; a gold bar below "
                        "means less than last month.",
        "guide_comparison": "Each colored line is one group — its name is written at the "
                            "line's end. Whichever line sits higher sold more that month.",
        "guide_heatmap": "Darker box = more business. Read across a row to follow one "
                         "{cat} month by month; read down a column to compare everyone "
                         "in the same month.",
        "guide_weekday": "Each bar is a day of the week, averaged across the whole period. "
                         "The gold bar is your best day — plan stock, staff, or offers around it.",
        "guide_bar": "Longer bar = bigger total. The gold bar at the top is the No. 1. "
                     "The number written next to each bar is its actual total.",
        "guide_distribution": "This shows how the values are spread out. A tall bar means "
                              "many records fall around that amount. The gold line is the "
                              "middle value — half the records are below it, half above.",
        "guide_correlation": "Each box shows how two columns move together, from -1 to +1. "
                             "Navy near +1: both rise together. Gold near -1: one rises "
                             "while the other falls. Near 0: no real link.",
        "median": "median",
        # report chrome
        # 3D & animation studio
        "title_3d_scatter": "3D view — {x} × {y} × {z}",
        "guide_3d_scatter": "Every dot is one record, placed by three measures at "
                            "once. Drag (or swipe) to spin it — clusters of dots "
                            "are records that behave alike.",
        "title_3d_surface": "3D landscape — {col} by {cat} and month",
        "guide_3d_surface": "Height = business. Peaks are the best group-month "
                            "combos, valleys the quiet ones. Drag to rotate.",
        "title_race": "Animated race — {col} by {cat}, month by month",
        "guide_race": "Press ▶ Play and watch the bars grow month by month — "
                      "you can see exactly when each group pulled ahead.",
        "need_3_numeric": "3D scatter needs at least 3 numeric columns.",
        "need_time_cat": "The 3D landscape and the animated race need a date "
                         "column plus a category column.",
        "key_findings": "Key Findings",
        "how_to_read": "How to read",
        "prepared_for": "Prepared for",
        "dataset": "Dataset",
        "showing_first": "Showing first {shown} of {total} rows.",
        "no_chartable": "No suitable numeric/categorical columns found to chart automatically.",
    },
    "hi": {
        "kpi_records": "रिकॉर्ड",
        "kpi_total": "कुल {col}",
        "kpi_avg": "औसत {col}",
        "kpi_latest": "{month} {col}",
        "kpi_delta": "{change} बनाम {month}",
        "kpi_distinct": "अलग-अलग {col}",
        "title_trend": "{col} समय के साथ ({unit})",
        "unit_monthly": "मासिक",
        "unit_daily": "दैनिक",
        "title_growth": "{col} — महीने-दर-महीने बढ़त %",
        "title_comparison": "{col} — {cat} की तुलना समय के साथ (टॉप {n})",
        "title_heatmap": "{col} हीटमैप — {cat} × महीना",
        "title_weekday": "हफ़्ते के दिन के हिसाब से औसत {col}",
        "title_bar": "{cat} के हिसाब से {col}",
        "title_distribution": "{col} का फैलाव",
        "title_correlation": "संख्या वाले कॉलमों का आपसी संबंध",
        "ins_trend": "पूरी अवधि में {col} {change:.1f}% {direction} गया "
                     "({first} → {last}); सबसे ऊँचा {peak_month} में {peak} रहा।",
        "up": "ऊपर", "down": "नीचे",
        "ins_growth": "{total} में से {ups} महीने बढ़े (नीला = बढ़त, सुनहरा = गिरावट)। "
                      "सबसे अच्छा महीना: {best} ({best_pct:+.1f}%); सबसे कमज़ोर: {worst} ({worst_pct:+.1f}%)।",
        "ins_comparison": "{col} के हिसाब से टॉप {n} {cat} समूहों की तुलना।",
        "ins_comparison_growth": " {fastest} सबसे तेज़ बढ़ा ({fastest_pct:+.1f}%), "
                                 "जबकि {slowest} {slowest_pct:+.1f}% रहा।",
        "ins_heatmap": "सबसे मज़बूत खाना: {month} में {cat} ({value})।",
        "ins_weekday": "औसतन {best} सबसे अच्छा दिन है ({best_val}); "
                       "{worst} सबसे धीमा ({worst_val})।",
        "ins_bar": "{top} सबसे आगे है — {value}, यानी कुल {col} का {share:.1f}% "
                   "({n} {cat} समूहों में){note}।",
        "ins_bar_note": " (कुल {total} में से टॉप {shown} दिखाए गए)",
        "ins_distribution": "{col} {vmin} से {vmax} के बीच है; बीच का मान (median) {median} "
                            "और औसत {mean} — कुल {n:,} रिकॉर्ड।",
        "ins_correlation": "सबसे मज़बूत संबंध {a} और {b} के बीच है ({value:+.2f}) — "
                           "ये {word} चलते हैं (नीला = साथ बढ़ते, सुनहरा = उल्टा)।",
        "positively": "साथ-साथ", "negatively": "उल्टे",
        "guide_trend": "बाएँ से दाएँ पढ़ें — हर बिंदु एक अवधि का कुल है। रेखा ऊपर जाए तो "
                       "कारोबार बढ़ रहा है। सुनहरा बिंदु सबसे ताज़ा आँकड़ा है।",
        "guide_growth": "हर बार पिछले महीने से तुलना है। रेखा के ऊपर नीली बार = पिछले महीने "
                        "से बेहतर; नीचे सुनहरी बार = पिछले महीने से कम।",
        "guide_comparison": "हर रंगीन रेखा एक समूह है — नाम रेखा के आख़िर में लिखा है। "
                            "जो रेखा ऊपर है, उस महीने वही आगे रहा।",
        "guide_heatmap": "गहरा खाना = ज़्यादा कारोबार। एक पंक्ति में बाएँ से दाएँ देखें तो एक "
                         "{cat} का महीना-दर-महीना हाल; एक कॉलम में ऊपर से नीचे देखें तो उस "
                         "महीने में सबकी तुलना।",
        "guide_weekday": "हर बार हफ़्ते का एक दिन है (पूरी अवधि का औसत)। सुनहरी बार आपका "
                         "सबसे अच्छा दिन है — स्टॉक, स्टाफ़ या ऑफ़र उसी हिसाब से रखें।",
        "guide_bar": "लंबी बार = बड़ा कुल। सबसे ऊपर सुनहरी बार नंबर 1 है। हर बार के पास "
                     "लिखा अंक उसका असली कुल है।",
        "guide_distribution": "यह दिखाता है कि मान कैसे फैले हैं। ऊँची बार यानी उतनी रक़म के "
                              "आसपास ज़्यादा रिकॉर्ड। सुनहरी रेखा बीच का मान है — आधे रिकॉर्ड "
                              "उससे नीचे, आधे ऊपर।",
        "guide_correlation": "हर खाना बताता है कि दो कॉलम साथ कैसे चलते हैं (-1 से +1)। "
                             "नीला +1 के पास: दोनों साथ बढ़ते हैं। सुनहरा -1 के पास: एक बढ़े "
                             "तो दूसरा घटे। 0 के पास: कोई ख़ास संबंध नहीं।",
        "median": "बीच का मान",
        "title_3d_scatter": "3D नज़ारा — {x} × {y} × {z}",
        "guide_3d_scatter": "हर बिंदु एक रिकॉर्ड है, तीन मापों पर एक साथ रखा हुआ। "
                            "खींचकर (या स्वाइप करके) घुमाइए — पास-पास के बिंदु "
                            "मिलते-जुलते रिकॉर्ड हैं।",
        "title_3d_surface": "3D भू-दृश्य — {cat} और महीने के हिसाब से {col}",
        "guide_3d_surface": "ऊँचाई = कारोबार। चोटियाँ सबसे अच्छे समूह-महीने हैं, "
                            "घाटियाँ सबसे धीमे। खींचकर घुमाइए।",
        "title_race": "एनिमेटेड रेस — {cat} के हिसाब से {col}, महीना-दर-महीना",
        "guide_race": "▶ Play दबाइए और बार को महीने-दर-महीने बढ़ते देखिए — साफ़ "
                      "दिखता है कौन कब आगे निकला।",
        "need_3_numeric": "3D स्कैटर के लिए कम से कम 3 संख्या वाले कॉलम चाहिए।",
        "need_time_cat": "3D भू-दृश्य और एनिमेटेड रेस के लिए तारीख़ वाला कॉलम और "
                         "श्रेणी वाला कॉलम चाहिए।",
        "key_findings": "मुख्य निष्कर्ष",
        "how_to_read": "कैसे पढ़ें",
        "prepared_for": "के लिए तैयार",
        "dataset": "डेटा फ़ाइल",
        "showing_first": "कुल {total} पंक्तियों में से पहली {shown} दिखाई गई हैं।",
        "no_chartable": "चार्ट बनाने लायक़ संख्या/श्रेणी वाले कॉलम नहीं मिले।",
    },
}


def t(key: str, lang: str = "en") -> str:
    table = STRINGS.get(lang, STRINGS["en"])
    return table.get(key, STRINGS["en"][key])
