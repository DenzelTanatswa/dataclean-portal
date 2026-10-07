import streamlit as st
import pandas as pd
import io

# Phase 2 service imports
from services.quality_score import calculate_quality_score, quality_label
from services.profiling import create_quality_profile, get_issues
from services.validation import run_all_validations, DEFAULT_RULES
from services.cleaning import clean_dataset
from services.audit import (
    save_dataset_metadata, save_cleaning_run,
    get_cleaning_history, get_audit_for_run,
    get_all_datasets, get_quality_history, get_db_summary,
)
from database.connection import test_connection, get_engine
from database.models import Base

# ==========================================
# PAGE CONFIGURATION
# ==========================================

st.set_page_config(
    page_title="DataClean Portal",
    page_icon="🧹",
    layout="wide"
)

# ==========================================
# PROFESSIONAL CSS
# ==========================================

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', Arial, sans-serif;
}

/* Sidebar branding */
section[data-testid="stSidebar"] {
    background: #0f172a;
    min-width: 220px;
}
section[data-testid="stSidebar"] * {
    color: #e2e8f0 !important;
}

/* Metric cards */
div[data-testid="metric-container"] {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 16px 20px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}
div[data-testid="metric-container"] label {
    font-size: 0.75rem !important;
    font-weight: 600 !important;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: #64748b !important;
}
div[data-testid="metric-container"] div[data-testid="stMetricValue"] {
    font-size: 2rem !important;
    font-weight: 700 !important;
    color: #0f172a !important;
}

/* Primary button */
div.stButton > button[kind="primary"] {
    background: #2563eb;
    color: #ffffff;
    border: none;
    border-radius: 8px;
    font-weight: 600;
    padding: 10px 24px;
    font-family: 'Inter', Arial, sans-serif;
}
div.stButton > button[kind="primary"]:hover {
    background: #1d4ed8;
}

/* Secondary button */
div.stButton > button {
    border-radius: 8px;
    font-family: 'Inter', Arial, sans-serif;
    font-weight: 500;
}

/* Download button */
div.stDownloadButton > button {
    background: #ffffff;
    border: 1.5px solid #2563eb;
    color: #2563eb;
    border-radius: 8px;
    font-weight: 600;
    font-family: 'Inter', Arial, sans-serif;
}
div.stDownloadButton > button:hover {
    background: #eff6ff;
}

/* Dataframe */
div[data-testid="stDataFrame"] {
    border-radius: 10px;
    overflow: hidden;
    border: 1px solid #e2e8f0;
}

/* Info / success / warning boxes */
div[data-testid="stAlert"] {
    border-radius: 10px;
}

/* Card helper class */
.dc-card {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 20px 24px;
    margin-bottom: 16px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}
.dc-page-title {
    font-size: 1.75rem;
    font-weight: 700;
    color: #0f172a;
    margin-bottom: 4px;
}
.dc-page-subtitle {
    font-size: 0.95rem;
    color: #64748b;
    margin-bottom: 24px;
}
.dc-section-title {
    font-size: 1.1rem;
    font-weight: 600;
    color: #0f172a;
    margin-bottom: 12px;
}
.dc-badge-green {
    display:inline-block;
    background:#dcfce7;color:#15803d;
    border-radius:20px;padding:3px 12px;
    font-size:0.8rem;font-weight:600;
}
.dc-badge-yellow {
    display:inline-block;
    background:#fef9c3;color:#a16207;
    border-radius:20px;padding:3px 12px;
    font-size:0.8rem;font-weight:600;
}
.dc-badge-red {
    display:inline-block;
    background:#fee2e2;color:#b91c1c;
    border-radius:20px;padding:3px 12px;
    font-size:0.8rem;font-weight:600;
}
.dc-score-big {
    font-size:3rem;font-weight:700;color:#0f172a;line-height:1;
}
.dc-welcome-center {
    text-align:center;
    padding: 60px 20px;
}
.dc-step {
    display:flex;align-items:center;gap:10px;
    padding:8px 0;font-size:0.95rem;color:#374151;
}
</style>
""", unsafe_allow_html=True)


# ==========================================
# INLINE HELPERS (thin wrappers kept for backward compat)
# ==========================================

def column_quality_label(missing_pct):
    if missing_pct == 0:
        return "🟢 Good"
    elif missing_pct <= 10:
        return "🟡 Warning"
    else:
        return "🔴 Critical"


def load_file(uploaded_file):
    """Load CSV or Excel, return (df, error_message)."""
    try:
        if uploaded_file.name.endswith(".csv"):
            df = pd.read_csv(uploaded_file)
        elif uploaded_file.name.endswith(".xlsx"):
            df = pd.read_excel(uploaded_file)
        else:
            return None, "Unsupported file format. Please upload CSV or XLSX."
        if df.empty:
            return None, "The uploaded file is empty."
        return df, None
    except Exception as e:
        return None, f"Could not read file: {e}"


def to_excel_bytes(df):
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Cleaned Data")
    return buf.getvalue()


# ==========================================
# SESSION STATE INITIALISATION
# ==========================================

if "page" not in st.session_state:
    st.session_state.page = "Dashboard"
if "df" not in st.session_state:
    st.session_state.df = None
if "cleaned_df" not in st.session_state:
    st.session_state.cleaned_df = None
if "audit_log" not in st.session_state:
    st.session_state.audit_log = []
if "filename" not in st.session_state:
    st.session_state.filename = ""
# Phase 2 additions
if "dataset_id" not in st.session_state:
    st.session_state.dataset_id = None
if "last_run_code" not in st.session_state:
    st.session_state.last_run_code = None
if "score_before" not in st.session_state:
    st.session_state.score_before = None
if "score_after" not in st.session_state:
    st.session_state.score_after = None
if "validation_rules" not in st.session_state:
    st.session_state.validation_rules = dict(DEFAULT_RULES)
if "db_ok" not in st.session_state:
    ok, _ = test_connection()
    st.session_state.db_ok = ok


# ==========================================
# DB INIT (create tables if missing)
# ==========================================

if st.session_state.db_ok:
    try:
        engine = get_engine()
        Base.metadata.create_all(engine)
    except Exception:
        st.session_state.db_ok = False


# ==========================================
# SIDEBAR
# ==========================================

with st.sidebar:
    st.markdown("""
    <div style="padding:24px 8px 16px 8px;text-align:center;">
        <div style="font-size:2rem;">🧹</div>
        <div style="font-size:1.3rem;font-weight:700;color:#f1f5f9;letter-spacing:0.02em;">DataClean</div>
        <div style="font-size:0.7rem;font-weight:600;letter-spacing:0.18em;color:#94a3b8;text-transform:uppercase;">PORTAL</div>
        <div style="margin-top:6px;font-size:0.72rem;color:#64748b;font-style:italic;">Clean Data. Better Decisions.</div>
    </div>
    <hr style="border-color:#1e293b;margin:0 0 16px 0;">
    """, unsafe_allow_html=True)

    nav_items = [
        ("🏠", "Dashboard"),
        ("📤", "Upload"),
        ("🔍", "Profile"),
        ("🧹", "Clean"),
        ("📦", "Export"),
        ("📁", "Datasets"),
        ("🕒", "History"),
        ("🗄️", "Database"),
    ]

    for icon, label in nav_items:
        active = st.session_state.page == label
        btn_style = (
            "background:#2563eb;color:#fff;border-radius:8px;"
            if active else
            "background:transparent;color:#cbd5e1;"
        )
        if st.button(
            f"{icon}  {label}",
            key=f"nav_{label}",
            use_container_width=True,
        ):
            st.session_state.page = label
            st.rerun()

    st.markdown("<div style='height:32px'></div>", unsafe_allow_html=True)

    if st.session_state.df is not None:
        st.markdown(f"""
        <div style="background:#1e293b;border-radius:8px;padding:12px 14px;font-size:0.78rem;">
            <div style="color:#94a3b8;font-weight:600;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:6px;">Active Dataset</div>
            <div style="color:#f1f5f9;font-weight:500;">{st.session_state.filename}</div>
            <div style="color:#64748b;margin-top:4px;">{st.session_state.df.shape[0]:,} rows · {st.session_state.df.shape[1]} cols</div>
        </div>
        """, unsafe_allow_html=True)

    # DB status indicator
    db_color = "#22c55e" if st.session_state.db_ok else "#ef4444"
    db_label = "PostgreSQL Connected" if st.session_state.db_ok else "PostgreSQL Offline"
    st.markdown(f"""
    <div style="margin-top:16px;padding:8px 12px;background:#1e293b;border-radius:8px;
                font-size:0.75rem;display:flex;align-items:center;gap:8px;">
        <span style="width:8px;height:8px;border-radius:50%;background:{db_color};
                     display:inline-block;"></span>
        <span style="color:#94a3b8;">{db_label}</span>
    </div>
    """, unsafe_allow_html=True)

page = st.session_state.page


# ==========================================
# PAGE: DASHBOARD
# ==========================================

if page == "Dashboard":

    if st.session_state.df is None:
        # Welcome / empty state
        st.markdown("""
        <div class="dc-welcome-center">
            <div style="font-size:3.5rem;margin-bottom:12px;">🧹</div>
            <div style="font-size:2rem;font-weight:700;color:#0f172a;margin-bottom:6px;">DataClean Portal</div>
            <div style="font-size:1rem;color:#64748b;font-style:italic;margin-bottom:28px;">Clean Data. Better Decisions.</div>
            <div style="font-size:1rem;color:#374151;max-width:480px;margin:0 auto 32px auto;line-height:1.7;">
                Upload your dataset to identify data-quality issues,
                clean your data and export a ready-to-use dataset.
            </div>
        </div>
        """, unsafe_allow_html=True)

        col_c = st.columns([1, 2, 1])[1]
        with col_c:
            if st.button("📤  Upload Dataset", type="primary", use_container_width=True):
                st.session_state.page = "Upload"
                st.rerun()
            st.markdown("""
            <div style="text-align:center;margin-top:16px;color:#94a3b8;font-size:0.85rem;">
                Supported formats: &nbsp;<strong>CSV</strong> &nbsp;•&nbsp; <strong>XLSX</strong>
            </div>
            """, unsafe_allow_html=True)

    else:
        df = st.session_state.df
        score = calculate_quality_score(df)
        icon, label, badge_cls = quality_label(score)

        st.markdown('<div class="dc-page-title">Data Quality Dashboard</div>', unsafe_allow_html=True)
        st.markdown('<div class="dc-page-subtitle">Monitor and improve the quality of your data.</div>', unsafe_allow_html=True)

        # Metric cards row
        c1, c2, c3, c4, c5 = st.columns(5)
        with c1:
            st.metric("Rows", f"{df.shape[0]:,}")
        with c2:
            st.metric("Columns", df.shape[1])
        with c3:
            st.metric("Missing Values", int(df.isnull().sum().sum()))
        with c4:
            st.metric("Duplicate Rows", int(df.duplicated().sum()))
        with c5:
            st.metric("Quality Score", f"{score} / 100")

        st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)

        left, right = st.columns([1, 2])

        with left:
            st.markdown('<div class="dc-card">', unsafe_allow_html=True)
            st.markdown('<div class="dc-section-title">Data Quality Score</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="dc-score-big">{score}</div>', unsafe_allow_html=True)
            st.markdown('<div style="color:#64748b;font-size:0.85rem;margin-bottom:12px;">out of 100</div>', unsafe_allow_html=True)
            st.markdown(f'<span class="{badge_cls}">{icon} {label}</span>', unsafe_allow_html=True)
            st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
            st.progress(score / 100)
            st.markdown('</div>', unsafe_allow_html=True)

        with right:
            st.markdown('<div class="dc-card">', unsafe_allow_html=True)
            st.markdown('<div class="dc-section-title">⚠ Data Quality Issues</div>', unsafe_allow_html=True)
            for sev, msg in get_issues(df):
                st.markdown(f'<div class="dc-step">{sev} &nbsp; {msg}</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

        # Dataset preview
        st.markdown('<div class="dc-section-title" style="margin-top:8px;">👀 Dataset Preview</div>', unsafe_allow_html=True)
        st.dataframe(df.head(10), use_container_width=True)


# ==========================================
# PAGE: UPLOAD
# ==========================================

elif page == "Upload":

    st.markdown('<div class="dc-page-title">📤 Upload Dataset</div>', unsafe_allow_html=True)
    st.markdown('<div class="dc-page-subtitle">Upload a CSV or Excel file to get started.</div>', unsafe_allow_html=True)

    uploaded_file = st.file_uploader(
        "Choose a file",
        type=["csv", "xlsx"],
        label_visibility="collapsed"
    )

    if uploaded_file is not None:
        df, err = load_file(uploaded_file)
        if err:
            st.error(f"❌ {err}")
        else:
            st.session_state.df = df
            st.session_state.cleaned_df = None
            st.session_state.audit_log = []
            st.session_state.filename = uploaded_file.name
            st.session_state.dataset_id = None
            st.session_state.last_run_code = None
            st.session_state.score_before = calculate_quality_score(df)
            st.session_state.score_after = None

            # Save metadata to PostgreSQL if available
            if st.session_state.db_ok:
                try:
                    ftype = "csv" if uploaded_file.name.endswith(".csv") else "xlsx"
                    did = save_dataset_metadata(
                        filename=uploaded_file.name,
                        file_type=ftype,
                        row_count=df.shape[0],
                        col_count=df.shape[1],
                        quality_score=st.session_state.score_before,
                    )
                    st.session_state.dataset_id = did
                    st.success(f"✅ Successfully uploaded **{uploaded_file.name}** — {df.shape[0]:,} rows, {df.shape[1]} columns. Saved to database (ID: {did}).")
                except Exception as e:
                    st.warning(f"⚠️ Uploaded successfully but could not save to database: {e}")
                    st.success(f"✅ Successfully uploaded **{uploaded_file.name}** — {df.shape[0]:,} rows, {df.shape[1]} columns.")
            else:
                st.success(f"✅ Successfully uploaded **{uploaded_file.name}** — {df.shape[0]:,} rows, {df.shape[1]} columns.")

            st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
            if st.button("Go to Dashboard →", type="primary"):
                st.session_state.page = "Dashboard"
                st.rerun()


# ==========================================
# PAGE: PROFILE
# ==========================================

elif page == "Profile":

    st.markdown('<div class="dc-page-title">🔍 Dataset Profile</div>', unsafe_allow_html=True)
    st.markdown('<div class="dc-page-subtitle">Analyze dataset structure and identify quality problems.</div>', unsafe_allow_html=True)

    if st.session_state.df is None:
        st.info("No dataset loaded. Please upload a file first.")
        if st.button("📤 Go to Upload"):
            st.session_state.page = "Upload"
            st.rerun()
    else:
        df = st.session_state.df

        # Overview metrics
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("Rows", f"{df.shape[0]:,}")
        with c2:
            st.metric("Columns", df.shape[1])
        with c3:
            st.metric("Missing Values", int(df.isnull().sum().sum()))
        with c4:
            st.metric("Duplicate Rows", int(df.duplicated().sum()))

        st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

        # Tabs: Profile | Validation | Statistics
        tab1, tab2, tab3 = st.tabs(["Column Quality", "Validation Rules", "Numerical Statistics"])

        with tab1:
            profile_df = create_quality_profile(df)
            st.dataframe(profile_df, use_container_width=True, hide_index=True)

        with tab2:
            st.markdown('<div class="dc-section-title">Validation Rule Configuration</div>', unsafe_allow_html=True)
            col_r1, col_r2 = st.columns(2)
            with col_r1:
                st.session_state.validation_rules["age_min"] = st.number_input(
                    "Age minimum", value=int(st.session_state.validation_rules["age_min"]), min_value=0)
                st.session_state.validation_rules["missing_threshold_pct"] = st.number_input(
                    "Missing value threshold (%)", value=float(st.session_state.validation_rules["missing_threshold_pct"]), min_value=0.0, max_value=100.0)
            with col_r2:
                st.session_state.validation_rules["age_max"] = st.number_input(
                    "Age maximum", value=int(st.session_state.validation_rules["age_max"]), min_value=0)
                st.session_state.validation_rules["duplicate_threshold_pct"] = st.number_input(
                    "Duplicate threshold (%)", value=float(st.session_state.validation_rules["duplicate_threshold_pct"]), min_value=0.0, max_value=100.0)

            st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
            if st.button("Run Validation", type="primary"):
                val_df = run_all_validations(df, st.session_state.validation_rules)
                st.session_state.validation_results = val_df

            if "validation_results" in st.session_state and st.session_state.validation_results is not None:
                st.markdown('<div class="dc-section-title" style="margin-top:16px;">Validation Results</div>', unsafe_allow_html=True)
                st.dataframe(st.session_state.validation_results, use_container_width=True, hide_index=True)
                passed = (st.session_state.validation_results["Status"] == "🟢 Passed").sum()
                failed = (st.session_state.validation_results["Status"] == "🔴 Failed").sum()
                warned = (st.session_state.validation_results["Status"] == "🟡 Warning").sum()
                vc1, vc2, vc3 = st.columns(3)
                with vc1:
                    st.metric("🟢 Passed", passed)
                with vc2:
                    st.metric("🟡 Warning", warned)
                with vc3:
                    st.metric("🔴 Failed", failed)

        with tab3:
            numeric_cols = df.select_dtypes(include=["number"]).columns
            if len(numeric_cols) > 0:
                stats = df[numeric_cols].describe().T[["count", "mean", "min", "max"]]
                stats.columns = ["Count", "Average", "Minimum", "Maximum"]
                st.dataframe(stats.round(2), use_container_width=True)
            else:
                st.info("No numerical columns found in this dataset.")


# ==========================================
# PAGE: CLEAN
# ==========================================

elif page == "Clean":

    st.markdown('<div class="dc-page-title">🧹 Clean Dataset</div>', unsafe_allow_html=True)
    st.markdown('<div class="dc-page-subtitle">Select cleaning operations and apply them to your dataset.</div>', unsafe_allow_html=True)

    if st.session_state.df is None:
        st.info("No dataset loaded. Please upload a file first.")
        if st.button("📤 Go to Upload"):
            st.session_state.page = "Upload"
            st.rerun()
    else:
        df = st.session_state.df

        # Cleaning option cards
        col_a, col_b = st.columns(2)

        with col_a:
            st.markdown('<div class="dc-card"><div class="dc-section-title">🗂 Duplicate Management</div>', unsafe_allow_html=True)
            remove_duplicates = st.checkbox("Remove duplicate rows")
            st.markdown('</div>', unsafe_allow_html=True)

            st.markdown('<div class="dc-card"><div class="dc-section-title">📍 Location Standardization</div>', unsafe_allow_html=True)
            standardize_cities = st.checkbox(
                "Standardize city names",
                disabled="City" not in df.columns,
                help="Requires a 'City' column" if "City" not in df.columns else ""
            )
            st.markdown('</div>', unsafe_allow_html=True)

        with col_b:
            st.markdown('<div class="dc-card"><div class="dc-section-title">🔤 Text Cleaning</div>', unsafe_allow_html=True)
            trim_spaces = st.checkbox("Remove unnecessary spaces")
            standardize_text = st.checkbox("Standardize text capitalization")
            st.markdown('</div>', unsafe_allow_html=True)

            st.markdown('<div class="dc-card"><div class="dc-section-title">❓ Missing Data & Validation</div>', unsafe_allow_html=True)
            fill_missing = st.checkbox("Fill missing values")
            fix_invalid_age = st.checkbox(
                "Flag invalid ages",
                disabled="Age" not in df.columns,
                help="Requires an 'Age' column" if "Age" not in df.columns else ""
            )
            st.markdown('</div>', unsafe_allow_html=True)

        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

        if st.button("🧹  Clean Dataset", type="primary"):

            options = {
                "remove_duplicates":  remove_duplicates,
                "trim_spaces":        trim_spaces,
                "standardize_text":   standardize_text,
                "standardize_cities": standardize_cities,
                "fill_missing":       fill_missing,
                "fix_invalid_age":    fix_invalid_age,
            }
            selected_ops = [k for k, v in options.items() if v]

            if not selected_ops:
                st.warning("Please select at least one cleaning operation.")
            else:
                score_before = calculate_quality_score(df)
                progress_bar = st.progress(0)
                status_box = st.empty()
                total_ops = len(selected_ops)
                completed = [0]

                # Wrap clean_dataset to show progress
                # We run it fully then show steps
                cleaned_df, audit_log = clean_dataset(df, options)

                for entry in audit_log:
                    completed[0] += 1
                    progress_bar.progress(completed[0] / total_ops)
                    status_box.markdown(
                        f'<div class="dc-step">✅ &nbsp; {entry["Operation"]}</div>',
                        unsafe_allow_html=True
                    )

                progress_bar.progress(1.0)
                status_box.empty()

                score_after = calculate_quality_score(cleaned_df)
                st.session_state.cleaned_df = cleaned_df
                st.session_state.audit_log = audit_log
                st.session_state.score_before = score_before
                st.session_state.score_after = score_after

                final_rows = len(cleaned_df)
                rows_removed = len(df) - final_rows
                issues_resolved = sum(r["Changes"] for r in audit_log)

                # Run validation on cleaned data
                val_df = run_all_validations(cleaned_df, st.session_state.validation_rules)
                st.session_state.validation_results = val_df

                # Save to DB
                run_code = None
                if st.session_state.db_ok and st.session_state.dataset_id:
                    try:
                        run_code = save_cleaning_run(
                            dataset_id=st.session_state.dataset_id,
                            original_rows=len(df),
                            cleaned_rows=final_rows,
                            rows_removed=rows_removed,
                            score_before=score_before,
                            score_after=score_after,
                            audit_log=audit_log,
                            quality_checks_df=val_df,
                        )
                        st.session_state.last_run_code = run_code
                    except Exception as e:
                        st.warning(f"⚠️ Could not save run to database: {e}")

                st.success("✅ Dataset cleaned successfully!" + (f"  |  Run ID: **{run_code}**" if run_code else ""))

                # Quality score comparison
                sq1, sq2, sq3 = st.columns(3)
                with sq1:
                    st.metric("Score Before", f"{score_before} / 100")
                with sq2:
                    st.metric("Score After", f"{score_after} / 100")
                with sq3:
                    delta = score_after - score_before
                    st.metric("Improvement", f"+{delta}" if delta >= 0 else str(delta))

                # Result cards
                r1, r2, r3, r4 = st.columns(4)
                with r1:
                    st.metric("Original Rows", len(df))
                with r2:
                    st.metric("Cleaned Rows", final_rows)
                with r3:
                    st.metric("Rows Removed", rows_removed)
                with r4:
                    st.metric("Issues Resolved", issues_resolved)

                st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

                # Audit log
                st.markdown('<div class="dc-section-title">📝 Cleaning Audit Log</div>', unsafe_allow_html=True)
                audit_df = pd.DataFrame(audit_log)
                if not audit_df.empty:
                    st.dataframe(audit_df, use_container_width=True, hide_index=True)

                # Validation results
                st.markdown('<div class="dc-section-title" style="margin-top:20px;">✅ Post-Clean Validation</div>', unsafe_allow_html=True)
                st.dataframe(val_df, use_container_width=True, hide_index=True)

                # Before / After
                st.markdown('<div class="dc-section-title" style="margin-top:20px;">🔄 Before vs After</div>', unsafe_allow_html=True)
                b_col, a_col = st.columns(2)
                with b_col:
                    st.markdown("**Before Cleaning**")
                    st.dataframe(df.head(10), use_container_width=True)
                with a_col:
                    st.markdown("**After Cleaning**")
                    st.dataframe(cleaned_df.head(10), use_container_width=True)

                st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
                if st.button("Go to Export →", type="primary"):
                    st.session_state.page = "Export"
                    st.rerun()


# ==========================================
# PAGE: EXPORT
# ==========================================

elif page == "Export":

    st.markdown('<div class="dc-page-title">📦 Export Dataset</div>', unsafe_allow_html=True)
    st.markdown('<div class="dc-page-subtitle">Download your cleaned dataset.</div>', unsafe_allow_html=True)

    if st.session_state.cleaned_df is None:
        st.info("No cleaned dataset available. Please run the Clean step first.")
        if st.button("🧹 Go to Clean"):
            st.session_state.page = "Clean"
            st.rerun()
    else:
        cleaned_df = st.session_state.cleaned_df

        st.markdown('<div class="dc-card">', unsafe_allow_html=True)
        st.markdown("✅ **Your cleaned dataset is ready.**")
        st.markdown(f"""
        | | |
        |---|---|
        | **Dataset** | cleaned_dataset |
        | **Rows** | {cleaned_df.shape[0]:,} |
        | **Columns** | {cleaned_df.shape[1]} |
        """)
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

        d1, d2 = st.columns(2)
        with d1:
            csv_data = cleaned_df.to_csv(index=False)
            st.download_button(
                label="📥 Download CSV",
                data=csv_data,
                file_name="cleaned_dataset.csv",
                mime="text/csv",
                use_container_width=True
            )
        with d2:
            st.download_button(
                label="📊 Download Excel",
                data=to_excel_bytes(cleaned_df),
                file_name="cleaned_dataset.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

        st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
        st.markdown('<div class="dc-section-title">Preview</div>', unsafe_allow_html=True)
        st.dataframe(cleaned_df.head(10), use_container_width=True)


# ==========================================
# PAGE: DATASETS
# ==========================================

elif page == "Datasets":

    st.markdown('<div class="dc-page-title">📁 Datasets</div>', unsafe_allow_html=True)
    st.markdown('<div class="dc-page-subtitle">All datasets processed through DataClean Portal.</div>', unsafe_allow_html=True)

    if not st.session_state.db_ok:
        st.warning("⚠️ PostgreSQL is not connected. Dataset history is unavailable.")
    else:
        try:
            datasets = get_all_datasets()
            if not datasets:
                st.info("No datasets have been uploaded yet. Upload a file to get started.")
            else:
                ds_df = pd.DataFrame(datasets)
                st.dataframe(ds_df, use_container_width=True, hide_index=True)
                st.markdown(f"**{len(datasets)} dataset(s) on record.**")
        except Exception as e:
            st.error(f"Could not load datasets: {e}")


# ==========================================
# PAGE: HISTORY
# ==========================================

elif page == "History":

    st.markdown('<div class="dc-page-title">🕒 Cleaning History</div>', unsafe_allow_html=True)
    st.markdown('<div class="dc-page-subtitle">All cleaning runs and quality score progression.</div>', unsafe_allow_html=True)

    if not st.session_state.db_ok:
        st.warning("⚠️ PostgreSQL is not connected. Cleaning history is unavailable.")
    else:
        try:
            history = get_cleaning_history()
            if not history:
                st.info("No cleaning runs recorded yet. Clean a dataset to get started.")
            else:
                hist_df = pd.DataFrame(history)
                st.dataframe(hist_df, use_container_width=True, hide_index=True)

                st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)

                # Quality score chart
                st.markdown('<div class="dc-section-title">📈 Quality Score Over Time</div>', unsafe_allow_html=True)
                quality_hist = get_quality_history()
                if quality_hist:
                    chart_df = pd.DataFrame(quality_hist)
                    chart_df = chart_df.rename(columns={"run_code": "Run", "score": "Quality Score"})
                    chart_df = chart_df.set_index("Run")[["Quality Score"]]
                    st.line_chart(chart_df, use_container_width=True)

                # Drill into a specific run
                st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
                st.markdown('<div class="dc-section-title">🔎 Inspect Run Audit Log</div>', unsafe_allow_html=True)
                run_codes = [r["Run ID"] for r in history]
                selected_run = st.selectbox("Select a Run ID", run_codes)
                if selected_run:
                    audit_entries = get_audit_for_run(selected_run)
                    if audit_entries:
                        st.dataframe(pd.DataFrame(audit_entries), use_container_width=True, hide_index=True)
                    else:
                        st.info("No audit entries found for this run.")
        except Exception as e:
            st.error(f"Could not load history: {e}")


# ==========================================
# PAGE: DATABASE
# ==========================================

elif page == "Database":

    st.markdown('<div class="dc-page-title">🗄️ Database</div>', unsafe_allow_html=True)
    st.markdown('<div class="dc-page-subtitle">PostgreSQL connection status and stored record counts.</div>', unsafe_allow_html=True)

    # Connection status card
    if st.session_state.db_ok:
        st.success("✅ PostgreSQL is connected and tables are initialised.")
    else:
        st.error("❌ PostgreSQL is not connected. Check your .env credentials and ensure PostgreSQL is running.")
        st.markdown("""
        **Troubleshooting checklist:**
        - Is PostgreSQL running locally?
        - Is the database `dataclean` created?
        - Are the credentials in `.env` correct?
        - Is port 5432 open?
        """)

    if st.button("🔄 Retry Connection"):
        ok, err = test_connection()
        st.session_state.db_ok = ok
        if ok:
            try:
                engine = get_engine()
                Base.metadata.create_all(engine)
            except Exception:
                pass
            st.success("✅ Connected successfully.")
        else:
            st.error(f"❌ Connection failed: {err}")
        st.rerun()

    if st.session_state.db_ok:
        st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
        st.markdown('<div class="dc-section-title">Record Counts</div>', unsafe_allow_html=True)
        try:
            summary = get_db_summary()
            m1, m2, m3, m4 = st.columns(4)
            with m1:
                st.metric("Datasets", summary["datasets"])
            with m2:
                st.metric("Cleaning Runs", summary["cleaning_runs"])
            with m3:
                st.metric("Quality Checks", summary["quality_checks"])
            with m4:
                st.metric("Audit Entries", summary["audit_entries"])
        except Exception as e:
            st.error(f"Could not load summary: {e}")

        st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
        st.markdown('<div class="dc-section-title">Table Reference</div>', unsafe_allow_html=True)
        st.markdown("""
        | Table | Purpose |
        |---|---|
        | `datasets` | One row per uploaded file — stores filename, shape, quality score, status |
        | `cleaning_runs` | One row per cleaning execution — links to dataset, stores before/after metrics |
        | `cleaning_audit` | One row per operation within a run — e.g. "Spaces removed: 4" |
        | `quality_checks` | One row per validation rule per run — stores pass/warn/fail status |
        | `dataset_versions` | Tracks each version of a dataset as cleaning progresses |
        """)
