import math
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import streamlit as st

st.set_page_config(
    page_title="INELSO Smart Learning Services",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
.block-container {padding-top: 1.6rem; padding-bottom: 3rem; max-width: 1250px;}
[data-testid="stMetric"] {
    background: #f7fbfd;
    border: 1px solid #d9e7ee;
    border-radius: 14px;
    padding: 14px 16px;
}
.inelso-hero {
    padding: 26px 28px;
    border-radius: 18px;
    background: linear-gradient(135deg,#102a43,#183b5b);
    color: white;
    margin-bottom: 18px;
}
.inelso-hero h1 {margin:0 0 8px 0; font-size:2.1rem;}
.inelso-hero p {margin:0; color:#dce9f5; font-size:1.05rem;}
.small-note {
    background:#eefafa;
    border-left:4px solid #2a8c99;
    border-radius:8px;
    padding:12px 14px;
}
</style>
""", unsafe_allow_html=True)

S21_DEMO = pd.DataFrame({
    "Ερώτηση": [f"Q{i:02d}" for i in range(1, 11)],
    "Ποσοστό σωστών (%)": [90, 56, 58, 44, 32, 26, 40, 54, 58, 18],
    "Δείκτης διάκρισης (%)": [28.06, 50.67, 40.76, 56.49, 41.14, 28.67, 54.50, -37.55, 45.11, 43.71],
})
S21_DEMO["Ερμηνεία"] = [
    "Πολύ εύκολη", "Καλή", "Καλή", "Ισχυρή", "Καλή",
    "Μέτρια", "Ισχυρή", "Χρειάζεται έλεγχο", "Καλή", "Δύσκολη αλλά διακριτική"
]

S26_DEMO = {
    "learners": 50,
    "attempts": 100,
    "attempt1": 54.53,
    "attempt2": 68.80,
    "mean_gain": 14.28,
    "median_gain": 15.00,
    "improved": 47,
    "unchanged": 1,
    "declined": 2,
    "ready": 94,
    "review": 6,
    "grade_writes": 0,
    "confidence1": 0.83,
    "confidence2": 0.87,
}
S26_MASTERY = pd.DataFrame({
    "Επίπεδο": ["Αρχικό", "Αναπτυσσόμενο", "Προς κατάκτηση", "Κατάκτηση"],
    "Εκπαιδευόμενοι": [6, 20, 16, 8],
})

def cronbach_alpha(df: pd.DataFrame):
    x = df.apply(pd.to_numeric, errors="coerce").dropna(axis=0, how="any")
    if x.shape[0] < 2 or x.shape[1] < 2:
        return np.nan
    item_vars = x.var(axis=0, ddof=1)
    total = x.sum(axis=1)
    total_var = total.var(ddof=1)
    if not np.isfinite(total_var) or total_var <= 0:
        return np.nan
    k = x.shape[1]
    return (k / (k - 1)) * (1 - item_vars.sum() / total_var)

def corrected_item_total(df: pd.DataFrame):
    x = df.apply(pd.to_numeric, errors="coerce")
    out = {}
    for col in x.columns:
        rest = x.drop(columns=[col]).sum(axis=1)
        valid = pd.concat([x[col], rest], axis=1).dropna()
        if len(valid) < 3 or valid.iloc[:,0].nunique() < 2 or valid.iloc[:,1].nunique() < 2:
            out[col] = np.nan
        else:
            out[col] = valid.iloc[:,0].corr(valid.iloc[:,1])
    return pd.Series(out)

def s21_from_upload(uploaded):
    df = pd.read_csv(uploaded)
    numeric = df.select_dtypes(include=[np.number]).copy()
    binary_cols = [c for c in numeric.columns if set(numeric[c].dropna().unique()).issubset({0, 1})]
    if len(binary_cols) >= 2:
        numeric = numeric[binary_cols]
    if numeric.shape[1] < 2:
        raise ValueError("Χρειάζονται τουλάχιστον δύο αριθμητικές στήλες απαντήσεων.")
    facility = numeric.mean(axis=0) * 100
    citc = corrected_item_total(numeric) * 100
    alpha = cronbach_alpha(numeric)
    table = pd.DataFrame({
        "Ερώτηση": numeric.columns.astype(str),
        "Ποσοστό σωστών (%)": facility.values,
        "Δείκτης διάκρισης (%)": citc.values,
    })
    table["Ερμηνεία"] = np.where(
        table["Δείκτης διάκρισης (%)"] < 0,
        "Χρειάζεται έλεγχο",
        np.where(table["Ποσοστό σωστών (%)"] >= 85, "Πολύ εύκολη",
                 np.where(table["Ποσοστό σωστών (%)"] <= 20, "Πολύ δύσκολη", "Κανονική"))
    )
    return table, alpha, len(numeric)


def s21_from_live_moodle():
    try:
        api_url = st.secrets["INELSO_LIVE_API_URL"]
        api_token = st.secrets["INELSO_LIVE_API_TOKEN"]
    except Exception:
        raise RuntimeError("Δεν έχουν ρυθμιστεί τα Streamlit Secrets για το Live Moodle API.")

    response = requests.get(
        api_url,
        headers={"X-INELSO-Token": api_token},
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()

    if not payload.get("ok"):
        raise RuntimeError(payload.get("error", "Το Live Moodle API επέστρεψε σφάλμα."))

    items = [x.get("id", f"Q{i+1:02d}") for i, x in enumerate(payload.get("items", []))]
    matrix = payload.get("matrix", [])
    if not matrix or not items:
        raise RuntimeError("Δεν επιστράφηκαν ολοκληρωμένες προσπάθειες από το Moodle.")

    df = pd.DataFrame(matrix, columns=items)
    df = df.apply(pd.to_numeric, errors="coerce")
    facility = df.mean(axis=0) * 100
    citc = corrected_item_total(df) * 100
    alpha = cronbach_alpha(df)

    table = pd.DataFrame({
        "Ερώτηση": items,
        "Ποσοστό σωστών (%)": facility.values,
        "Δείκτης διάκρισης (%)": citc.values,
    })
    table["Ερμηνεία"] = np.where(
        table["Δείκτης διάκρισης (%)"] < 0,
        "Χρειάζεται έλεγχο",
        np.where(table["Ποσοστό σωστών (%)"] >= 85, "Πολύ εύκολη",
                 np.where(table["Ποσοστό σωστών (%)"] <= 20, "Πολύ δύσκολη", "Κανονική"))
    )
    return table, alpha, int(payload.get("attempts", len(df))), payload

def s26_from_upload(uploaded):
    df = pd.read_csv(uploaded)
    required = {"learner_id", "attempt", "score"}
    if not required.issubset(df.columns):
        raise ValueError("Το CSV πρέπει να περιέχει: learner_id, attempt, score.")
    piv = df.pivot_table(index="learner_id", columns="attempt", values="score", aggfunc="mean")
    if 1 not in piv.columns or 2 not in piv.columns:
        raise ValueError("Χρειάζονται attempt=1 και attempt=2.")
    clean = piv[[1,2]].dropna()
    gain = clean[2] - clean[1]
    summary = {
        "learners": clean.shape[0],
        "attempts": df.shape[0],
        "attempt1": clean[1].mean(),
        "attempt2": clean[2].mean(),
        "mean_gain": gain.mean(),
        "median_gain": gain.median(),
        "improved": int((gain > 0).sum()),
        "unchanged": int((gain == 0).sum()),
        "declined": int((gain < 0).sum()),
        "ready": int((df["status"].astype(str).str.upper() == "READY").sum()) if "status" in df.columns else np.nan,
        "review": int((df["status"].astype(str).str.upper() == "ESCALATE").sum()) if "status" in df.columns else np.nan,
        "grade_writes": 0,
        "confidence1": df.loc[df["attempt"] == 1, "confidence"].mean() if "confidence" in df.columns else np.nan,
        "confidence2": df.loc[df["attempt"] == 2, "confidence"].mean() if "confidence" in df.columns else np.nan,
    }
    return df, clean, summary

st.markdown("""
<div class="inelso-hero">
<h1>INELSO · Smart Learning Services</h1>
<p>Streamlit demo για Service 21 και Service 26 — απλή customer εικόνα, Python analytics και τεχνική τεκμηρίωση όταν χρειάζεται.</p>
</div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.header("Ρυθμίσεις")
    mode = st.radio("Πηγή δεδομένων", ["Demo Mode", "Upload CSV", "Live Moodle Data"], index=0)
    st.caption("Demo Mode: ελεγχόμενα δεδομένα. Upload CSV: δικό σου αρχείο. Live Moodle Data: απευθείας read-only ανάγνωση από το Moodle για το Service 21.")
    st.divider()
    st.markdown("**Κατάσταση prototype:** v0.1")
    st.markdown("Moodle integration: επόμενο deployment βήμα")
    st.markdown("Official grade writes: **0**")

tab1, tab2, tab3 = st.tabs(["Service 21 · Ποιότητα αξιολόγησης", "Service 26 · Ανατροφοδότηση", "Τεχνική εικόνα"])

with tab1:
    st.title("Service 21 · Ποιότητα αξιολόγησης")
    st.write("Ποιες ερωτήσεις λειτουργούν καλά και ποιες χρειάζονται επανέλεγχο;")
    s21_table = S21_DEMO.copy()
    alpha = 0.67103
    n_attempts = 50
    live_payload = None
    if mode == "Upload CSV":
        up21 = st.file_uploader(
            "CSV Service 21 — μία γραμμή ανά προσπάθεια, μία αριθμητική/δυαδική στήλη ανά ερώτηση",
            type=["csv"], key="s21"
        )
        if up21 is not None:
            try:
                s21_table, alpha, n_attempts = s21_from_upload(up21)
                st.success("Το CSV αναλύθηκε επιτυχώς.")
            except Exception as e:
                st.error(str(e))
    elif mode == "Live Moodle Data":
        try:
            s21_table, alpha, n_attempts, live_payload = s21_from_live_moodle()
            st.success("Συνδέθηκε επιτυχώς με το Moodle σε read-only λειτουργία.")
            st.caption(
                f"Live πηγή: {live_payload.get('quiz_name','Moodle quiz')} · "
                f"CMID {live_payload.get('cmid','—')} · "
                f"Τελευταία ανάγνωση: {live_payload.get('generated_at','—')}"
            )
        except Exception as e:
            st.error(f"Live Moodle σύνδεση: {e}")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Προσπάθειες", f"{n_attempts}")
    c2.metric("Μέση επίδοση", f"{s21_table['Ποσοστό σωστών (%)'].mean():.2f}%")
    c3.metric("Εσωτερική συνέπεια", "—" if not np.isfinite(alpha) else f"{alpha*100:.2f}%")
    flagged = int((s21_table["Δείκτης διάκρισης (%)"] < 0).sum())
    c4.metric("Ερωτήσεις για έλεγχο", flagged)
    st.subheader("Ποσοστό σωστών ανά ερώτηση")
    st.bar_chart(s21_table.set_index("Ερώτηση")[["Ποσοστό σωστών (%)"]])
    st.subheader("Δείκτης διάκρισης")
    st.bar_chart(s21_table.set_index("Ερώτηση")[["Δείκτης διάκρισης (%)"]])
    bad = s21_table[s21_table["Δείκτης διάκρισης (%)"] < 0]
    if not bad.empty:
        items = ", ".join(bad["Ερώτηση"].astype(str).tolist())
        st.warning(f"Ενέργεια: επανέλεγχος των ερωτήσεων {items}, επειδή εμφανίζουν αρνητικό δείκτη διάκρισης.")
    else:
        st.success("Δεν εντοπίστηκε αρνητικός δείκτης διάκρισης.")
    with st.expander("Τεχνική τεκμηρίωση Service 21", expanded=False):
        st.write("Η ευκολία υπολογίζεται ως ποσοστό σωστών απαντήσεων. Ο δείκτης διάκρισης εδώ είναι corrected item–total correlation.")
        st.dataframe(s21_table, use_container_width=True, hide_index=True)
        st.write("Cronbach’s alpha:", "—" if not np.isfinite(alpha) else f"{alpha:.5f}")
        st.caption("Στο Live Moodle Data mode, το response matrix έρχεται read-only από το Moodle API και τα psychometric metrics υπολογίζονται ξανά μέσα στο Streamlit.")

with tab2:
    st.title("Service 26 · Ανατροφοδότηση εξάσκησης")
    st.write("Βελτιώθηκε ο εκπαιδευόμενος μετά την ανατροφοδότηση και πότε χρειάζεται ανθρώπινος έλεγχος;")
    summary = dict(S26_DEMO)
    uploaded_df = None
    clean_pairs = None
    if mode == "Upload CSV":
        up26 = st.file_uploader(
            "CSV Service 26 — απαιτούμενες στήλες: learner_id, attempt, score. Προαιρετικές: confidence, status",
            type=["csv"], key="s26"
        )
        if up26 is not None:
            try:
                uploaded_df, clean_pairs, summary = s26_from_upload(up26)
                st.success("Το CSV αναλύθηκε επιτυχώς.")
            except Exception as e:
                st.error(str(e))
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Εκπαιδευόμενοι", summary["learners"])
    c2.metric("1η προσπάθεια", f"{summary['attempt1']:.2f}")
    c3.metric("2η προσπάθεια", f"{summary['attempt2']:.2f}", delta=f"+{summary['mean_gain']:.2f}")
    c4.metric("Βελτιώθηκαν", f"{summary['improved']}/{summary['learners']}")
    before_after = pd.DataFrame(
        {"Μέση επίδοση": [summary["attempt1"], summary["attempt2"]]},
        index=["1η προσπάθεια", "2η προσπάθεια"]
    )
    st.subheader("Πριν και μετά την ανατροφοδότηση")
    st.bar_chart(before_after)
    if np.isfinite(summary.get("ready", np.nan)) and np.isfinite(summary.get("review", np.nan)):
        status_df = pd.DataFrame(
            {"Προσπάθειες": [summary["ready"], summary["review"]]},
            index=["Άμεση ανατροφοδότηση", "Ανθρώπινος έλεγχος"]
        )
        st.subheader("Αυτόματη ροή και ανθρώπινος έλεγχος")
        st.bar_chart(status_df)
    if mode == "Demo Mode":
        st.subheader("Τελικό επίπεδο μετά τη 2η προσπάθεια")
        st.bar_chart(S26_MASTERY.set_index("Επίπεδο"))
    st.markdown(
        f"""<div class="small-note"><b>Μήνυμα για τον πελάτη:</b>
        {summary['improved']} από {summary['learners']} εκπαιδευόμενους βελτιώθηκαν.
        Η μέση μεταβολή ήταν {summary['mean_gain']:.2f} μονάδες.
        Δεν έγινε καμία εγγραφή επίσημου βαθμού.</div>""",
        unsafe_allow_html=True
    )
    with st.expander("Τεχνική τεκμηρίωση Service 26", expanded=False):
        st.write("Η εφαρμογή συγκρίνει την πρώτη και τη δεύτερη προσπάθεια ανά εκπαιδευόμενο.")
        st.json({
            "mean_gain": round(float(summary["mean_gain"]), 4),
            "median_gain": round(float(summary["median_gain"]), 4),
            "improved": int(summary["improved"]),
            "unchanged": int(summary["unchanged"]),
            "declined": int(summary["declined"]),
            "ready": None if not np.isfinite(summary.get("ready", np.nan)) else int(summary["ready"]),
            "human_review": None if not np.isfinite(summary.get("review", np.nan)) else int(summary["review"]),
            "official_grade_writes": 0,
        })
        if uploaded_df is not None:
            st.dataframe(uploaded_df, use_container_width=True, hide_index=True)
        else:
            st.caption("Demo Mode: 100 controlled practice attempts. Live Moodle enrolment verification παραμένει ξεχωριστό integration layer.")

with tab3:
    st.title("Τεχνική εικόνα")
    st.write("Το Streamlit είναι πρόσθετο presentation/data-app layer και δεν αντικαθιστά το υπάρχον λειτουργικό Moodle/PHP demo.")
    st.markdown("""
**Προτεινόμενη αρχιτεκτονική**
1. Moodle / LTI για πρόσβαση και context
2. Streamlit για interactive analytics
3. Python για υπολογισμούς
4. Customer-facing KPI και charts
5. Τεχνικά στοιχεία πίσω από expanders
    """)
    st.info("Το Service 21 υποστηρίζει πλέον Demo Mode, Upload CSV και Live Moodle Data μέσω read-only API. Το Service 26 παραμένει Demo/CSV μέχρι να ενεργοποιηθεί το αντίστοιχο live endpoint.")
    with st.expander("Όρια του demo", expanded=False):
        st.write(
            "Τα δεδομένα επίδειξης είναι controlled/synthetic. "
            "Το Service 21 live Moodle integration και το Service 26 live enrolment verification "
            "παραμένουν στο υπάρχον server implementation μέχρι να ολοκληρωθεί η απευθείας σύνδεση Streamlit."
        )
