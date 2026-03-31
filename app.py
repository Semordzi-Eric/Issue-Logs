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

# Apply dark mode styles
apply_custom_css()

# Import modules
from modules.dashboard import render_dashboard
from modules.issues import render_add_issue, render_manage_issues
from modules.emails import render_email_tracker
from modules.reports import render_reports


def main():
    with st.sidebar:
        st.markdown("## 🛡️ Audit Hub v1.0")
        st.markdown("---")

        # Navigation
        choice = st.radio("Navigation", [
            "📊 Dashboard Overview",
            "📝 Log New Issue",
            "🔍 Manage Issues",
            "📧 Email Tracker",
            "📄 Generative Reports"
        ])

        st.markdown("---")
        st.caption("Log issues, track emails, and auto-generate executive summary reports.")

    # Routing
    if choice == "📊 Dashboard Overview":
        render_dashboard()
    elif choice == "📝 Log New Issue":
        render_add_issue()
    elif choice == "🔍 Manage Issues":
        render_manage_issues()
    elif choice == "📧 Email Tracker":
        render_email_tracker()
    elif choice == "📄 Generative Reports":
        render_reports()


if __name__ == "__main__":
    main()
