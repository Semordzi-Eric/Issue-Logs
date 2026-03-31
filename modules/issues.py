import streamlit as st
import pandas as pd
from database.models import get_session, Issue
from utils.helpers import generate_issue_id, predict_category
from utils.styling import render_status_badge

CATEGORIES = [
    "Revenue Leakage", "Failed Transactions", "Suspicious Activity",
    "Reversals", "Reprocessed", "System Errors", "Others"
]

PRIORITIES = ["Low", "Medium", "High", "Critical"]
STATUSES = ["Open", "Investigating", "Resolved", "Escalated"]

def render_add_issue():
    st.title("📝 Log New Audit Issue")
    st.markdown("Use this form to track new findings or incidents.")
    st.markdown("---")

    with st.form("new_issue_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            title = st.text_input("Issue Title*", help="A short, descriptive title")
            date = st.date_input("Date Found*")
            
        with col2:
            affected_system = st.text_input("Affected System / Channel*", help="e.g., POS, Mobile App, Core Banking")
            priority = st.selectbox("Priority*", PRIORITIES, index=1)
            
        description = st.text_area("Issue Description*", help="Detailed explanation of the finding", height=150)
        
        # Auto-predict category
        suggested_category = predict_category(description) if description else "Others"
        cat_index = CATEGORIES.index(suggested_category) if suggested_category in CATEGORIES else 5
        
        col3, col4 = st.columns(2)
        with col3:
            category = st.selectbox("Category*", CATEGORIES, index=cat_index)
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
                st.success(f"Issue {new_issue.issue_id} logged successfully!")
                session.close()

def render_manage_issues():
    st.title("🔍 Manage & Filter Issues")
    
    session = get_session()
    issues = session.query(Issue).all()
    
    if not issues:
        st.info("No issues found. Go to 'Add Issue' to create one.")
        session.close()
        return
        
    # Convert to DataFrame
    data = []
    for i in issues:
        data.append({
            "ID": i.id, # hidden mostly
            "Issue ID": i.issue_id,
            "Date": i.date,
            "Title": i.title,
            "Category": i.category,
            "Priority": i.priority,
            "Status": i.status,
            "Amount": f"₵{i.amount:,.2f}" if i.amount else "-"
        })
    df = pd.DataFrame(data)
    
    # Filters
    st.markdown("### Filters")
    f_col1, f_col2, f_col3 = st.columns(3)
    
    with f_col1:
        f_status = st.multiselect("Status", STATUSES, default=[])
    with f_col2:
        f_priority = st.multiselect("Priority", PRIORITIES, default=[])
    with f_col3:
        f_search = st.text_input("Search (Title/ID)")
        
    # Apply filters
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
    
    # Display table without ID column
    disp_df = filtered_df.drop(columns=['ID'])
    st.dataframe(disp_df, hide_index=True)
    
    st.markdown("### Update an Issue")
    
    # Quick Status Update Form
    if not filtered_df.empty:
        update_col1, update_col2 = st.columns(2)
        with update_col1:
            selected_issue_id = st.selectbox("Select Issue to Update", filtered_df['Issue ID'].tolist())
        
        target_issue = session.query(Issue).filter_by(issue_id=selected_issue_id).first()
        
        if target_issue:
            with st.form("update_issue_form"):
                u_col1, u_col2 = st.columns(2)
                with u_col1:
                    new_status = st.selectbox("New Status", STATUSES, index=STATUSES.index(target_issue.status))
                with u_col2:
                    new_priority = st.selectbox("Update Priority", PRIORITIES, index=PRIORITIES.index(target_issue.priority))
                    
                resolution = st.text_area("Resolution Notes / Update Details", value=target_issue.resolution_notes or "")
                
                upd_submitted = st.form_submit_button("Save Updates")
                
                if upd_submitted:
                    target_issue.status = new_status
                    target_issue.priority = new_priority
                    target_issue.resolution_notes = resolution
                    session.commit()
                    st.success(f"Successfully updated {target_issue.issue_id}!")
                    st.rerun()

    st.markdown("---")
    st.markdown("### 🗑️ Delete an Issue")
    st.warning("⚠️ Deleting an issue will also remove all linked email logs. This action cannot be undone.")

    if not filtered_df.empty:
        del_col1, del_col2 = st.columns([3, 1])
        with del_col1:
            del_issue_id = st.selectbox("Select Issue to Delete", filtered_df['Issue ID'].tolist(), key="delete_select")
        
        confirm_delete = st.checkbox(f"I confirm I want to permanently delete **{del_issue_id}** and all its linked emails.")
        
        if st.button("🗑️ Delete Issue", type="primary", disabled=not confirm_delete):
            del_target = session.query(Issue).filter_by(issue_id=del_issue_id).first()
            if del_target:
                # Cascade delete linked email logs
                from database.models import EmailLog
                session.query(EmailLog).filter_by(issue_id=del_target.id).delete()
                session.delete(del_target)
                session.commit()
                st.success(f"Issue {del_issue_id} and its linked emails have been deleted.")
                st.rerun()
                    
    session.close()
