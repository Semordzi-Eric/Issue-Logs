import streamlit as st
import datetime
import pandas as pd
from database.models import get_session, Issue, EmailLog, EmailResponse

# ──────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────
def _direction_icon(direction: str) -> str:
    return "📤 Sent" if direction == "Sent" else "📥 Received"

def _direction_color(direction: str) -> str:
    return "#2196F3" if direction == "Sent" else "#4CAF50"

def _build_thread_html(email: EmailLog, responses: list) -> str:
    """Renders a chat-style mail trail as HTML."""
    html = ""

    # Original email (always "Sent" — you logged it)
    html += f"""
    <div style="border-left: 3px solid #2196F3; padding: 10px 14px; margin-bottom: 12px;
                background: rgba(33,150,243,0.08); border-radius: 0 8px 8px 0;">
        <div style="display:flex; justify-content:space-between; margin-bottom:4px;">
            <span style="font-weight:700; font-size:0.82rem; color:#2196F3;">📤 SENT &nbsp;→ {email.recipient}</span>
            <span style="font-size:0.78rem; color:#9BA3B5;">{email.date_sent}</span>
        </div>
        <div style="font-size:0.85rem; color:#C8CBD6; margin-top:2px;">
            <b>Subject:</b> {email.subject}
        </div>
        <div style="font-size:0.84rem; color:#E8EAF0; margin-top:6px; line-height:1.5;">
            {email.email_summary}
        </div>
    </div>
    """

    for r in responses:
        border_col = "#2196F3" if r.direction == "Sent" else "#4CAF50"
        bg_col     = "rgba(33,150,243,0.07)" if r.direction == "Sent" else "rgba(76,175,80,0.07)"
        icon_label = f"📤 SENT → {r.from_to}" if r.direction == "Sent" else f"📥 RECEIVED ← {r.from_to}"
        html += f"""
        <div style="border-left: 3px solid {border_col}; padding: 10px 14px; margin-bottom: 12px;
                    background: {bg_col}; border-radius: 0 8px 8px 0;">
            <div style="display:flex; justify-content:space-between; margin-bottom:4px;">
                <span style="font-weight:700; font-size:0.82rem; color:{border_col};">{icon_label}</span>
                <span style="font-size:0.78rem; color:#9BA3B5;">{r.date}</span>
            </div>
            <div style="font-size:0.84rem; color:#E8EAF0; margin-top:6px; line-height:1.5;">
                {r.summary}
            </div>
        </div>
        """

    return html


# ──────────────────────────────────────────────
# MAIN RENDER
# ──────────────────────────────────────────────
def render_email_tracker():
    st.title("📧 Email Tracking Module")
    st.markdown("Log emails and build a full mail trail per issue.")
    st.markdown("---")

    session = get_session()
    all_issues = session.query(Issue).all()
    open_issues = [i for i in all_issues if i.status != 'Resolved']

    # ── TAB LAYOUT ──────────────────────────────
    tab1, tab2, tab3, tab4 = st.tabs([
        "📤  Log New Email",
        "📥  Log a Response",
        "🧵  Mail Threads",
        "⏳  Pending Follow-ups"
    ])

    # ════════════════════════════════════════════
    # TAB 1 — Log New (outgoing) Email
    # ════════════════════════════════════════════
    with tab1:
        st.subheader("Log a New Outgoing Email")
        if not open_issues:
            st.info("No open issues found. Create one first under 'Log New Issue'.")
        else:
            issue_options = {i.issue_id: i.id for i in open_issues}
            with st.form("new_email_form"):
                issue_disp = st.selectbox("Related Issue*", list(issue_options.keys()))
                c1, c2 = st.columns(2)
                with c1:
                    date_sent = st.date_input("Date Sent*", value=datetime.datetime.utcnow().date())
                    recipient = st.text_input("Recipient (To)*")
                with c2:
                    subject   = st.text_input("Subject*")
                    follow_up_date = st.date_input("Follow-up Date (Optional)", value=None)

                email_summary   = st.text_area("Email Summary*", help="Key points only — not the full text", height=120)
                response_status = st.selectbox("Initial Response Status",
                                               ["No Response", "Responded", "Follow-up Needed"])

                submitted = st.form_submit_button("📤 Log Email", type="primary")
                if submitted:
                    if not recipient or not subject or not email_summary:
                        st.error("Please fill in Recipient, Subject, and Summary.")
                    else:
                        new_email = EmailLog(
                            issue_id=issue_options[issue_disp],
                            date_sent=date_sent,
                            recipient=recipient,
                            subject=subject,
                            email_summary=email_summary,
                            response_status=response_status,
                            follow_up_date=follow_up_date if follow_up_date else None
                        )
                        session.add(new_email)
                        session.commit()
                        st.success(f"✅ Email logged for issue **{issue_disp}**.")
                        st.rerun()

    # ════════════════════════════════════════════
    # TAB 2 — Log a Response (adds to mail trail)
    # ════════════════════════════════════════════
    with tab2:
        st.subheader("Log a Response to an Existing Email")
        all_emails = session.query(EmailLog).all()

        if not all_emails:
            st.info("No emails logged yet. Go to 'Log New Email' first.")
        else:
            # Build selectable list with context
            email_map = {}
            for e in all_emails:
                linked = session.query(Issue).filter_by(id=e.issue_id).first()
                label = f"[{linked.issue_id if linked else 'N/A'}]  {e.subject}  →  {e.recipient}  ({e.date_sent})"
                email_map[label] = e.id

            with st.form("log_response_form"):
                selected_label = st.selectbox("Select Email Thread*", list(email_map.keys()))
                c1, c2 = st.columns(2)
                with c1:
                    resp_date = st.date_input("Response Date*",
                                              value=datetime.datetime.utcnow().date())
                    direction = st.selectbox("Direction*",
                                             ["Received", "Sent"],
                                             help="'Received' = they replied to you. 'Sent' = your follow-up.")
                with c2:
                    from_to = st.text_input(
                        "From (if Received) / To (if Sent)*",
                        help="e.g. the person who replied, or the new recipient"
                    )
                    new_status = st.selectbox("Update Thread Status",
                                              ["No Response", "Responded", "Follow-up Needed"])

                resp_summary = st.text_area("Response Summary*",
                                            help="Key points of the reply or follow-up", height=120)

                resp_submitted = st.form_submit_button("📥 Log Response", type="primary")
                if resp_submitted:
                    if not from_to or not resp_summary:
                        st.error("Please fill in From/To and Response Summary.")
                    else:
                        email_id = email_map[selected_label]
                        new_resp = EmailResponse(
                            email_log_id=email_id,
                            date=resp_date,
                            direction=direction,
                            from_to=from_to,
                            summary=resp_summary
                        )
                        session.add(new_resp)
                        # Update parent email status
                        parent = session.query(EmailLog).filter_by(id=email_id).first()
                        if parent:
                            parent.response_status = new_status
                        session.commit()
                        st.success("✅ Response logged and thread status updated.")
                        st.rerun()

    # ════════════════════════════════════════════
    # TAB 3 — Mail Thread Viewer
    # ════════════════════════════════════════════
    with tab3:
        st.subheader("Full Mail Threads by Issue")
        all_emails = session.query(EmailLog).all()

        if not all_emails:
            st.info("No emails logged yet.")
        else:
            # Group emails by issue
            issue_email_map: dict = {}
            for e in all_emails:
                linked = session.query(Issue).filter_by(id=e.issue_id).first()
                key = linked.issue_id if linked else "Unlinked"
                issue_email_map.setdefault(key, []).append(e)

            for issue_id_str, emails in issue_email_map.items():
                linked_issue = session.query(Issue).filter_by(issue_id=issue_id_str).first()
                title_text   = linked_issue.title if linked_issue else "Unknown Issue"

                st.markdown(f"#### 🗂️ {issue_id_str} — {title_text}")

                for email in emails:
                    responses = session.query(EmailResponse)\
                                       .filter_by(email_log_id=email.id)\
                                       .order_by(EmailResponse.date).all()

                    badge_color = {
                        "Responded":        "#4CAF50",
                        "No Response":      "#F57C00",
                        "Follow-up Needed": "#1565C0"
                    }.get(email.response_status, "#9BA3B5")

                    thread_len = len(responses) + 1  # +1 for original
                    expander_label = (
                        f"📧 {email.subject}  ·  To: {email.recipient}"
                        f"  ·  {thread_len} message(s)"
                        f"  ·  Status: {email.response_status}"
                    )

                    with st.expander(expander_label, expanded=False):
                        thread_html = _build_thread_html(email, responses)
                        st.markdown(thread_html, unsafe_allow_html=True)

                st.markdown("---")

    # ════════════════════════════════════════════
    # TAB 4 — Pending Follow-ups
    # ════════════════════════════════════════════
    with tab4:
        st.subheader("⏳ Pending Follow-ups")
        pending = session.query(EmailLog)\
                         .filter(EmailLog.response_status != 'Responded').all()

        if not pending:
            st.success("🎉 No pending follow-ups. Inbox under control!")
        else:
            rows = []
            for e in pending:
                linked = session.query(Issue).filter_by(id=e.issue_id).first()
                days   = (datetime.datetime.utcnow().date() - e.date_sent).days
                rows.append({
                    "Issue":        linked.issue_id if linked else "N/A",
                    "Subject":      e.subject,
                    "Recipient":    e.recipient,
                    "Days Pending": max(0, days),
                    "Date Sent":    str(e.date_sent),
                    "Status":       e.response_status
                })
            df = pd.DataFrame(rows).sort_values("Days Pending", ascending=False)

            def style_days(val):
                if val > 5:   return "color: #E57373; font-weight:700;"
                if val > 2:   return "color: #FFB74D; font-weight:600;"
                return "color: #81C784;"

            st.dataframe(
                df.style.applymap(style_days, subset=["Days Pending"]),
                hide_index=True
            )

    # ════════════════════════════════════════════
    # DELETE SECTION (below tabs)
    # ════════════════════════════════════════════
    st.markdown("---")
    st.markdown("### 🗑️ Delete an Email Log")
    st.warning("⚠️ Deleting an email will also remove its entire response thread. This cannot be undone.")

    all_emails_del = session.query(EmailLog).all()
    if not all_emails_del:
        st.info("No email logs found to delete.")
    else:
        del_options = {}
        for e in all_emails_del:
            linked = session.query(Issue).filter_by(id=e.issue_id).first()
            label  = f"[{linked.issue_id if linked else 'N/A'}]  {e.subject}  →  {e.recipient}  ({e.date_sent})"
            del_options[label] = e.id

        del_label   = st.selectbox("Select Email to Delete", list(del_options.keys()), key="delete_email_select")
        confirm_del = st.checkbox("I confirm I want to permanently delete this email and all its responses.")

        if st.button("🗑️ Delete Email Log", type="primary", disabled=not confirm_del):
            target = session.query(EmailLog).filter_by(id=del_options[del_label]).first()
            if target:
                session.delete(target)   # cascade deletes EmailResponse rows too
                session.commit()
                st.success("Email log and all responses deleted.")
                st.rerun()

    session.close()
