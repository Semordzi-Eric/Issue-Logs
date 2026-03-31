import streamlit as st
import pandas as pd
from database.models import get_session, Issue, EmailLog, EmailResponse
from utils.helpers import generate_issue_id, predict_category

CATEGORIES = [
    "Revenue Leakage", "Failed Transactions", "Suspicious Activity",
    "Reversals", "Reprocessed", "System Errors", "Others"
]
PRIORITIES = ["Low", "Medium", "High", "Critical"]
STATUSES   = ["Open", "Investigating", "Resolved", "Escalated"]


def _navigate_to_emails(issue_id: str):
    """Deep-link to Email Tracker pre-filtered to a specific issue."""
    st.session_state.email_context_issue = issue_id
    st.session_state.nav_page = "📧 Email Tracker"
    st.rerun()


# ──────────────────────────────────────────────
# LOG NEW ISSUE
# ──────────────────────────────────────────────
def render_add_issue():
    st.title("📝 Log New Audit Issue")
    st.markdown("Use this form to track new findings or incidents.")
    st.markdown("---")

    with st.form("new_issue_form"):
        col1, col2 = st.columns(2)
        with col1:
            title = st.text_input("Issue Title*", help="A short, descriptive title")
            date  = st.date_input("Date Found*")
        with col2:
            affected_system = st.text_input(
                "Affected System / Channel*",
                help="e.g., POS, Mobile App, Core Banking"
            )
            priority = st.selectbox("Priority*", PRIORITIES, index=1)

        description = st.text_area(
            "Issue Description*",
            help="Detailed explanation of the finding", height=150
        )

        suggested_category = predict_category(description) if description else "Others"
        cat_index = CATEGORIES.index(suggested_category) if suggested_category in CATEGORIES else 6

        col3, col4 = st.columns(2)
        with col3:
            category       = st.selectbox("Category*", CATEGORIES, index=cat_index)
            transaction_id = st.text_input("Transaction ID (Optional)")
        with col4:
            amount = st.number_input("Amount Involved (Optional, GHS ₵)", min_value=0.0, step=10.0)
            status = st.selectbox("Initial Status", STATUSES, index=0)

        root_cause = st.text_input("Root Cause / Initial Hypothesis (Optional)")
        submitted  = st.form_submit_button("Log Issue", type="primary")

        if submitted:
            if not title or not description or not affected_system:
                st.error("Please fill in all required fields marked with *.")
            else:
                session = get_session()
                new_issue = Issue(
                    issue_id=generate_issue_id(),
                    date=date, title=title, description=description,
                    category=category, priority=priority,
                    affected_system=affected_system,
                    transaction_id=transaction_id if transaction_id else None,
                    amount=amount if amount > 0 else None,
                    root_cause=root_cause if root_cause else None,
                    status=status
                )
                session.add(new_issue)
                session.commit()
                iid = new_issue.issue_id
                session.close()
                st.success(f"✅ Issue **{iid}** logged successfully!")
                st.info("💡 Head to **Manage Issues** to update or track emails for this issue.")


# ──────────────────────────────────────────────
# MANAGE ISSUES  (issue CRUD + email snapshot)
# ──────────────────────────────────────────────
def render_manage_issues():
    st.title("🔍 Manage & Filter Issues")
    st.markdown(
        "View, filter, and update issues. "
        "Click **📧 Open Email Trail** on any issue to manage its communications in the Email Tracker."
    )
    st.markdown("---")

    session = get_session()
    issues  = session.query(Issue).all()

    if not issues:
        st.info("No issues found. Go to **Log New Issue** to create one.")
        session.close()
        return

    # ── Build summary table ──────────────────────
    rows = []
    for i in issues:
        emails      = session.query(EmailLog).filter_by(issue_id=i.id).all()
        email_count = len(emails)
        responded   = sum(1 for e in emails if e.response_status == "Responded")
        pending     = sum(1 for e in emails if e.response_status != "Responded")
        rows.append({
            "ID":          i.id,
            "Issue ID":    i.issue_id,
            "Date":        i.date,
            "Title":       i.title,
            "Category":    i.category,
            "Priority":    i.priority,
            "Status":      i.status,
            "Amount":      f"₵{i.amount:,.2f}" if i.amount else "-",
            "📧 Emails":   email_count,
            "✅ Responded": responded,
            "⏳ Pending":  pending,
        })
    df = pd.DataFrame(rows)

    # ── Filters ─────────────────────────────────
    st.markdown("### Filters")
    f_col1, f_col2, f_col3 = st.columns(3)
    with f_col1:
        f_status   = st.multiselect("Status",   STATUSES,   default=[])
    with f_col2:
        f_priority = st.multiselect("Priority", PRIORITIES, default=[])
    with f_col3:
        f_search   = st.text_input("Search (Title / Issue ID)")

    filtered_df = df.copy()
    if f_status:
        filtered_df = filtered_df[filtered_df["Status"].isin(f_status)]
    if f_priority:
        filtered_df = filtered_df[filtered_df["Priority"].isin(f_priority)]
    if f_search:
        s = f_search.lower()
        filtered_df = filtered_df[
            filtered_df["Issue ID"].str.lower().str.contains(s) |
            filtered_df["Title"].str.lower().str.contains(s)
        ]

    st.markdown(f"**Showing {len(filtered_df)} issue(s)**")
    st.dataframe(filtered_df.drop(columns=["ID"]), hide_index=True)

    if filtered_df.empty:
        session.close()
        return

    # ── Select issue ─────────────────────────────
    st.markdown("---")
    selected_id = st.selectbox(
        "Select Issue",
        filtered_df["Issue ID"].tolist(),
        key="manage_issue_select"
    )
    target = session.query(Issue).filter_by(issue_id=selected_id).first()

    if not target:
        session.close()
        return

    # ── Issue detail card ────────────────────────
    with st.container():
        d_col1, d_col2, d_col3, d_col4 = st.columns(4)
        d_col1.metric("Category",  target.category)
        d_col2.metric("Priority",  target.priority)
        d_col3.metric("Status",    target.status)
        emails_count = session.query(EmailLog).filter_by(issue_id=target.id).count()
        d_col4.metric("Emails Logged", emails_count)

    # ── Email Trail snapshot ─────────────────────
    issue_emails = session.query(EmailLog).filter_by(issue_id=target.id)\
                          .order_by(EmailLog.date_sent).all()

    if issue_emails:
        st.markdown("#### 📬 Email Communications Summary")
        for em in issue_emails:
            resp_count = session.query(EmailResponse).filter_by(email_log_id=em.id).count()
            status_emoji = {
                "Responded":        "✅",
                "No Response":      "⏳",
                "Follow-up Needed": "🔔"
            }.get(em.response_status, "❓")
            st.markdown(
                f"&nbsp;&nbsp;{status_emoji} **{em.subject}** → {em.recipient} "
                f"&nbsp;·&nbsp; {em.date_sent} "
                f"&nbsp;·&nbsp; {resp_count + 1} message(s) "
                f"&nbsp;·&nbsp; *{em.response_status}*",
                unsafe_allow_html=True
            )

    # ── Deep-link to Email Tracker ────────────────
    st.markdown("")
    if st.button(
        f"📧 Open Full Email Trail for {selected_id}",
        help="Opens Email Tracker pre-filtered to this issue"
    ):
        _navigate_to_emails(selected_id)

    st.markdown("---")

    # ── Update form ──────────────────────────────
    st.markdown("### ✏️ Update Issue")
    with st.form("update_issue_form"):
        u_col1, u_col2 = st.columns(2)
        with u_col1:
            new_status   = st.selectbox("Status",   STATUSES,
                                        index=STATUSES.index(target.status))
        with u_col2:
            new_priority = st.selectbox("Priority", PRIORITIES,
                                        index=PRIORITIES.index(target.priority))

        resolution = st.text_area(
            "Resolution Notes / Update Details",
            value=target.resolution_notes or ""
        )
        if st.form_submit_button("💾 Save Updates", type="primary"):
            target.status           = new_status
            target.priority         = new_priority
            target.resolution_notes = resolution
            session.commit()
            st.success(f"✅ {selected_id} updated.")
            st.rerun()

    # ── Delete ───────────────────────────────────
    st.markdown("---")
    st.markdown("### 🗑️ Delete Issue")
    st.warning("⚠️ This permanently deletes the issue and ALL linked emails and responses.")

    confirm = st.checkbox(f"I confirm: permanently delete **{selected_id}** and all its data.")
    if st.button("🗑️ Delete Issue", type="primary", disabled=not confirm):
        linked = session.query(EmailLog).filter_by(issue_id=target.id).all()
        for em in linked:
            session.query(EmailResponse).filter_by(email_log_id=em.id).delete()
            session.delete(em)
        session.delete(target)
        session.commit()
        st.success(f"Issue {selected_id} deleted.")
        st.rerun()

    session.close()
