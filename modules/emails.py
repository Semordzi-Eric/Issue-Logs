import streamlit as st
import datetime
import pandas as pd
from database.models import get_session, Issue, EmailLog, EmailResponse


# ──────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────
def _thread_html(email: EmailLog, responses: list) -> str:
    """Renders a chat-style mail trail as HTML."""
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
        bc  = "#2196F3" if r.direction == "Sent" else "#4CAF50"
        bg  = "rgba(33,150,243,0.07)" if r.direction == "Sent" else "rgba(76,175,80,0.07)"
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


def _get_context_issue(session) -> str | None:
    """
    Returns the issue_id set by Manage Issues' deep-link button, if any.
    Clears it after first use so subsequent visits start fresh.
    """
    issue_id = st.session_state.get("email_context_issue")
    return issue_id


def _clear_context():
    if "email_context_issue" in st.session_state:
        del st.session_state["email_context_issue"]


# ──────────────────────────────────────────────
# MAIN RENDER
# ──────────────────────────────────────────────
def render_email_tracker():
    st.title("📧 Email Tracker")

    session = get_session()
    all_issues = session.query(Issue).order_by(Issue.date.desc()).all()
    all_emails = session.query(EmailLog).order_by(EmailLog.date_sent.desc()).all()

    # ── Context banner (arrived from Manage Issues) ──
    context_issue_id = _get_context_issue(session)
    context_issue    = None

    if context_issue_id:
        context_issue = session.query(Issue).filter_by(issue_id=context_issue_id).first()
        if context_issue:
            bc1, bc2 = st.columns([8, 1])
            with bc1:
                st.info(
                    f"🔗 Showing emails for issue **{context_issue_id} — {context_issue.title}**. "
                    "Clear the filter to see all issues."
                )
            with bc2:
                if st.button("✖ Clear", key="clear_ctx"):
                    _clear_context()
                    st.rerun()

    st.markdown("---")

    # ── Tabs ────────────────────────────────────
    tab_threads, tab_log_email, tab_log_response, tab_pending, tab_delete = st.tabs([
        "🧵  Mail Threads",
        "📤  Log Email",
        "📥  Log Response",
        "⏳  Pending Follow-ups",
        "🗑️  Delete"
    ])

    # ════════════════════════════════════════════
    # TAB 1 — Mail Threads
    # ════════════════════════════════════════════
    with tab_threads:
        # Filter emails to context issue or show all
        if context_issue:
            display_emails = [e for e in all_emails if e.issue_id == context_issue.id]
            issue_pool     = [context_issue]
            st.markdown(f"**Showing threads for {context_issue_id}**")
        else:
            display_emails = all_emails
            issue_pool     = all_issues
            st.markdown(f"**All mail threads ({len(display_emails)} email(s) across {len(issue_pool)} issue(s))**")

        if not display_emails:
            st.info("No emails logged yet. Use the **📤 Log Email** tab to start.")
        else:
            # Group by issue
            issue_dict = {i.id: i for i in all_issues}
            grouped: dict = {}
            for em in display_emails:
                issue_obj = issue_dict.get(em.issue_id)
                key = issue_obj.issue_id if issue_obj else "Unlinked"
                grouped.setdefault(key, {"issue": issue_obj, "emails": []})
                grouped[key]["emails"].append(em)

            for gkey, gdata in grouped.items():
                issue_obj = gdata["issue"]
                g_emails  = gdata["emails"]
                title_str = issue_obj.title if issue_obj else "Unknown"
                status_str = issue_obj.status if issue_obj else ""

                st.markdown(f"#### 🗂️ {gkey} — {title_str}")
                st.caption(f"Status: {status_str}  ·  {len(g_emails)} email thread(s)")

                for em in g_emails:
                    responses = session.query(EmailResponse)\
                                       .filter_by(email_log_id=em.id)\
                                       .order_by(EmailResponse.date).all()
                    total = len(responses) + 1

                    status_icon = {
                        "Responded":        "✅",
                        "No Response":      "⏳",
                        "Follow-up Needed": "🔔"
                    }.get(em.response_status, "❓")

                    exp_label = (
                        f"{status_icon} {em.subject}  ·  → {em.recipient}"
                        f"  ·  {total} message(s)  ·  {em.response_status}"
                    )
                    with st.expander(exp_label, expanded=(total == 1 and len(g_emails) == 1)):
                        st.markdown(_thread_html(em, responses), unsafe_allow_html=True)

                st.markdown("---")

    # ════════════════════════════════════════════
    # TAB 2 — Log New Email
    # ════════════════════════════════════════════
    with tab_log_email:
        st.subheader("Log a New Outgoing Email")

        if not all_issues:
            st.info("No issues found. Create one under **Log New Issue** first.")
        else:
            issue_options = {i.issue_id: i.id for i in all_issues}
            issue_keys    = list(issue_options.keys())

            # Pre-select if coming from Manage Issues
            default_idx = issue_keys.index(context_issue_id) \
                if context_issue_id and context_issue_id in issue_keys else 0

            with st.form("email_log_form"):
                issue_disp  = st.selectbox("Related Issue*", issue_keys, index=default_idx)
                c1, c2      = st.columns(2)
                with c1:
                    date_sent      = st.date_input("Date Sent*",
                                                   value=datetime.datetime.utcnow().date())
                    recipient      = st.text_input("Recipient (To)*")
                with c2:
                    subject        = st.text_input("Subject*")
                    follow_up_date = st.date_input("Follow-up Date (Optional)", value=None)

                email_summary   = st.text_area("Email Summary*",
                                               help="Key points only, not the full body", height=120)
                response_status = st.selectbox("Initial Response Status",
                                               ["No Response", "Responded", "Follow-up Needed"])

                if st.form_submit_button("📤 Log Email", type="primary"):
                    if not recipient or not subject or not email_summary:
                        st.error("Please fill in Recipient, Subject, and Summary.")
                    else:
                        session.add(EmailLog(
                            issue_id=issue_options[issue_disp],
                            date_sent=date_sent,
                            recipient=recipient,
                            subject=subject,
                            email_summary=email_summary,
                            response_status=response_status,
                            follow_up_date=follow_up_date if follow_up_date else None
                        ))
                        session.commit()
                        st.success(f"✅ Email logged for **{issue_disp}**.")
                        st.rerun()

    # ════════════════════════════════════════════
    # TAB 3 — Log a Response
    # ════════════════════════════════════════════
    with tab_log_response:
        st.subheader("Log a Response or Follow-up")

        # Filter email list to context issue or all
        if context_issue:
            selectable_emails = [e for e in all_emails if e.issue_id == context_issue.id]
        else:
            selectable_emails = all_emails

        if not selectable_emails:
            st.info("No emails logged yet. Use the **📤 Log Email** tab first.")
        else:
            issue_dict = {i.id: i for i in all_issues}
            email_map  = {}
            for e in selectable_emails:
                issue_obj  = issue_dict.get(e.issue_id)
                issue_part = issue_obj.issue_id if issue_obj else "N/A"
                label = f"[{issue_part}]  {e.subject}  →  {e.recipient}  ({e.date_sent})"
                email_map[label] = e.id

            with st.form("response_form"):
                selected_label = st.selectbox("Select Email Thread*", list(email_map.keys()))
                r_col1, r_col2 = st.columns(2)
                with r_col1:
                    resp_date  = st.date_input("Response Date*",
                                               value=datetime.datetime.utcnow().date())
                    direction  = st.selectbox("Direction*", ["Received", "Sent"],
                                              help="Received = they replied. Sent = your follow-up.")
                with r_col2:
                    from_to    = st.text_input("From (if Received) / To (if Sent)*")
                    new_status = st.selectbox("Update Thread Status",
                                              ["No Response", "Responded", "Follow-up Needed"])

                resp_summary = st.text_area("Response Summary*", height=120)

                if st.form_submit_button("📥 Log Response", type="primary"):
                    if not from_to or not resp_summary:
                        st.error("Please fill in From/To and Response Summary.")
                    else:
                        eid = email_map[selected_label]
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
                        st.success("✅ Response logged and thread status updated.")
                        st.rerun()

    # ════════════════════════════════════════════
    # TAB 4 — Pending Follow-ups
    # ════════════════════════════════════════════
    with tab_pending:
        st.subheader("⏳ Pending Follow-ups")

        pending_source = [e for e in all_emails if e.response_status != "Responded"]
        if context_issue:
            pending_source = [e for e in pending_source if e.issue_id == context_issue.id]

        if not pending_source:
            st.success("🎉 No pending follow-ups. All communications responded!")
        else:
            issue_dict = {i.id: i for i in all_issues}
            rows = []
            for e in pending_source:
                linked = issue_dict.get(e.issue_id)
                days   = (datetime.datetime.utcnow().date() - e.date_sent).days
                rows.append({
                    "Issue ID":          linked.issue_id if linked else "N/A",
                    "Issue Title":       linked.title if linked else "N/A",
                    "Subject":           e.subject,
                    "Recipient":         e.recipient,
                    "Days Without Reply": max(0, days),
                    "Date Sent":         str(e.date_sent),
                    "Status":            e.response_status,
                })
            df = pd.DataFrame(rows).sort_values("Days Without Reply", ascending=False)

            def style_days(val):
                if val > 5: return "color:#E57373; font-weight:700;"
                if val > 2: return "color:#FFB74D; font-weight:600;"
                return "color:#81C784;"

            st.dataframe(
                df.style.applymap(style_days, subset=["Days Without Reply"]),
                hide_index=True
            )

    # ════════════════════════════════════════════
    # TAB 5 — Delete
    # ════════════════════════════════════════════
    with tab_delete:
        st.subheader("🗑️ Delete Email Log")
        st.warning("⚠️ Deletes the email and its entire response thread. Cannot be undone.")

        del_source = all_emails if not context_issue \
            else [e for e in all_emails if e.issue_id == context_issue.id]

        if not del_source:
            st.info("No emails to delete.")
        else:
            issue_dict = {i.id: i for i in all_issues}
            del_map    = {}
            for e in del_source:
                linked = issue_dict.get(e.issue_id)
                ipart  = linked.issue_id if linked else "N/A"
                label  = f"[{ipart}]  {e.subject}  →  {e.recipient}  ({e.date_sent})"
                del_map[label] = e.id

            del_label  = st.selectbox("Select Email to Delete", list(del_map.keys()))
            confirm    = st.checkbox("I confirm: permanently delete this email and all its responses.")

            if st.button("🗑️ Delete", type="primary", disabled=not confirm):
                target = session.query(EmailLog).filter_by(id=del_map[del_label]).first()
                if target:
                    session.delete(target)   # cascade handles EmailResponse rows
                    session.commit()
                    st.success("Email and all responses deleted.")
                    st.rerun()

    session.close()
