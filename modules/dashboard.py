import streamlit as st
import pandas as pd
import plotly.express as px
from database.models import get_session, Issue, EmailLog, get_setting

def render_dashboard():
    st.title("📊 Audit & Revenue Assurance Dashboard")
    st.markdown("---")

    session = get_session()
    issues = session.query(Issue).all()
    emails = session.query(EmailLog).all()
    session.close()

    last_sync = get_setting("last_sync_time", "Never")
    st.caption(f"☁️ **Last Cloud Sync:** {last_sync}")

    if not issues:
        st.info("No audit logs found. Start by adding an issue in the **Log New Issue** tab.")
        return

    df = pd.DataFrame([{
        'Issue ID': i.issue_id,
        'Date': pd.to_datetime(i.date),
        'Category': i.category,
        'Priority': i.priority,
        'Status': i.status,
        'Amount': i.amount or 0.0
    } for i in issues])

    # ── KPI Row 1 — Issues ───────────────────────
    st.markdown("#### 📌 Issue Overview")
    col1, col2, col3, col4 = st.columns(4)
    total_issues        = len(df)
    open_issues         = len(df[df['Status'] != 'Resolved'])
    resolved_issues     = len(df[df['Status'] == 'Resolved'])
    total_revenue_impact = df['Amount'].sum()

    col1.metric("Total Issues Logged",  total_issues)
    col2.metric("Open / Pending",       open_issues,
                delta=f"-{resolved_issues} Resolved" if resolved_issues else None,
                delta_color="inverse")
    col3.metric("Resolved",             resolved_issues)
    col4.metric("Est. Revenue Impact",  f"₵{total_revenue_impact:,.2f}")

    # ── KPI Row 2 — Emails ───────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("#### 📧 Communications Overview")
    e_col1, e_col2, e_col3, e_col4 = st.columns(4)
    total_emails   = len(emails)
    responded      = sum(1 for e in emails if e.response_status == "Responded")
    pending        = sum(1 for e in emails if e.response_status == "No Response")
    follow_up      = sum(1 for e in emails if e.response_status == "Follow-up Needed")

    e_col1.metric("Total Emails Logged", total_emails)
    e_col2.metric("✅ Responded",         responded)
    e_col3.metric("⏳ No Response",       pending)
    e_col4.metric("🔔 Follow-up Needed",  follow_up)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Charts ───────────────────────────────────
    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:
        st.subheader("Issues Over Time")
        daily_counts = df.groupby('Date').size().reset_index(name='Count')
        fig_time = px.line(
            daily_counts, x='Date', y='Count',
            markers=True, line_shape='spline',
            color_discrete_sequence=['#4CAF50']
        )
        fig_time.update_layout(
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            xaxis_title="", yaxis_title="Issues",
            font=dict(color="#E8EAF0"),
            margin=dict(l=10, r=10, t=10, b=10)
        )
        st.plotly_chart(fig_time, use_container_width=True)

    with chart_col2:
        st.subheader("Issues by Category")
        cat_counts = df['Category'].value_counts().reset_index()
        cat_counts.columns = ['Category', 'Count']
        fig_bar = px.bar(
            cat_counts, x='Category', y='Count',
            color='Category',
            color_discrete_sequence=px.colors.qualitative.Pastel
        )
        fig_bar.update_layout(
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            showlegend=False, xaxis_title="",
            font=dict(color="#E8EAF0"),
            margin=dict(l=10, r=10, t=10, b=10)
        )
        st.plotly_chart(fig_bar, use_container_width=True)

    chart_col3, chart_col4 = st.columns(2)

    with chart_col3:
        st.subheader("Status Distribution")
        status_counts = df['Status'].value_counts().reset_index()
        status_counts.columns = ['Status', 'Count']
        fig_pie_status = px.pie(
            status_counts, names='Status', values='Count', hole=0.4,
            color='Status',
            color_discrete_map={
                'Open': '#FFB74D', 'Investigating': '#64B5F6',
                'Resolved': '#81C784', 'Escalated': '#E57373'
            }
        )
        fig_pie_status.update_layout(
            plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
            font=dict(color="#E8EAF0"), margin=dict(l=10, r=10, t=10, b=10)
        )
        st.plotly_chart(fig_pie_status, use_container_width=True)

    with chart_col4:
        st.subheader("Priority Levels")
        prio_counts = df['Priority'].value_counts().reset_index()
        prio_counts.columns = ['Priority', 'Count']
        fig_pie_prio = px.pie(
            prio_counts, names='Priority', values='Count',
            color='Priority',
            color_discrete_map={
                'Critical': '#D32F2F', 'High': '#F57C00',
                'Medium': '#FBC02D', 'Low': '#388E3C'
            }
        )
        fig_pie_prio.update_layout(
            plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
            font=dict(color="#E8EAF0"), margin=dict(l=10, r=10, t=10, b=10)
        )
        st.plotly_chart(fig_pie_prio, use_container_width=True)

    # ── Recent Issues Table ───────────────────────
    st.markdown("---")
    st.markdown("#### 🕒 Recent Issues (Last 10)")
    recent = df.sort_values('Date', ascending=False).head(10)
    st.dataframe(recent[['Issue ID','Date','Category','Priority','Status','Amount']],
                 hide_index=True, use_container_width=True)
