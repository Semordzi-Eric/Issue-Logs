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

PAGES = [
    "📊 Dashboard Overview",
    "📝 Log New Issue",
    "🔍 Manage Issues",
    "📧 Email Tracker",
    "📄 Generative Reports"
]

def main():
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


if __name__ == "__main__":
    main()
