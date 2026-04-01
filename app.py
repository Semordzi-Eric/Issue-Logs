import streamlit as st
from database.models import init_db
from utils.styling import apply_custom_css

# Initialize Database
init_db()

# ── Must be first Streamlit call ──
st.set_page_config(
    page_title="Audit & Revenue Assurance Tracker",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

apply_custom_css()

from modules.dashboard import render_dashboard
from modules.issues import render_add_issue, render_manage_issues
from modules.emails import render_email_tracker
from modules.reports import render_reports
from modules.settings import render_settings

PAGES = [
    "📊 Dashboard Overview",
    "📝 Log New Issue",
    "🔍 Manage Issues",
    "📧 Email Tracker",
    "📄 Generative Reports",
    "⚙️ Settings & Sync"
]

from database.sheets_sync import get_sheets_sync
from database.models import reload_from_sheets_data, get_setting

def main():
    # ── Bootstrap Sync from Google Sheets (Primary Database Logic) ──
    # Check Secrets, Session, and DB for Sheet ID
    gs_id = None
    try:
        if "gs_sheet_id" in st.secrets:
            gs_id = st.secrets["gs_sheet_id"]
    except: pass
    
    if not gs_id:
        gs_id = get_setting("gs_sheet_id")
    if not gs_id:
        gs_id = st.session_state.get("gs_sheet_id")

    if gs_id:
        if "gs_bootstrapped" not in st.session_state:
            with st.spinner("🔄 Bootstrapping from Google Sheets..."):
                try:
                    sync = get_sheets_sync()
                    data = sync.pull_all_data()
                    if data:
                        reload_from_sheets_data(data)
                        st.session_state.gs_bootstrapped = True
                        st.toast("✅ Synced with Cloud Database", icon="☁️")
                except Exception as e:
                    st.error(f"⚠️ Bootstrap Sync Failed: {e}")

    # ── Support programmatic navigation via session state ──
    if "nav_page" not in st.session_state:
        st.session_state.nav_page = PAGES[0]

    with st.sidebar:
        st.markdown("## 🛡️ Audit Hub v1.0")
        st.markdown("---")

        # Sync radio to session state so external buttons can drive navigation
        current_index = PAGES.index(st.session_state.nav_page) \
            if st.session_state.nav_page in PAGES else 0

        choice = st.radio(
            "Navigation",
            PAGES,
            index=current_index,
            key="sidebar_nav"
        )

        # Keep session state in sync with sidebar clicks
        if choice != st.session_state.nav_page:
            st.session_state.nav_page = choice
            st.rerun()

        st.markdown("---")
        st.caption("Log issues, track emails, and auto-generate executive summary reports.")

    # ── Routing ──
    page = st.session_state.nav_page
    if page == "📊 Dashboard Overview":
        render_dashboard()
    elif page == "📝 Log New Issue":
        render_add_issue()
    elif page == "🔍 Manage Issues":
        render_manage_issues()
    elif page == "📧 Email Tracker":
        render_email_tracker()
    elif page == "📄 Generative Reports":
        render_reports()
    elif page == "⚙️ Settings & Sync":
        render_settings()


if __name__ == "__main__":
    main()
