import streamlit as st
import datetime
import pandas as pd
from database.models import get_session, Issue, EmailLog, EmailResponse

EMAIL_SUBJECTS = [
    "Re: Issue {issue_id} — Action Required",
    "Follow-up: {issue_id} — Awaiting Resolution",
    "Escalation Notice: {issue_id} — Unresolved",
    "Update Request: {issue_id} Status",
    "Investigation Report: {issue_id}",
]


def _get_recent_recipients() -> list:
    """Return distinct recipients from previously logged emails."""
    session = get_session()
    results = session.query(EmailLog.recipient).distinct().all()
    session.close()
    return [r[0] for r in results if r[0]]


# ──────────────────────────────────────────────
# HELPERS
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


def _thread_to_text(email: EmailLog, linked_issue, responses: list) -> str:
    """Plain-text export of a single mail thread."""
    lines = [
        f"MAIL TRAIL EXPORT",
        f"Issue: {linked_issue.issue_id if linked_issue else 'N/A'} — {linked_issue.title if linked_issue else ''}",
        f"{'='*60}",
        f"",
        f"[SENT]  Date: {email.date_sent}",
        f"To:      {email.recipient}",
        f"Subject: {email.subject}",
        f"Summary: {email.email_summary}",
        f"",
    ]
    for r in responses:
        direction_label = "SENT" if r.direction == "Sent" else "RECEIVED"
        from_to_label   = f"To: {r.from_to}" if r.direction == "Sent" else f"From: {r.from_to}"
        lines += [
            f"[{direction_label}]  Date: {r.date}",
            f"{from_to_label}",
            f"Summary: {r.summary}",
            f"",
        ]
    lines.append(f"{'='*60}")
    lines.append(f"Exported: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")
    return "\n".join(lines)


def _all_threads_to_csv(all_emails, all_issues, session) -> str:
    """Export all threads to CSV for download."""
    issue_dict = {i.id: i for i in all_issues}
    rows = []
    for em in all_emails:
        linked = issue_dict.get(em.issue_id)
        rows.append({
            "Type": "Email",
            "Issue ID": linked.issue_id if linked else "N/A",
            "Date": str(em.date_sent),
            "Direction": "Sent",
            "From/To": em.recipient,
            "Subject": em.subject,
            "Summary": em.email_summary,
            "Status": em.response_status,
        })
        resps = session.query(EmailResponse).filter_by(email_log_id=em.id).order_by(EmailResponse.date).all()
        for r in resps:
            rows.append({
                "Type": "Response",
                "Issue ID": linked.issue_id if linked else "N/A",
                "Date": str(r.date),
                "Direction": r.direction,
                "From/To": r.from_to,
                "Subject": em.subject,
                "Summary": r.summary,
                "Status": "",
            })
    return pd.DataFrame(rows).to_csv(index=False)


def _get_context_issue(session):
    return st.session_state.get("email_context_issue")


def _clear_context():
    if "email_context_issue" in st.session_state:
        del st.session_state["email_context_issue"]


# ──────────────────────────────────────────────
# MAIN RENDER
# ──────────────────────────────────────────────
def render_email_tracker():
    st.title("📧 Email Tracker")

    session    = get_session()
    all_issues = session.query(Issue).order_by(Issue.date.desc()).all()
    all_emails = session.query(EmailLog).order_by(EmailLog.date_sent.desc()).all()

    context_issue_id = _get_context_issue(session)
    context_issue    = None

    if context_issue_id:
        context_issue = session.query(Issue).filter_by(issue_id=context_issue_id).first()
        if context_issue:
            bc1, bc2 = st.columns([8, 1])
            with bc1:
                st.info(
                    f"🔗 Showing emails for **{context_issue_id} — {context_issue.title}**. "
                    "Clear the filter to see all issues."
                )
            with bc2:
                if st.button("✖ Clear", key="clear_ctx"):
                    _clear_context()
                    st.rerun()

    st.markdown("---")

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
        if context_issue:
            display_emails = [e for e in all_emails if e.issue_id == context_issue.id]
            st.markdown(f"**Showing threads for {context_issue_id}** — {len(display_emails)} email(s)")
        else:
            display_emails = all_emails
            st.markdown(f"**All mail threads — {len(display_emails)} email(s) across {len(all_issues)} issue(s)**")

        # ── Bulk CSV download of all visible threads ──────────
        if display_emails:
            csv_all = _all_threads_to_csv(display_emails, all_issues, session)
            st.download_button(
                label="📥 Export All Visible Threads (CSV)",
                data=csv_all,
                file_name=f"mail_trail_export_{datetime.date.today()}.csv",
                mime="text/csv",
                key="dl_all_threads"
            )

        if not display_emails:
            st.info("No emails logged yet. Use the **📤 Log Email** tab to start.")
        else:
            issue_dict = {i.id: i for i in all_issues}
            grouped: dict = {}
            for em in display_emails:
                issue_obj = issue_dict.get(em.issue_id)
                key = issue_obj.issue_id if issue_obj else "Unlinked"
                grouped.setdefault(key, {"issue": issue_obj, "emails": []})
                grouped[key]["emails"].append(em)

            for gkey, gdata in grouped.items():
                issue_obj  = gdata["issue"]
                g_emails   = gdata["emails"]
                title_str  = issue_obj.title if issue_obj else "Unknown"
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
                        # ── Per-thread download ──
                        thread_txt = _thread_to_text(em, issue_obj, responses)
                        st.download_button(
                            label="📄 Export this thread (.txt)",
                            data=thread_txt,
                            file_name=f"thread_{gkey}_{em.id}_{em.date_sent}.txt",
                            mime="text/plain",
                            key=f"dl_thread_{em.id}"
                        )
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
            default_idx   = issue_keys.index(context_issue_id) \
                if context_issue_id and context_issue_id in issue_keys else 0

            # ── Form clear counter (resets fields on save) ──────────────
            if "email_form_key" not in st.session_state:
                st.session_state.email_form_key = 0

            # Show last-saved confirmation
            if st.session_state.get("last_email_saved"):
                saved = st.session_state.pop("last_email_saved")
                st.success(
                    f"✅ Email logged for **{saved['issue']}** → {saved['recipient']}  "
                    f"| Subject: *{saved['subject']}*"
                )
                st.toast("📧 Email saved!", icon="✅")

            # ── Quick-fill helpers (outside form) ──────────────────
            recent_recips = _get_recent_recipients()
            if recent_recips:
                st.markdown("**📋 Recent Recipients — click to fill:**")
                r_cols = st.columns(min(len(recent_recips), 5))
                for ri, recip in enumerate(recent_recips[:5]):
                    with r_cols[ri]:
                        if st.button(recip, key=f"recip_{ri}",
                                     use_container_width=True):
                            st.session_state.prefill_recipient = recip
                            st.rerun()

            if context_issue_id:
                st.markdown("**📝 Subject Templates — click to fill:**")
                s_cols = st.columns(min(len(EMAIL_SUBJECTS), 3))
                for si, subj_tpl in enumerate(EMAIL_SUBJECTS[:3]):
                    filled = subj_tpl.format(issue_id=context_issue_id)
                    with s_cols[si]:
                        btn_lbl = (filled[:32] + "…") if len(filled) > 32 else filled
                        if st.button(btn_lbl, key=f"subj_{si}",
                                     use_container_width=True, help=filled):
                            st.session_state.prefill_subject = filled
                            st.rerun()

            prefill_recip   = st.session_state.pop("prefill_recipient", "")
            prefill_subject = st.session_state.pop("prefill_subject", "")

            st.markdown("")
            # ── The form (key changes on save → fields reset) ─────
            with st.form(key=f"email_log_form_{st.session_state.email_form_key}"):
                issue_disp = st.selectbox("Related Issue*", issue_keys, index=default_idx)

                c1, c2 = st.columns(2)
                with c1:
                    date_sent = st.date_input(
                        "Date Sent*", value=datetime.datetime.utcnow().date()
                    )
                    recipient = st.text_input(
                        "Recipient (To)* — email or name",
                        value=prefill_recip,
                        placeholder="e.g. manager@bank.com"
                    )
                with c2:
                    subject = st.text_input(
                        "Subject*",
                        value=prefill_subject,
                        placeholder="e.g. Re: Issue AUD-20250331-001"
                    )
                    response_status = st.selectbox(
                        "Initial Status",
                        ["No Response", "Follow-up Needed", "Responded"]
                    )

                email_summary = st.text_area(
                    "Email Summary*",
                    placeholder="Key points of the email — what you flagged, requested, or communicated.",
                    height=110,
                    help="No need to paste the full email. Just the key points."
                )
                follow_up_date = st.date_input("Follow-up Date (Optional)", value=None)

                submitted = st.form_submit_button(
                    "📤 Log Email", type="primary", use_container_width=True
                )

            if submitted:
                if not recipient or not subject or not email_summary:
                    st.error("❌ Recipient, Subject, and Summary are required.")
                else:
                    with st.spinner("Saving..."):
                        session.add(EmailLog(
                            issue_id=issue_options[issue_disp],
                            date_sent=date_sent,
                            recipient=recipient.strip(),
                            subject=subject.strip(),
                            email_summary=email_summary.strip(),
                            response_status=response_status,
                            follow_up_date=follow_up_date if follow_up_date else None
                        ))
                        session.commit()
                    # Store confirmation, bump key to clear form
                    st.session_state.last_email_saved = {
                        "issue":     issue_disp,
                        "recipient": recipient.strip(),
                        "subject":   subject.strip()
                    }
                    st.session_state.email_form_key += 1
                    st.rerun()

            # ── Today's log (compact audit trail) ─────────────────
            today_emails = [
                e for e in all_emails
                if e.date_sent == datetime.date.today()
            ]
            if today_emails:
                st.markdown("---")
                st.markdown(f"**📌 Logged today ({len(today_emails)} email(s)):**")
                issue_dict = {i.id: i for i in all_issues}
                for te in today_emails:
                    lnk = issue_dict.get(te.issue_id)
                    iid = lnk.issue_id if lnk else "N/A"
                    st.markdown(
                        f"&nbsp;&nbsp;• [{iid}] **{te.subject}** → {te.recipient} · *{te.response_status}*",
                        unsafe_allow_html=True
                    )

    # ════════════════════════════════════════════
    # TAB 3 — Log a Response
    # ════════════════════════════════════════════
    with tab_log_response:
        st.subheader("Log a Response or Follow-up")

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

            # ── Form clear counter ────────────
            if "resp_form_key" not in st.session_state:
                st.session_state.resp_form_key = 0

            # Show last-saved confirmation
            if st.session_state.get("last_resp_saved"):
                saved = st.session_state.pop("last_resp_saved")
                st.success(
                    f"✅ **{saved['direction']}** response logged on thread: *{saved['thread']}*  "
                    f"| From/To: {saved['from_to']}"
                )
                st.toast("📥 Response saved!", icon="✅")

            # ── Quick-fill recipient from thread ────────────────
            if recent_recips := _get_recent_recipients():
                st.markdown("**📋 Quick From/To — click to fill:**")
                rc2 = st.columns(min(len(recent_recips), 5))
                for ri2, recip2 in enumerate(recent_recips[:5]):
                    with rc2[ri2]:
                        if st.button(recip2, key=f"rrecip_{ri2}",
                                     use_container_width=True):
                            st.session_state.prefill_from_to = recip2
                            st.rerun()

            prefill_from_to = st.session_state.pop("prefill_from_to", "")

            st.markdown("")
            with st.form(key=f"response_form_{st.session_state.resp_form_key}"):
                selected_label = st.selectbox(
                    "Email Thread to Reply On*",
                    list(email_map.keys()),
                    help="Select the original email this is a response to"
                )

                r_col1, r_col2, r_col3 = st.columns(3)
                with r_col1:
                    resp_date = st.date_input(
                        "Response Date*", value=datetime.datetime.utcnow().date()
                    )
                with r_col2:
                    direction = st.selectbox(
                        "Direction*", ["Received", "Sent"],
                        help="Received = they replied to you | Sent = you followed up"
                    )
                with r_col3:
                    new_status = st.selectbox(
                        "Update Thread Status",
                        ["Responded", "Follow-up Needed", "No Response"]
                    )

                from_to = st.text_input(
                    "From (if Received) / To (if Sent)*",
                    value=prefill_from_to,
                    placeholder="Person who replied, or new recipient"
                )
                resp_summary = st.text_area(
                    "Response Summary*",
                    placeholder="Key points of the reply or follow-up sent.",
                    height=110
                )
                resp_submitted = st.form_submit_button(
                    "📥 Log Response", type="primary", use_container_width=True
                )

            if resp_submitted:
                if not from_to or not resp_summary:
                    st.error("❌ From/To and Response Summary are required.")
                else:
                    with st.spinner("Saving response..."):
                        eid = email_map[selected_label]
                        session.add(EmailResponse(
                            email_log_id=eid,
                            date=resp_date,
                            direction=direction,
                            from_to=from_to.strip(),
                            summary=resp_summary.strip()
                        ))
                        parent = session.query(EmailLog).filter_by(id=eid).first()
                        if parent:
                            parent.response_status = new_status
                        session.commit()
                    # Store confirmation, bump key to clear form
                    st.session_state.last_resp_saved = {
                        "direction": direction,
                        "thread":    selected_label[:50],
                        "from_to":   from_to.strip()
                    }
                    st.session_state.resp_form_key += 1
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
            st.success("🎉 No pending follow-ups. All communications are responded to!")
        else:
            issue_dict = {i.id: i for i in all_issues}
            rows = []
            for e in pending_source:
                linked = issue_dict.get(e.issue_id)
                days   = (datetime.datetime.utcnow().date() - e.date_sent).days
                rows.append({
                    "Issue ID":           linked.issue_id if linked else "N/A",
                    "Issue Title":        linked.title if linked else "N/A",
                    "Subject":            e.subject,
                    "Recipient":          e.recipient,
                    "Days Without Reply": max(0, days),
                    "Date Sent":          str(e.date_sent),
                    "Follow-up Date":     str(e.follow_up_date) if e.follow_up_date else "-",
                    "Status":             e.response_status,
                    "_email_id":          e.id,
                })
            df = pd.DataFrame(rows).sort_values("Days Without Reply", ascending=False)

            def style_days(val):
                if val > 5: return "color:#E57373; font-weight:700;"
                if val > 2: return "color:#FFB74D; font-weight:600;"
                return "color:#81C784;"

            st.dataframe(
                df.drop(columns=["_email_id"]).style.map(style_days, subset=["Days Without Reply"]),
                hide_index=True,
                use_container_width=True
            )

            # ── Quick Mark Responded buttons ──────────
            st.markdown("**⚡ Quick Actions:**")
            qr_cols = st.columns(min(len(pending_source), 3))
            for qi, e in enumerate(pending_source[:3]):
                linked = issue_dict.get(e.issue_id)
                lbl    = f"✅ Mark Responded: {e.subject[:20]}…"
                with qr_cols[qi]:
                    if st.button(lbl, key=f"qresp_{e.id}", use_container_width=True,
                                 help=f"{e.subject} → {e.recipient}"):
                        with st.spinner("Updating..."):
                            e_obj = session.query(EmailLog).filter_by(id=e.id).first()
                            if e_obj:
                                e_obj.response_status = "Responded"
                                session.commit()
                        st.toast("Marked as Responded!", icon="✅")
                        st.rerun()

            st.download_button(
                "📥 Export Pending Follow-ups (CSV)",
                data=df.drop(columns=["_email_id"]).to_csv(index=False),
                file_name=f"pending_followups_{datetime.date.today()}.csv",
                mime="text/csv"
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

            del_label = st.selectbox("Select Email to Delete", list(del_map.keys()))
            confirm   = st.checkbox("I confirm: permanently delete this email and all its responses.")

            if st.button("🗑️ Delete", type="primary", disabled=not confirm):
                with st.spinner("Deleting..."):
                    target = session.query(EmailLog).filter_by(id=del_map[del_label]).first()
                    if target:
                        session.delete(target)
                        session.commit()
                st.success("🗑️ Email log and all responses deleted.")
                st.toast("Deleted successfully", icon="🗑️")
                st.rerun()

    session.close()
