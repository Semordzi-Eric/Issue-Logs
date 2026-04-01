import streamlit as st
import datetime
import pandas as pd
from database.models import get_session, Issue, EmailLog, EmailResponse
from database.sheets_sync import get_sheets_sync
from utils.helpers import generate_issue_id, predict_category

CATEGORIES = [
    "Revenue Leakage", "Failed Transactions", "Suspicious Activity",
    "Reversals", "Reprocessed", "System Errors", "Others"
]
PRIORITIES = ["Low", "Medium", "High", "Critical"]
STATUSES   = ["Open", "Investigating", "Resolved", "Escalated"]

# ── Quick-Log Templates ─────────────────────────────────
TEMPLATES = {
    "💸 Revenue Leakage": {
        "title":           "Revenue Leakage Detected",
        "category":        "Revenue Leakage",
        "priority":        "High",
        "affected_system": "Core Banking",
        "description":     "A revenue leakage was identified. Transactions were processed but revenue was not correctly captured or posted.",
        "root_cause":      "Under investigation — possible billing system mismatch.",
    },
    "❌ Failed Transaction": {
        "title":           "Failed Transaction Reported",
        "category":        "Failed Transactions",
        "priority":        "Medium",
        "affected_system": "POS Terminal",
        "description":     "One or more transactions failed to process successfully. Customer was debited but transaction did not complete.",
        "root_cause":      "Under investigation — possible network timeout or system error.",
    },
    "🔁 Reversal Issue": {
        "title":           "Suspicious Reversal Detected",
        "category":        "Reversals",
        "priority":        "High",
        "affected_system": "Mobile Banking",
        "description":     "A transaction reversal was flagged as suspicious. The reversal amount does not match the original transaction.",
        "root_cause":      "Possible duplicate reversal or unauthorized reversal request.",
    },
    "♻️ Reprocessed Transaction": {
        "title":           "Transaction Reprocessed",
        "category":        "Reprocessed",
        "priority":        "Medium",
        "affected_system": "Core Banking",
        "description":     "A transaction was reprocessed, potentially causing a double charge or duplicate credit.",
        "root_cause":      "System retry without deduplication check.",
    },
    "🚨 Suspicious Activity": {
        "title":           "Suspicious Account Activity",
        "category":        "Suspicious Activity",
        "priority":        "Critical",
        "affected_system": "Internet Banking",
        "description":     "Unusual account activity detected. Multiple high-value transactions in a short period from an atypical location.",
        "root_cause":      "Possible unauthorized access or fraud attempt.",
    },
    "⚙️ System Error": {
        "title":           "System Error Reported",
        "category":        "System Errors",
        "priority":        "Medium",
        "affected_system": "Core Banking",
        "description":     "A system error was reported that may have impacted transaction processing or data integrity.",
        "root_cause":      "Pending system logs review.",
    },
}

EMAIL_SUBJECTS = [
    "Re: Issue {issue_id} — Action Required",
    "Follow-up: {issue_id} — Awaiting Resolution",
    "Escalation Notice: {issue_id} — Unresolved",
    "Update Request: {issue_id} Status",
    "Investigation Report: {issue_id}",
]


def _navigate_to_emails(issue_id: str):
    st.session_state.email_context_issue = issue_id
    st.session_state.nav_page = "📧 Email Tracker"
    st.rerun()


def _get_field_memory():
    """Return last-used field values from session state."""
    return {
        "affected_system": st.session_state.get("last_system", ""),
        "priority":        st.session_state.get("last_priority", "Medium"),
        "category":        st.session_state.get("last_category", "Others"),
    }


def _save_field_memory(system, priority, category):
    st.session_state.last_system   = system
    st.session_state.last_priority = priority
    st.session_state.last_category = category


def _get_recent_systems() -> list:
    """Pull unique recent affected systems from DB."""
    session = get_session()
    results = session.query(Issue.affected_system).distinct().all()
    session.close()
    return [r[0] for r in results if r[0]]


def _get_recent_recipients() -> list:
    session = get_session()
    results = session.query(EmailLog.recipient).distinct().all()
    session.close()
    return [r[0] for r in results if r[0]]


# ──────────────────────────────────────────────
# LOG NEW ISSUE
# ──────────────────────────────────────────────
def render_add_issue():
    st.title("📝 Log New Audit Issue")
    st.markdown("---")

    # ── Quick-Log Template Buttons ───────────────
    st.markdown("#### ⚡ Quick Templates — Click to Pre-fill the Form")
    st.caption("Select a template to auto-fill all fields. You can edit before submitting.")

    tpl_cols = st.columns(len(TEMPLATES))
    selected_tpl = st.session_state.get("selected_template", None)

    for idx, (label, tpl) in enumerate(TEMPLATES.items()):
        with tpl_cols[idx]:
            if st.button(label, key=f"tpl_{idx}", use_container_width=True):
                st.session_state.selected_template = label
                st.rerun()

    if selected_tpl and selected_tpl in TEMPLATES:
        tpl = TEMPLATES[selected_tpl]
        st.info(f"✨ Template **{selected_tpl}** loaded. Fields pre-filled below — edit as needed.")

    st.markdown("---")

    # ── Fast Entry toggle ────────────────────────
    fast_mode = st.toggle("⚡ Fast Entry Mode (minimal fields)", value=False,
                          help="Log quickly with just the essentials. Fills defaults for the rest.")

    st.markdown("")

    # Load template or memory defaults
    tpl_data  = TEMPLATES.get(selected_tpl, {}) if selected_tpl else {}
    mem       = _get_field_memory()
    recent_systems = _get_recent_systems()

    # Priority default
    prio_default = tpl_data.get("priority", mem["priority"])
    prio_idx     = PRIORITIES.index(prio_default) if prio_default in PRIORITIES else 1

    # Category default
    cat_default  = tpl_data.get("category", mem["category"])
    cat_idx      = CATEGORIES.index(cat_default) if cat_default in CATEGORIES else 6

    # System default
    sys_default  = tpl_data.get("affected_system", mem["affected_system"])

    if fast_mode:
        # ── FAST ENTRY FORM ──────────────────────
        st.markdown("##### 🚀 Fast Entry — Essential Fields Only")
        with st.form("fast_issue_form"):
            fast_title  = st.text_input("Issue Title*", value=tpl_data.get("title", ""))
            f_col1, f_col2, f_col3 = st.columns(3)
            with f_col1:
                fast_cat    = st.selectbox("Category*", CATEGORIES, index=cat_idx)
            with f_col2:
                fast_prio   = st.selectbox("Priority*", PRIORITIES, index=prio_idx)
            with f_col3:
                # System — show dropdown of recent + free text
                sys_opts    = ["(Type new...)"] + recent_systems
                sys_sel     = st.selectbox("Affected System*", sys_opts,
                                           index=sys_opts.index(sys_default)
                                           if sys_default in sys_opts else 0)

            if sys_sel == "(Type new...)":
                fast_sys = st.text_input("Enter System Name*", value="")
            else:
                fast_sys = sys_sel

            fast_desc = st.text_area("Brief Description*", value=tpl_data.get("description", ""), height=80)
            fast_txn  = st.text_input("Transaction ID (Optional)")
            fast_amt  = st.number_input("Amount (GHS ₵)", min_value=0.0, step=10.0)
            fast_sub  = st.form_submit_button("⚡ Quick Save", type="primary")

        if fast_sub:
            if not fast_title or not fast_desc or not fast_sys:
                st.error("❌ Title, Description, and System are required.")
            else:
                with st.spinner("Saving..."):
                    session = get_session()
                    ni = Issue(
                        issue_id=generate_issue_id(),
                        date=datetime.date.today(),
                        title=fast_title,
                        description=fast_desc,
                        category=fast_cat,
                        priority=fast_prio,
                        affected_system=fast_sys,
                        transaction_id=fast_txn if fast_txn else None,
                        amount=fast_amt if fast_amt > 0 else None,
                        root_cause=tpl_data.get("root_cause", None),
                        status="Open"
                    )
                    session.add(ni)
                    session.commit()
                    iid = ni.issue_id
                    session.close()
                    _save_field_memory(fast_sys, fast_prio, fast_cat)
                    # Clear template after use
                    if "selected_template" in st.session_state:
                        del st.session_state["selected_template"]
                st.success(f"✅ Issue **{iid}** logged!")
                # ── Google Sheets Sync ──
                get_sheets_sync().sync_issue(ni, action="INSERT")
                st.toast(f"{iid} saved!", icon="⚡")
                st.info("💡 Head to **Manage Issues** to add more details.")

    else:
        # ── FULL ENTRY FORM ──────────────────────
        st.markdown("##### 📋 Full Issue Form")
        with st.form("new_issue_form"):
            col1, col2 = st.columns(2)
            with col1:
                title = st.text_input("Issue Title*", value=tpl_data.get("title", ""),
                                      help="A short, descriptive title")
                date  = st.date_input("Date Found*", value=datetime.date.today())
            with col2:
                # Affected System: recent dropdown + free text
                sys_opts = ["(Type new...)"] + recent_systems
                sys_sel  = st.selectbox("Affected System*", sys_opts,
                                        index=sys_opts.index(sys_default)
                                        if sys_default in sys_opts else 0,
                                        help="Select a recent system or choose '(Type new...)'")
                if sys_sel == "(Type new...)":
                    affected_system = st.text_input("Enter System Name*",
                                                    value=tpl_data.get("affected_system", ""))
                else:
                    affected_system = sys_sel
                    st.text_input("Affected System (selected)", value=sys_sel, disabled=True)

                priority = st.selectbox("Priority*", PRIORITIES, index=prio_idx)

            description = st.text_area("Issue Description*",
                                       value=tpl_data.get("description", ""),
                                       help="Detailed explanation of the finding", height=130)

            col3, col4 = st.columns(2)
            with col3:
                category       = st.selectbox("Category*", CATEGORIES, index=cat_idx)
                transaction_id = st.text_input("Transaction ID (Optional)")
            with col4:
                amount = st.number_input("Amount Involved (GHS ₵)", min_value=0.0, step=10.0)
                status = st.selectbox("Initial Status", STATUSES, index=0)

            root_cause = st.text_input("Root Cause / Hypothesis (Optional)",
                                       value=tpl_data.get("root_cause", ""))
            submitted  = st.form_submit_button("📝 Log Issue", type="primary")

        if submitted:
            if not title or not description or not affected_system:
                st.error("❌ Please fill in all required fields marked with *.")
            else:
                with st.spinner("Saving issue..."):
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
                    _save_field_memory(affected_system, priority, category)
                    if "selected_template" in st.session_state:
                        del st.session_state["selected_template"]
                st.success(f"✅ Issue **{iid}** logged successfully!")
                # ── Google Sheets Sync ──
                get_sheets_sync().sync_issue(new_issue, action="INSERT")
                st.toast(f"Issue {iid} saved!", icon="✅")
                st.info("💡 Head to **Manage Issues** to update or track emails for this issue.")


# ──────────────────────────────────────────────
# MANAGE ISSUES
# ──────────────────────────────────────────────
def render_manage_issues():
    st.title("🔍 Manage & Filter Issues")
    st.markdown(
        "View, filter, and update issues. "
        "Click **📧 Open Email Trail** to manage communications in Email Tracker."
    )
    st.markdown("---")

    session = get_session()
    issues  = session.query(Issue).all()

    if not issues:
        st.info("No issues found. Go to **Log New Issue** to create one.")
        session.close()
        return

    rows = []
    for i in issues:
        emails       = session.query(EmailLog).filter_by(issue_id=i.id).all()
        email_count  = len(emails)
        responded    = sum(1 for e in emails if e.response_status == "Responded")
        pending      = sum(1 for e in emails if e.response_status != "Responded")
        rows.append({
            "ID": i.id, "Issue ID": i.issue_id, "Date": i.date,
            "Title": i.title, "Category": i.category,
            "Priority": i.priority, "Status": i.status,
            "Amount": f"₵{i.amount:,.2f}" if i.amount else "-",
            "📧 Emails": email_count, "✅ Responded": responded, "⏳ Pending": pending,
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
    disp = filtered_df.drop(columns=["ID"])
    st.dataframe(disp, hide_index=True, use_container_width=True)
    st.download_button(
        "📥 Export Issues Table (CSV)",
        data=disp.to_csv(index=False),
        file_name=f"issues_export_{datetime.date.today()}.csv",
        mime="text/csv",
        key="dl_issues_table"
    )

    if filtered_df.empty:
        session.close()
        return

    # ── Select issue ─────────────────────────────
    st.markdown("---")
    selected_id = st.selectbox("Select Issue to work with",
                               filtered_df["Issue ID"].tolist(),
                               key="manage_issue_select")
    target = session.query(Issue).filter_by(issue_id=selected_id).first()

    if not target:
        session.close()
        return

    # ── Detail Metrics ───────────────────────────
    d_col1, d_col2, d_col3, d_col4 = st.columns(4)
    d_col1.metric("Category",     target.category)
    d_col2.metric("Priority",     target.priority)
    d_col3.metric("Status",       target.status)
    d_col4.metric("Emails Logged", session.query(EmailLog).filter_by(issue_id=target.id).count())

    # ── Quick Status Buttons ─────────────────────
    st.markdown("#### ⚡ Quick Status Update")
    st.caption("Click any button below to instantly change the issue status — no form needed.")
    qs_cols = st.columns(4)
    status_colors = {
        "Open":          ("🟠", "Open"),
        "Investigating": ("🔵", "Investigating"),
        "Resolved":      ("🟢", "Resolved"),
        "Escalated":     ("🔴", "Escalated"),
    }
    for idx, (skey, (icon, label)) in enumerate(status_colors.items()):
        with qs_cols[idx]:
            is_current = target.status == skey
            btn_label  = f"{icon} {label} {'✓' if is_current else ''}"
            if st.button(btn_label, key=f"qs_{skey}", disabled=is_current,
                         use_container_width=True):
                with st.spinner(f"Setting status to {label}..."):
                    target.status = skey
                    session.commit()
                    # ── Google Sheets Sync ──
                    get_sheets_sync().sync_issue(target, action="UPDATE")
                st.toast(f"Status → {label}", icon=icon)
                st.rerun()

    # ── Email Trail Snapshot ─────────────────────
    issue_emails = session.query(EmailLog).filter_by(issue_id=target.id)\
                          .order_by(EmailLog.date_sent).all()
    if issue_emails:
        st.markdown("#### 📬 Email Communications Summary")
        for em in issue_emails:
            resp_count   = session.query(EmailResponse).filter_by(email_log_id=em.id).count()
            status_emoji = {"Responded": "✅", "No Response": "⏳",
                            "Follow-up Needed": "🔔"}.get(em.response_status, "❓")
            st.markdown(
                f"&nbsp;&nbsp;{status_emoji} **{em.subject}** → {em.recipient} "
                f"&nbsp;·&nbsp; {em.date_sent} "
                f"&nbsp;·&nbsp; {resp_count + 1} message(s) "
                f"&nbsp;·&nbsp; *{em.response_status}*",
                unsafe_allow_html=True
            )

    st.markdown("")
    if st.button(f"📧 Open Full Email Trail for {selected_id}",
                 help="Opens Email Tracker pre-filtered to this issue"):
        _navigate_to_emails(selected_id)

    st.markdown("---")

    # ── Full Update Form ─────────────────────────
    st.markdown("### ✏️ Update Issue Details")
    with st.form("update_issue_form"):
        u_col1, u_col2 = st.columns(2)
        with u_col1:
            new_status   = st.selectbox("Status",   STATUSES,
                                        index=STATUSES.index(target.status))
        with u_col2:
            new_priority = st.selectbox("Priority", PRIORITIES,
                                        index=PRIORITIES.index(target.priority))
        resolution = st.text_area("Resolution Notes / Update Details",
                                  value=target.resolution_notes or "")
        update_submitted = st.form_submit_button("💾 Save All Updates", type="primary")

    if update_submitted:
        with st.spinner("Saving..."):
            target.status           = new_status
            target.priority         = new_priority
            target.resolution_notes = resolution
            session.commit()
            # ── Google Sheets Sync ──
            get_sheets_sync().sync_issue(target, action="UPDATE")
        st.success(f"✅ {selected_id} updated successfully.")
        st.toast("Issue updated!", icon="💾")
        st.rerun()

    # ── Delete ───────────────────────────────────
    st.markdown("---")
    st.markdown("### 🗑️ Delete Issue")
    st.warning("⚠️ This permanently deletes the issue and ALL linked emails and responses.")
    confirm = st.checkbox(f"I confirm: permanently delete **{selected_id}** and all its data.")
    if st.button("🗑️ Delete Issue", type="primary", disabled=not confirm):
        with st.spinner("Deleting..."):
            # 1. Sheets Sync first (Cascading delete in cloud)
            get_sheets_sync().sync_issue(target, action="DELETE")
            
            # 2. Local Delete (SQLAlchemy Cascades handle EmailLogs and Responses)
            session.delete(target)
            session.commit()
        st.success(f"🗑️ Issue {selected_id} deleted.")
        st.toast("Issue deleted", icon="🗑️")
        st.rerun()

    session.close()
