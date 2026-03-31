import streamlit as st
import datetime
import pandas as pd
from database.models import get_session, Issue, EmailLog, EmailResponse
from utils.helpers import generate_issue_id, predict_category
from utils.styling import render_status_badge

CATEGORIES = [
    "Revenue Leakage", "Failed Transactions", "Suspicious Activity",
    "Reversals", "Reprocessed", "System Errors", "Others"
]

PRIORITIES = ["Low", "Medium", "High", "Critical"]
STATUSES   = ["Open", "Investigating", "Resolved", "Escalated"]


# ──────────────────────────────────────────────
# HELPER — render chat-style mail thread
# ──────────────────────────────────────────────
def _thread_html(email: EmailLog, responses: list) -> str:
    html = f"""
    <div style="border-left:3px solid #2196F3; padding:10px 14px; margin-bottom:12px;
                background:rgba(33,150,243,0.08); border-radius:0 8px 8px 0;">
        <div style="display:flex; justify-content:space-between; margin-bottom:4px;">
            <span style="font-weight:700; font-size:0.82rem; color:#2196F3;">
                📤 SENT &nbsp;→ {email.recipient}
            </span>
            <span style="font-size:0.78rem; color:#9BA3B5;">{email.date_sent}</span>
        </div>
        <div style="font-size:0.84rem; color:#C8CBD6;"><b>Subject:</b> {email.subject}</div>
        <div style="font-size:0.84rem; color:#E8EAF0; margin-top:6px; line-height:1.5;">
            {email.email_summary}
        </div>
    </div>"""
    for r in responses:
        bc = "#2196F3" if r.direction == "Sent" else "#4CAF50"
        bg = "rgba(33,150,243,0.07)" if r.direction == "Sent" else "rgba(76,175,80,0.07)"
        lbl = f"📤 SENT → {r.from_to}" if r.direction == "Sent" else f"📥 RECEIVED ← {r.from_to}"
        html += f"""
        <div style="border-left:3px solid {bc}; padding:10px 14px; margin-bottom:12px;
                    background:{bg}; border-radius:0 8px 8px 0;">
            <div style="display:flex; justify-content:space-between; margin-bottom:4px;">
                <span style="font-weight:700; font-size:0.82rem; color:{bc};">{lbl}</span>
                <span style="font-size:0.78rem; color:#9BA3B5;">{r.date}</span>
            </div>
            <div style="font-size:0.84rem; color:#E8EAF0; line-height:1.5;">{r.summary}</div>
        </div>"""
    return html


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
            affected_system = st.text_input("Affected System / Channel*",
                                            help="e.g., POS, Mobile App, Core Banking")
            priority = st.selectbox("Priority*", PRIORITIES, index=1)

        description = st.text_area("Issue Description*",
                                   help="Detailed explanation of the finding", height=150)

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

        submitted = st.form_submit_button("Log Issue", type="primary")

        if submitted:
            if not title or not description or not affected_system:
                st.error("Please fill in all required fields marked with *.")
            else:
                session = get_session()
                new_issue = Issue(
                    issue_id=generate_issue_id(),
                    date=date,
                    title=title,
                    description=description,
                    category=category,
                    priority=priority,
                    affected_system=affected_system,
                    transaction_id=transaction_id if transaction_id else None,
                    amount=amount if amount > 0 else None,
                    root_cause=root_cause if root_cause else None,
                    status=status
                )
                session.add(new_issue)
                session.commit()
                st.success(f"✅ Issue **{new_issue.issue_id}** logged successfully!")
                session.close()


# ──────────────────────────────────────────────
# MANAGE ISSUES  (with embedded email trail)
# ──────────────────────────────────────────────
def render_manage_issues():
    st.title("🔍 Manage & Filter Issues")

    session = get_session()
    issues = session.query(Issue).all()

    if not issues:
        st.info("No issues found. Go to 'Add Issue' to create one.")
        session.close()
        return

    # ── Build DataFrame ──────────────────────────
    data = []
    for i in issues:
        email_count = session.query(EmailLog).filter_by(issue_id=i.id).count()
        data.append({
            "ID":       i.id,
            "Issue ID": i.issue_id,
            "Date":     i.date,
            "Title":    i.title,
            "Category": i.category,
            "Priority": i.priority,
            "Status":   i.status,
            "Amount":   f"₵{i.amount:,.2f}" if i.amount else "-",
            "Emails":   email_count,
        })
    df = pd.DataFrame(data)

    # ── Filters ─────────────────────────────────
    st.markdown("### Filters")
    f_col1, f_col2, f_col3 = st.columns(3)
    with f_col1:
        f_status   = st.multiselect("Status", STATUSES, default=[])
    with f_col2:
        f_priority = st.multiselect("Priority", PRIORITIES, default=[])
    with f_col3:
        f_search   = st.text_input("Search (Title / Issue ID)")

    filtered_df = df.copy()
    if f_status:
        filtered_df = filtered_df[filtered_df['Status'].isin(f_status)]
    if f_priority:
        filtered_df = filtered_df[filtered_df['Priority'].isin(f_priority)]
    if f_search:
        srch = f_search.lower()
        filtered_df = filtered_df[
            (filtered_df['Issue ID'].str.lower().str.contains(srch)) |
            (filtered_df['Title'].str.lower().str.contains(srch))
        ]

    st.markdown(f"**Showing {len(filtered_df)} issue(s)**")
    disp_df = filtered_df.drop(columns=['ID'])
    st.dataframe(disp_df, hide_index=True)

    if filtered_df.empty:
        session.close()
        return

    # ── Select Issue ─────────────────────────────
    st.markdown("---")
    selected_issue_id = st.selectbox(
        "Select Issue to work with",
        filtered_df['Issue ID'].tolist(),
        key="main_issue_select"
    )
    target_issue = session.query(Issue).filter_by(issue_id=selected_issue_id).first()

    if not target_issue:
        session.close()
        return

    # ── TABS per issue ────────────────────────────
    tab_update, tab_emails, tab_log_email, tab_log_response = st.tabs([
        "✏️  Update Issue",
        "🧵  Email Trail",
        "📤  Log Email",
        "📥  Log Response",
    ])

    # ════════════════════════════════════════
    # TAB 1 — Update Issue
    # ════════════════════════════════════════
    with tab_update:
        with st.form("update_issue_form"):
            u_col1, u_col2 = st.columns(2)
            with u_col1:
                new_status   = st.selectbox("Status", STATUSES,
                                            index=STATUSES.index(target_issue.status))
            with u_col2:
                new_priority = st.selectbox("Priority", PRIORITIES,
                                            index=PRIORITIES.index(target_issue.priority))

            resolution = st.text_area("Resolution Notes / Update Details",
                                      value=target_issue.resolution_notes or "")
            upd_submitted = st.form_submit_button("💾 Save Updates", type="primary")
            if upd_submitted:
                target_issue.status           = new_status
                target_issue.priority         = new_priority
                target_issue.resolution_notes = resolution
                session.commit()
                st.success(f"✅ {target_issue.issue_id} updated successfully!")
                st.rerun()

    # ════════════════════════════════════════
    # TAB 2 — Email Trail (read-only view)
    # ════════════════════════════════════════
    with tab_emails:
        emails = session.query(EmailLog).filter_by(issue_id=target_issue.id)\
                        .order_by(EmailLog.date_sent).all()

        if not emails:
            st.info("No emails logged for this issue yet. Use the **📤 Log Email** tab to add one.")
        else:
            st.markdown(f"**{len(emails)} email thread(s) for {selected_issue_id}**")
            for email in emails:
                responses = session.query(EmailResponse)\
                                   .filter_by(email_log_id=email.id)\
                                   .order_by(EmailResponse.date).all()
                total_msgs = len(responses) + 1
                status_col = {
                    "Responded":        "#4CAF50",
                    "No Response":      "#F57C00",
                    "Follow-up Needed": "#2196F3"
                }.get(email.response_status, "#9BA3B5")

                exp_label = (
                    f"📧 {email.subject}  ·  To: {email.recipient}"
                    f"  ·  {total_msgs} message(s)"
                    f"  ·  [{email.response_status}]"
                )
                with st.expander(exp_label, expanded=(len(emails) == 1)):
                    st.markdown(_thread_html(email, responses), unsafe_allow_html=True)

    # ════════════════════════════════════════
    # TAB 3 — Log a new outgoing email
    # ════════════════════════════════════════
    with tab_log_email:
        st.markdown(f"Logging email for **{selected_issue_id} — {target_issue.title}**")
        with st.form("inline_email_form"):
            e_col1, e_col2 = st.columns(2)
            with e_col1:
                date_sent  = st.date_input("Date Sent*",
                                           value=datetime.datetime.utcnow().date())
                recipient  = st.text_input("Recipient (To)*")
            with e_col2:
                subject        = st.text_input("Subject*")
                follow_up_date = st.date_input("Follow-up Date (Optional)", value=None)

            email_summary   = st.text_area("Email Summary*",
                                           help="Key points only — not the full text", height=110)
            response_status = st.selectbox("Initial Response Status",
                                           ["No Response", "Responded", "Follow-up Needed"])

            email_submitted = st.form_submit_button("📤 Log Email", type="primary")
            if email_submitted:
                if not recipient or not subject or not email_summary:
                    st.error("Please fill in Recipient, Subject, and Summary.")
                else:
                    new_email = EmailLog(
                        issue_id=target_issue.id,
                        date_sent=date_sent,
                        recipient=recipient,
                        subject=subject,
                        email_summary=email_summary,
                        response_status=response_status,
                        follow_up_date=follow_up_date if follow_up_date else None
                    )
                    session.add(new_email)
                    session.commit()
                    st.success(f"✅ Email logged for **{selected_issue_id}**.")
                    st.rerun()

    # ════════════════════════════════════════
    # TAB 4 — Log a response to an email
    # ════════════════════════════════════════
    with tab_log_response:
        emails_for_issue = session.query(EmailLog).filter_by(issue_id=target_issue.id).all()

        if not emails_for_issue:
            st.info("No emails on this issue yet. Log one first in the **📤 Log Email** tab.")
        else:
            email_map = {}
            for e in emails_for_issue:
                label = f"{e.subject}  →  {e.recipient}  ({e.date_sent})"
                email_map[label] = e.id

            with st.form("inline_response_form"):
                selected_email_label = st.selectbox("Select Email Thread*", list(email_map.keys()))
                r_col1, r_col2 = st.columns(2)
                with r_col1:
                    resp_date = st.date_input("Response Date*",
                                              value=datetime.datetime.utcnow().date())
                    direction = st.selectbox("Direction*", ["Received", "Sent"],
                                            help="'Received' = they replied. 'Sent' = your follow-up.")
                with r_col2:
                    from_to    = st.text_input("From (if Received) / To (if Sent)*")
                    new_status = st.selectbox("Update Thread Status",
                                              ["No Response", "Responded", "Follow-up Needed"])

                resp_summary = st.text_area("Response Summary*", height=110)
                resp_submitted = st.form_submit_button("📥 Log Response", type="primary")

                if resp_submitted:
                    if not from_to or not resp_summary:
                        st.error("Please fill in From/To and Response Summary.")
                    else:
                        eid = email_map[selected_email_label]
                        session.add(EmailResponse(
                            email_log_id=eid,
                            date=resp_date,
                            direction=direction,
                            from_to=from_to,
                            summary=resp_summary
                        ))
                        parent = session.query(EmailLog).filter_by(id=eid).first()
                        if parent:
                            parent.response_status = new_status
                        session.commit()
                        st.success("✅ Response logged.")
                        st.rerun()

    # ── Delete Section ───────────────────────────
    st.markdown("---")
    st.markdown("### 🗑️ Delete an Issue")
    st.warning("⚠️ Deleting an issue will also remove all linked emails and responses. This cannot be undone.")

    confirm_delete = st.checkbox(
        f"I confirm I want to permanently delete **{selected_issue_id}** and all its data."
    )
    if st.button("🗑️ Delete Issue", type="primary", disabled=not confirm_delete):
        del_target = session.query(Issue).filter_by(issue_id=selected_issue_id).first()
        if del_target:
            linked_emails = session.query(EmailLog).filter_by(issue_id=del_target.id).all()
            for em in linked_emails:
                session.query(EmailResponse).filter_by(email_log_id=em.id).delete()
                session.delete(em)
            session.delete(del_target)
            session.commit()
            st.success(f"Issue {selected_issue_id} and all its data have been deleted.")
            st.rerun()

    session.close()
