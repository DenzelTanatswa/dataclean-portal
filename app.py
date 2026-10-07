import streamlit as st
import pandas as pd
import io
import base64
from pathlib import Path

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

LOGO_PATH = Path("assets/dataclean_logo.png")

def load_logo_b64():
    """Return base64-encoded logo string, or None if file missing."""
    try:
        if LOGO_PATH.exists():
            return base64.b64encode(LOGO_PATH.read_bytes()).decode()
    except Exception:
        pass
    return None

# Use logo as page icon if available, else emoji fallback
_logo_b64 = load_logo_b64()
_page_icon = LOGO_PATH if LOGO_PATH.exists() else "🧹"

st.set_page_config(
    page_title="DataClean Portal",
    page_icon=_page_icon,
    layout="wide"
)

# ==========================================
# THEME DEFINITIONS
# ==========================================

THEMES = {
    "Light": {
        "--bg":           "#F7F9FC",
        "--surface":      "#FFFFFF",
        "--card":         "#FFFFFF",
        "--sidebar-bg":   "#0F172A",
        "--sidebar-text": "#E2E8F0",
        "--sidebar-muted":"#94A3B8",
        "--sidebar-dim":  "#475569",
        "--sidebar-hover":"#1E293B",
        "--nav-active":   "#2563EB",
        "--text":         "#0F172A",
        "--text-muted":   "#64748B",
        "--border":       "#E2E8F0",
        "--primary":      "#2563EB",
        "--primary-hover":"#1D4ED8",
        "--success":      "#16A34A",
        "--warning":      "#F59E0B",
        "--danger":       "#DC2626",
        "--metric-text":  "#0F172A",
        "--metric-label": "#64748B",
        "--card-shadow":  "0 1px 4px rgba(0,0,0,0.07)",
        "--footer-border":"#E2E8F0",
        "--footer-text":  "#94A3B8",
    },
    "Dark": {
        "--bg":           "#0B1120",
        "--surface":      "#111827",
        "--card":         "#111827",
        "--sidebar-bg":   "#060D1A",
        "--sidebar-text": "#F8FAFC",
        "--sidebar-muted":"#94A3B8",
        "--sidebar-dim":  "#475569",
        "--sidebar-hover":"#1E293B",
        "--nav-active":   "#3B82F6",
        "--text":         "#F8FAFC",
        "--text-muted":   "#94A3B8",
        "--border":       "#334155",
        "--primary":      "#3B82F6",
        "--primary-hover":"#2563EB",
        "--success":      "#22C55E",
        "--warning":      "#F59E0B",
        "--danger":       "#EF4444",
        "--metric-text":  "#F8FAFC",
        "--metric-label": "#94A3B8",
        "--card-shadow":  "0 1px 4px rgba(0,0,0,0.4)",
        "--footer-border":"#1E293B",
        "--footer-text":  "#475569",
    },
}

def apply_theme(theme_name: str):
    """Inject CSS variables + full component styles for the chosen theme."""
    t = THEMES.get(theme_name, THEMES["Light"])
    vars_css = "\n".join(f"    {k}: {v};" for k, v in t.items())
    st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

:root {{
{vars_css}
}}

html, body, [class*="css"] {{
    font-family: 'Inter', 'Segoe UI', Arial, sans-serif;
    background-color: var(--bg) !important;
    color: var(--text) !important;
}}

/* ── Sidebar ─────────────────────────────── */
section[data-testid="stSidebar"] {{
    background: var(--sidebar-bg) !important;
    border-right: 1px solid #1E293B;
}}
section[data-testid="stSidebar"] * {{
    color: var(--sidebar-text) !important;
    font-family: 'Inter', 'Segoe UI', Arial, sans-serif !important;
}}

/* ── Main area background ────────────────── */
.main .block-container {{
    background: var(--bg);
    padding-top: 2rem;
}}

/* ── Metric cards ────────────────────────── */
div[data-testid="metric-container"] {{
    background: var(--card) !important;
    border: 1px solid var(--border) !important;
    border-radius: 12px !important;
    padding: 16px 20px !important;
    box-shadow: var(--card-shadow) !important;
}}
div[data-testid="metric-container"] label {{
    font-size: 0.72rem !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.06em !important;
    color: var(--metric-label) !important;
}}
div[data-testid="metric-container"] div[data-testid="stMetricValue"] {{
    font-size: 1.9rem !important;
    font-weight: 700 !important;
    color: var(--metric-text) !important;
}}

/* ── Primary button ──────────────────────── */
div.stButton > button[kind="primary"] {{
    background: var(--primary) !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    padding: 10px 24px !important;
    font-family: 'Inter', Arial, sans-serif !important;
    transition: background 0.15s !important;
}}
div.stButton > button[kind="primary"]:hover {{
    background: var(--primary-hover) !important;
}}

/* ── Secondary button ────────────────────── */
div.stButton > button {{
    border-radius: 8px !important;
    font-family: 'Inter', Arial, sans-serif !important;
    font-weight: 500 !important;
    border: 1px solid var(--border) !important;
    background: var(--card) !important;
    color: var(--text) !important;
    transition: background 0.15s !important;
}}
div.stButton > button:hover {{
    background: var(--surface) !important;
    border-color: var(--primary) !important;
}}

/* ── Download button ─────────────────────── */
div.stDownloadButton > button {{
    background: var(--card) !important;
    border: 1.5px solid var(--primary) !important;
    color: var(--primary) !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    font-family: 'Inter', Arial, sans-serif !important;
}}
div.stDownloadButton > button:hover {{
    background: var(--surface) !important;
}}

/* ── Dataframe ───────────────────────────── */
div[data-testid="stDataFrame"] {{
    border-radius: 10px !important;
    overflow: hidden !important;
    border: 1px solid var(--border) !important;
}}

/* ── Alerts ──────────────────────────────── */
div[data-testid="stAlert"] {{
    border-radius: 10px !important;
}}

/* ── Tabs ────────────────────────────────── */
div[data-testid="stTabs"] button {{
    color: var(--text-muted) !important;
    font-family: 'Inter', Arial, sans-serif !important;
}}
div[data-testid="stTabs"] button[aria-selected="true"] {{
    color: var(--primary) !important;
    border-bottom-color: var(--primary) !important;
}}

/* ── Expander ────────────────────────────── */
div[data-testid="stExpander"] {{
    border: 1px solid var(--border) !important;
    border-radius: 8px !important;
    background: var(--card) !important;
}}

/* ── Selectbox / number input ────────────── */
div[data-testid="stSelectbox"] > div,
div[data-testid="stNumberInput"] > div {{
    background: var(--card) !important;
    border-color: var(--border) !important;
    color: var(--text) !important;
    border-radius: 8px !important;
}}

/* ── Checkbox label ──────────────────────── */
div[data-testid="stCheckbox"] label {{
    color: var(--text) !important;
}}

/* ── Progress bar ────────────────────────── */
div[data-testid="stProgressBar"] > div {{
    border-radius: 99px !important;
    background: var(--border) !important;
}}
div[data-testid="stProgressBar"] > div > div {{
    border-radius: 99px !important;
    background: var(--primary) !important;
}}

/* ── Custom component classes ────────────── */
.dc-card {{
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 20px 24px;
    margin-bottom: 16px;
    box-shadow: var(--card-shadow);
}}
.dc-page-title {{
    font-size: 1.75rem;
    font-weight: 700;
    color: var(--text);
    margin-bottom: 4px;
}}
.dc-page-subtitle {{
    font-size: 0.95rem;
    color: var(--text-muted);
    margin-bottom: 24px;
}}
.dc-section-title {{
    font-size: 1.05rem;
    font-weight: 600;
    color: var(--text);
    margin-bottom: 12px;
}}
.dc-score-big {{
    font-size: 3rem;
    font-weight: 700;
    color: var(--text);
    line-height: 1;
}}
.dc-welcome-center {{
    text-align: center;
    padding: 60px 20px;
}}
.dc-step {{
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 0;
    font-size: 0.95rem;
    color: var(--text);
}}
.dc-badge-green {{
    display: inline-block;
    background: #dcfce7;
    color: #15803d;
    border-radius: 20px;
    padding: 3px 12px;
    font-size: 0.8rem;
    font-weight: 600;
}}
.dc-badge-yellow {{
    display: inline-block;
    background: #fef9c3;
    color: #a16207;
    border-radius: 20px;
    padding: 3px 12px;
    font-size: 0.8rem;
    font-weight: 600;
}}
.dc-badge-red {{
    display: inline-block;
    background: #fee2e2;
    color: #b91c1c;
    border-radius: 20px;
    padding: 3px 12px;
    font-size: 0.8rem;
    font-weight: 600;
}}
.dc-social-btn {{
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 5px 12px;
    border-radius: 6px;
    border: 1px solid #334155;
    background: #1e293b;
    color: #cbd5e1 !important;
    font-size: 0.75rem;
    font-weight: 500;
    text-decoration: none;
    transition: background 0.15s, border-color 0.15s;
    font-family: 'Inter', Arial, sans-serif;
}}
.dc-social-btn:hover {{
    background: var(--primary);
    border-color: var(--primary);
    color: #ffffff !important;
    text-decoration: none;
}}
.dc-footer {{
    margin-top: 48px;
    padding: 20px 0 8px 0;
    border-top: 1px solid var(--footer-border);
    text-align: center;
    font-size: 0.8rem;
    color: var(--footer-text);
    font-family: 'Inter', Arial, sans-serif;
}}
.dc-footer a {{
    color: var(--primary);
    text-decoration: none;
    font-weight: 500;
}}
.dc-footer a:hover {{
    text-decoration: underline;
}}
/* Nav button active highlight via Streamlit button override */
div[data-testid="stSidebar"] div.stButton > button {{
    background: transparent !important;
    border: none !important;
    color: var(--sidebar-text) !important;
    text-align: left !important;
    padding: 9px 14px !important;
    border-radius: 8px !important;
    font-size: 0.88rem !important;
    font-weight: 500 !important;
    width: 100% !important;
    transition: background 0.12s !important;
}}
div[data-testid="stSidebar"] div.stButton > button:hover {{
    background: var(--sidebar-hover) !important;
    border: none !important;
}}
</style>
""", unsafe_allow_html=True)


# ==========================================
# INLINE HELPERS
# ==========================================

def column_quality_label(missing_pct):
    if missing_pct == 0:
        return "🟢 Good"
    elif missing_pct <= 10:
        return "🟡 Warning"
    else:
        return "🔴 Critical"


def load_file(uploaded_file):
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
if "theme" not in st.session_state:
    st.session_state.theme = "Light"

# Apply theme CSS (runs every page load)
apply_theme(st.session_state.theme)

# ==========================================
# DB INIT
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

    # ── Logo / branding ───────────────────
    logo_b64 = load_logo_b64()
    if logo_b64:
        st.markdown(
            f"""
            <div style="padding:20px 12px 10px 12px;text-align:center;">
                <img src="data:image/png;base64,{logo_b64}"
                     style="max-width:150px;width:100%;height:auto;
                            border-radius:8px;margin-bottom:8px;">
                <div style="font-size:0.7rem;color:var(--sidebar-muted);
                            font-style:italic;letter-spacing:0.02em;">
                    Clean Data. Better Decisions.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            """
            <div style="padding:24px 8px 16px 8px;text-align:center;">
                <div style="font-size:2rem;">🧹</div>
                <div style="font-size:1.3rem;font-weight:700;color:#f1f5f9;
                            letter-spacing:0.02em;">DataClean</div>
                <div style="font-size:0.7rem;font-weight:600;letter-spacing:0.18em;
                            color:#94a3b8;text-transform:uppercase;">PORTAL</div>
                <div style="margin-top:6px;font-size:0.72rem;color:#64748b;
                            font-style:italic;">Clean Data. Better Decisions.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown(
        "<hr style='border-color:#1E293B;margin:4px 0 12px 0;'>",
        unsafe_allow_html=True,
    )

    # ── Navigation label ──────────────────
    st.markdown(
        "<div style='font-size:0.65rem;font-weight:700;letter-spacing:0.12em;"
        "color:#475569;text-transform:uppercase;padding:0 4px 6px 4px;'>"
        "NAVIGATION</div>",
        unsafe_allow_html=True,
    )

    # ── Nav items ─────────────────────────
    nav_items = [
        ("▦", "Dashboard"),
        ("⇧", "Upload"),
        ("◉", "Profile"),
        ("✦", "Clean"),
        ("↓", "Export"),
        ("▤", "Datasets"),
        ("↺", "History"),
        ("⬡", "Database"),
    ]

    for icon, label in nav_items:
        active = st.session_state.page == label
        # Active item gets a blue pill background via inline style injected
        # around the button using a wrapper div
        if active:
            st.markdown(
                f"""
                <div style="background:var(--nav-active);border-radius:8px;
                            margin:1px 0;">
                """,
                unsafe_allow_html=True,
            )
        if st.button(
            f"{icon}  {label}",
            key=f"nav_{label}",
            use_container_width=True,
        ):
            st.session_state.page = label
            st.rerun()
        if active:
            st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    # ── Active dataset chip ───────────────
    if st.session_state.df is not None:
        st.markdown(
            f"""
            <div style="background:#1e293b;border-radius:8px;
                        padding:10px 14px;font-size:0.78rem;margin:4px 0 8px 0;">
                <div style="color:#94a3b8;font-weight:600;text-transform:uppercase;
                            letter-spacing:0.05em;margin-bottom:4px;font-size:0.68rem;">
                    Active Dataset
                </div>
                <div style="color:#f1f5f9;font-weight:500;
                            white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">
                    {st.session_state.filename}
                </div>
                <div style="color:#64748b;margin-top:3px;font-size:0.75rem;">
                    {st.session_state.df.shape[0]:,} rows
                    &nbsp;·&nbsp;
                    {st.session_state.df.shape[1]} cols
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # ── DB status dot ─────────────────────
    db_color = "#22c55e" if st.session_state.db_ok else "#ef4444"
    db_label = "PostgreSQL Connected" if st.session_state.db_ok else "PostgreSQL Offline"
    st.markdown(
        f"""
        <div style="padding:7px 12px;background:#1e293b;border-radius:8px;
                    font-size:0.74rem;display:flex;align-items:center;gap:8px;
                    margin-bottom:12px;">
            <span style="width:7px;height:7px;border-radius:50%;
                         background:{db_color};display:inline-block;
                         flex-shrink:0;"></span>
            <span style="color:#94a3b8;">{db_label}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Theme switcher ────────────────────
    st.markdown(
        "<hr style='border-color:#1E293B;margin:4px 0 10px 0;'>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div style='font-size:0.65rem;font-weight:700;letter-spacing:0.12em;"
        "color:#475569;text-transform:uppercase;padding:0 4px 8px 4px;'>"
        "APPEARANCE</div>",
        unsafe_allow_html=True,
    )
    t_col1, t_col2 = st.columns(2)
    with t_col1:
        light_active = st.session_state.theme == "Light"
        if st.button(
            "☀️  Light",
            key="theme_light",
            use_container_width=True,
            type="primary" if light_active else "secondary",
        ):
            st.session_state.theme = "Light"
            st.rerun()
    with t_col2:
        dark_active = st.session_state.theme == "Dark"
        if st.button(
            "🌙  Dark",
            key="theme_dark",
            use_container_width=True,
            type="primary" if dark_active else "secondary",
        ):
            st.session_state.theme = "Dark"
            st.rerun()

    # ── Developer footer ──────────────────
    st.markdown(
        "<hr style='border-color:#1E293B;margin:12px 0 10px 0;'>",
        unsafe_allow_html=True,
    )
    st.markdown(
        """
        <div style="text-align:center;padding:0 4px 8px 4px;">
            <div style="font-size:0.65rem;color:#475569;text-transform:uppercase;
                        letter-spacing:0.1em;margin-bottom:5px;">Developed by</div>
            <div style="font-size:0.85rem;font-weight:600;color:#e2e8f0;
                        margin-bottom:10px;">Denzel Chidzikwe</div>
            <div style="display:flex;justify-content:center;gap:8px;flex-wrap:wrap;">
                <a href="https://github.com/DenzelTanatswa" target="_blank"
                   class="dc-social-btn">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor">
                        <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205
                        11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235
                        -3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23
                        -1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845
                        1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765
                        -1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385
                        1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3
                        1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56
                        3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23
                        1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375
                        .81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225
                        .69.825.57A12.02 12.02 0 0 0 24 12c0-6.63-5.37-12-12-12z"/>
                    </svg>
                    GitHub
                </a>
                <a href="https://www.linkedin.com/in/denzel-chidzikwe-0a6965288"
                   target="_blank" class="dc-social-btn">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor">
                        <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037
                        -1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9
                        h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0
                        4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0
                        0 1-2.063-2.065 2.064 2.064 0 1 1 2.063 2.065zm1.782
                        13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774
                        0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24
                        23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/>
                    </svg>
                    LinkedIn
                </a>
            </div>
            <div style="margin-top:10px;font-size:0.66rem;color:#334155;">
                DataClean Portal
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.expander("About the Developer"):
        st.markdown(
            """
            <div style="font-size:0.82rem;color:#cbd5e1;line-height:1.7;">
                <div style="font-weight:600;color:#f1f5f9;margin-bottom:2px;">
                    Denzel Chidzikwe
                </div>
                <div style="color:#94a3b8;font-size:0.75rem;margin-bottom:10px;">
                    Data Analytics &nbsp;|&nbsp; Big Data
                    &nbsp;|&nbsp; Business Intelligence
                </div>
                <div style="color:#94a3b8;font-size:0.78rem;margin-bottom:12px;">
                    Built DataClean Portal as an end-to-end data quality,
                    cleansing, validation and analytics project.
                </div>
                <div style="display:flex;gap:8px;flex-wrap:wrap;">
                    <a href="https://github.com/DenzelTanatswa"
                       target="_blank" class="dc-social-btn">&#128279; GitHub</a>
                    <a href="https://www.linkedin.com/in/denzel-chidzikwe-0a6965288"
                       target="_blank" class="dc-social-btn">&#128279; LinkedIn</a>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

page = st.session_state.page


# ==========================================
# MAIN PAGE FOOTER (every page)
# ==========================================

st.markdown("""
<div class="dc-footer">
    <strong>DataClean Portal</strong> &nbsp;&bull;&nbsp; Clean Data. Better Decisions.<br>
    <span style="margin-top:4px;display:inline-block;">
        Developed by <strong>Denzel Chidzikwe</strong>
        &nbsp;&bull;&nbsp;
        <a href="https://github.com/DenzelTanatswa" target="_blank">GitHub</a>
        &nbsp;&bull;&nbsp;
        <a href="https://www.linkedin.com/in/denzel-chidzikwe-0a6965288"
           target="_blank">LinkedIn</a>
    </span>
</div>
""", unsafe_allow_html=True)


# ==========================================
# PAGE: DASHBOARD
# ==========================================

if page == "Dashboard":

    if st.session_state.df is None:
        # Welcome / empty state with logo
        logo_b64 = load_logo_b64()
        if logo_b64:
            st.markdown(
                f"""
                <div class="dc-welcome-center">
                    <img src="data:image/png;base64,{logo_b64}"
                         style="max-width:180px;width:100%;height:auto;
                                border-radius:12px;margin-bottom:20px;">
                    <div style="font-size:1.1rem;color:var(--text-muted);
                                font-style:italic;margin-bottom:12px;">
                        Clean Data. Better Decisions.
                    </div>
                    <div style="font-size:1rem;color:var(--text-muted);
                                max-width:480px;margin:0 auto 32px auto;
                                line-height:1.7;">
                        Transform messy datasets into clean, validated
                        and analysis-ready data.
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.markdown("""
            <div class="dc-welcome-center">
                <div style="font-size:3.5rem;margin-bottom:12px;">🧹</div>
                <div style="font-size:2rem;font-weight:700;color:var(--text);
                            margin-bottom:6px;">DataClean Portal</div>
                <div style="font-size:1rem;color:var(--text-muted);
                            font-style:italic;margin-bottom:28px;">
                    Clean Data. Better Decisions.
                </div>
                <div style="font-size:1rem;color:var(--text-muted);
                            max-width:480px;margin:0 auto 32px auto;line-height:1.7;">
                    Transform messy datasets into clean, validated
                    and analysis-ready data.
                </div>
            </div>
            """, unsafe_allow_html=True)

        col_c = st.columns([1, 2, 1])[1]
        with col_c:
            if st.button("⇧  Upload Dataset", type="primary",
                         use_container_width=True):
                st.session_state.page = "Upload"
                st.rerun()
            st.markdown("""
            <div style="text-align:center;margin-top:14px;
                        color:var(--text-muted);font-size:0.85rem;">
                Supported formats: &nbsp;<strong>CSV</strong>
                &nbsp;•&nbsp; <strong>XLSX</strong>
            </div>
            """, unsafe_allow_html=True)

    else:
        df = st.session_state.df
        score = calculate_quality_score(df)
        icon, label, badge_cls = quality_label(score)

        st.markdown('<div class="dc-page-title">Data Quality Dashboard</div>',
                    unsafe_allow_html=True)
        st.markdown(
            '<div class="dc-page-subtitle">'
            'Monitor and improve the quality of your data.'
            '</div>',
            unsafe_allow_html=True,
        )

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
            st.markdown('<div class="dc-section-title">Data Quality Score</div>',
                        unsafe_allow_html=True)
            st.markdown(f'<div class="dc-score-big">{score}</div>',
                        unsafe_allow_html=True)
            st.markdown(
                '<div style="color:var(--text-muted);font-size:0.85rem;'
                'margin-bottom:12px;">out of 100</div>',
                unsafe_allow_html=True,
            )
            st.markdown(f'<span class="{badge_cls}">{icon} {label}</span>',
                        unsafe_allow_html=True)
            st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
            st.progress(score / 100)
            st.markdown('</div>', unsafe_allow_html=True)

        with right:
            st.markdown('<div class="dc-card">', unsafe_allow_html=True)
            st.markdown(
                '<div class="dc-section-title">⚠ Data Quality Issues</div>',
                unsafe_allow_html=True,
            )
            for sev, msg in get_issues(df):
                st.markdown(
                    f'<div class="dc-step">{sev} &nbsp; {msg}</div>',
                    unsafe_allow_html=True,
                )
            st.markdown('</div>', unsafe_allow_html=True)

        st.markdown(
            '<div class="dc-section-title" style="margin-top:8px;">'
            '👀 Dataset Preview</div>',
            unsafe_allow_html=True,
        )
        st.dataframe(df.head(10), use_container_width=True)


# ==========================================
# PAGE: UPLOAD
# ==========================================

elif page == "Upload":

    st.markdown('<div class="dc-page-title">⇧ Upload Dataset</div>',
                unsafe_allow_html=True)
    st.markdown(
        '<div class="dc-page-subtitle">'
        'Upload a CSV or Excel file to get started.'
        '</div>',
        unsafe_allow_html=True,
    )

    uploaded_file = st.file_uploader(
        "Choose a file", type=["csv", "xlsx"], label_visibility="collapsed"
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
                    st.success(
                        f"✅ Uploaded **{uploaded_file.name}** — "
                        f"{df.shape[0]:,} rows, {df.shape[1]} columns. "
                        f"Saved to database (ID: {did})."
                    )
                except Exception as e:
                    st.warning(f"⚠️ Uploaded but could not save to database: {e}")
                    st.success(
                        f"✅ Uploaded **{uploaded_file.name}** — "
                        f"{df.shape[0]:,} rows, {df.shape[1]} columns."
                    )
            else:
                st.success(
                    f"✅ Uploaded **{uploaded_file.name}** — "
                    f"{df.shape[0]:,} rows, {df.shape[1]} columns."
                )

            st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
            if st.button("Go to Dashboard →", type="primary"):
                st.session_state.page = "Dashboard"
                st.rerun()


# ==========================================
# PAGE: PROFILE
# ==========================================

elif page == "Profile":

    st.markdown('<div class="dc-page-title">◉ Dataset Profile</div>',
                unsafe_allow_html=True)
    st.markdown(
        '<div class="dc-page-subtitle">'
        'Analyze dataset structure and identify quality problems.'
        '</div>',
        unsafe_allow_html=True,
    )

    if st.session_state.df is None:
        st.info("No dataset loaded. Please upload a file first.")
        if st.button("⇧ Go to Upload"):
            st.session_state.page = "Upload"
            st.rerun()
    else:
        df = st.session_state.df

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

        tab1, tab2, tab3 = st.tabs(
            ["Column Quality", "Validation Rules", "Numerical Statistics"]
        )

        with tab1:
            profile_df = create_quality_profile(df)
            st.dataframe(profile_df, use_container_width=True, hide_index=True)

        with tab2:
            st.markdown(
                '<div class="dc-section-title">Validation Rule Configuration</div>',
                unsafe_allow_html=True,
            )
            col_r1, col_r2 = st.columns(2)
            with col_r1:
                st.session_state.validation_rules["age_min"] = st.number_input(
                    "Age minimum",
                    value=int(st.session_state.validation_rules["age_min"]),
                    min_value=0,
                )
                st.session_state.validation_rules["missing_threshold_pct"] = (
                    st.number_input(
                        "Missing value threshold (%)",
                        value=float(
                            st.session_state.validation_rules["missing_threshold_pct"]
                        ),
                        min_value=0.0,
                        max_value=100.0,
                    )
                )
            with col_r2:
                st.session_state.validation_rules["age_max"] = st.number_input(
                    "Age maximum",
                    value=int(st.session_state.validation_rules["age_max"]),
                    min_value=0,
                )
                st.session_state.validation_rules["duplicate_threshold_pct"] = (
                    st.number_input(
                        "Duplicate threshold (%)",
                        value=float(
                            st.session_state.validation_rules["duplicate_threshold_pct"]
                        ),
                        min_value=0.0,
                        max_value=100.0,
                    )
                )

            st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
            if st.button("Run Validation", type="primary"):
                val_df = run_all_validations(df, st.session_state.validation_rules)
                st.session_state.validation_results = val_df

            if (
                "validation_results" in st.session_state
                and st.session_state.validation_results is not None
            ):
                st.markdown(
                    '<div class="dc-section-title" style="margin-top:16px;">'
                    'Validation Results</div>',
                    unsafe_allow_html=True,
                )
                st.dataframe(
                    st.session_state.validation_results,
                    use_container_width=True,
                    hide_index=True,
                )
                passed = (
                    st.session_state.validation_results["Status"] == "🟢 Passed"
                ).sum()
                failed = (
                    st.session_state.validation_results["Status"] == "🔴 Failed"
                ).sum()
                warned = (
                    st.session_state.validation_results["Status"] == "🟡 Warning"
                ).sum()
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

    st.markdown('<div class="dc-page-title">✦ Clean Dataset</div>',
                unsafe_allow_html=True)
    st.markdown(
        '<div class="dc-page-subtitle">'
        'Select cleaning operations and apply them to your dataset.'
        '</div>',
        unsafe_allow_html=True,
    )

    if st.session_state.df is None:
        st.info("No dataset loaded. Please upload a file first.")
        if st.button("⇧ Go to Upload"):
            st.session_state.page = "Upload"
            st.rerun()
    else:
        df = st.session_state.df
        col_a, col_b = st.columns(2)

        with col_a:
            st.markdown(
                '<div class="dc-card">'
                '<div class="dc-section-title">🗂 Duplicate Management</div>',
                unsafe_allow_html=True,
            )
            remove_duplicates = st.checkbox("Remove duplicate rows")
            st.markdown('</div>', unsafe_allow_html=True)

            st.markdown(
                '<div class="dc-card">'
                '<div class="dc-section-title">📍 Location Standardization</div>',
                unsafe_allow_html=True,
            )
            standardize_cities = st.checkbox(
                "Standardize city names",
                disabled="City" not in df.columns,
                help="Requires a 'City' column" if "City" not in df.columns else "",
            )
            st.markdown('</div>', unsafe_allow_html=True)

        with col_b:
            st.markdown(
                '<div class="dc-card">'
                '<div class="dc-section-title">🔤 Text Cleaning</div>',
                unsafe_allow_html=True,
            )
            trim_spaces = st.checkbox("Remove unnecessary spaces")
            standardize_text = st.checkbox("Standardize text capitalization")
            st.markdown('</div>', unsafe_allow_html=True)

            st.markdown(
                '<div class="dc-card">'
                '<div class="dc-section-title">❓ Missing Data & Validation</div>',
                unsafe_allow_html=True,
            )
            fill_missing = st.checkbox("Fill missing values")
            fix_invalid_age = st.checkbox(
                "Flag invalid ages",
                disabled="Age" not in df.columns,
                help="Requires an 'Age' column" if "Age" not in df.columns else "",
            )
            st.markdown('</div>', unsafe_allow_html=True)

        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

        if st.button("✦  Clean Dataset", type="primary"):
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
                completed = [0]

                cleaned_df, audit_log = clean_dataset(df, options)

                for entry in audit_log:
                    completed[0] += 1
                    progress_bar.progress(completed[0] / len(audit_log))
                    status_box.markdown(
                        f'<div class="dc-step">✅ &nbsp; {entry["Operation"]}</div>',
                        unsafe_allow_html=True,
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

                val_df = run_all_validations(
                    cleaned_df, st.session_state.validation_rules
                )
                st.session_state.validation_results = val_df

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

                run_label = f"  |  Run ID: **{run_code}**" if run_code else ""
                st.success(f"✅ Dataset cleaned successfully!{run_label}")

                sq1, sq2, sq3 = st.columns(3)
                with sq1:
                    st.metric("Score Before", f"{score_before} / 100")
                with sq2:
                    st.metric("Score After", f"{score_after} / 100")
                with sq3:
                    delta = score_after - score_before
                    st.metric("Improvement", f"+{delta}" if delta >= 0 else str(delta))

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

                st.markdown(
                    '<div class="dc-section-title">📝 Cleaning Audit Log</div>',
                    unsafe_allow_html=True,
                )
                audit_df = pd.DataFrame(audit_log)
                if not audit_df.empty:
                    st.dataframe(audit_df, use_container_width=True, hide_index=True)

                st.markdown(
                    '<div class="dc-section-title" style="margin-top:20px;">'
                    '✅ Post-Clean Validation</div>',
                    unsafe_allow_html=True,
                )
                st.dataframe(val_df, use_container_width=True, hide_index=True)

                st.markdown(
                    '<div class="dc-section-title" style="margin-top:20px;">'
                    '🔄 Before vs After</div>',
                    unsafe_allow_html=True,
                )
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

    st.markdown('<div class="dc-page-title">↓ Export Dataset</div>',
                unsafe_allow_html=True)
    st.markdown(
        '<div class="dc-page-subtitle">Download your cleaned dataset.</div>',
        unsafe_allow_html=True,
    )

    if st.session_state.cleaned_df is None:
        st.info("No cleaned dataset available. Please run the Clean step first.")
        if st.button("✦ Go to Clean"):
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
            st.download_button(
                label="📥 Download CSV",
                data=cleaned_df.to_csv(index=False),
                file_name="cleaned_dataset.csv",
                mime="text/csv",
                use_container_width=True,
            )
        with d2:
            st.download_button(
                label="📊 Download Excel",
                data=to_excel_bytes(cleaned_df),
                file_name="cleaned_dataset.xlsx",
                mime=(
                    "application/vnd.openxmlformats-officedocument"
                    ".spreadsheetml.sheet"
                ),
                use_container_width=True,
            )

        st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
        st.markdown('<div class="dc-section-title">Preview</div>',
                    unsafe_allow_html=True)
        st.dataframe(cleaned_df.head(10), use_container_width=True)


# ==========================================
# PAGE: DATASETS
# ==========================================

elif page == "Datasets":

    st.markdown('<div class="dc-page-title">▤ Datasets</div>',
                unsafe_allow_html=True)
    st.markdown(
        '<div class="dc-page-subtitle">'
        'All datasets processed through DataClean Portal.'
        '</div>',
        unsafe_allow_html=True,
    )

    if not st.session_state.db_ok:
        st.warning("⚠️ PostgreSQL is not connected. Dataset history is unavailable.")
    else:
        try:
            datasets = get_all_datasets()
            if not datasets:
                st.info("No datasets uploaded yet. Upload a file to get started.")
            else:
                st.dataframe(
                    pd.DataFrame(datasets), use_container_width=True, hide_index=True
                )
                st.markdown(f"**{len(datasets)} dataset(s) on record.**")
        except Exception as e:
            st.error(f"Could not load datasets: {e}")


# ==========================================
# PAGE: HISTORY
# ==========================================

elif page == "History":

    st.markdown('<div class="dc-page-title">↺ Cleaning History</div>',
                unsafe_allow_html=True)
    st.markdown(
        '<div class="dc-page-subtitle">'
        'All cleaning runs and quality score progression.'
        '</div>',
        unsafe_allow_html=True,
    )

    if not st.session_state.db_ok:
        st.warning("⚠️ PostgreSQL is not connected. Cleaning history is unavailable.")
    else:
        try:
            history = get_cleaning_history()
            if not history:
                st.info("No cleaning runs recorded yet.")
            else:
                st.dataframe(
                    pd.DataFrame(history), use_container_width=True, hide_index=True
                )

                st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)
                st.markdown(
                    '<div class="dc-section-title">📈 Quality Score Over Time</div>',
                    unsafe_allow_html=True,
                )
                quality_hist = get_quality_history()
                if quality_hist:
                    chart_df = pd.DataFrame(quality_hist)
                    chart_df = chart_df.rename(
                        columns={"run_code": "Run", "score": "Quality Score"}
                    )
                    st.line_chart(
                        chart_df.set_index("Run")[["Quality Score"]],
                        use_container_width=True,
                    )

                st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
                st.markdown(
                    '<div class="dc-section-title">🔎 Inspect Run Audit Log</div>',
                    unsafe_allow_html=True,
                )
                run_codes = [r["Run ID"] for r in history]
                selected_run = st.selectbox("Select a Run ID", run_codes)
                if selected_run:
                    audit_entries = get_audit_for_run(selected_run)
                    if audit_entries:
                        st.dataframe(
                            pd.DataFrame(audit_entries),
                            use_container_width=True,
                            hide_index=True,
                        )
                    else:
                        st.info("No audit entries found for this run.")
        except Exception as e:
            st.error(f"Could not load history: {e}")


# ==========================================
# PAGE: DATABASE
# ==========================================

elif page == "Database":

    st.markdown('<div class="dc-page-title">⬡ Database</div>',
                unsafe_allow_html=True)
    st.markdown(
        '<div class="dc-page-subtitle">'
        'PostgreSQL connection status and stored record counts.'
        '</div>',
        unsafe_allow_html=True,
    )

    if st.session_state.db_ok:
        st.success("✅ PostgreSQL is connected and tables are initialised.")
    else:
        st.error(
            "❌ PostgreSQL is not connected. "
            "Check your .env credentials and ensure PostgreSQL is running."
        )
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
                Base.metadata.create_all(get_engine())
            except Exception:
                pass
            st.success("✅ Connected successfully.")
        else:
            st.error(f"❌ Connection failed: {err}")
        st.rerun()

    if st.session_state.db_ok:
        st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
        st.markdown('<div class="dc-section-title">Record Counts</div>',
                    unsafe_allow_html=True)
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
        st.markdown('<div class="dc-section-title">Table Reference</div>',
                    unsafe_allow_html=True)
        st.markdown("""
        | Table | Purpose |
        |---|---|
        | `datasets` | One row per uploaded file — filename, shape, quality score, status |
        | `cleaning_runs` | One row per cleaning execution — before/after metrics |
        | `cleaning_audit` | One row per operation within a run |
        | `quality_checks` | One row per validation rule per run |
        | `dataset_versions` | Tracks each version as cleaning progresses |
        """)
