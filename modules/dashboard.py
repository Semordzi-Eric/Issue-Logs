import streamlit as st
import pandas as pd
import plotly.express as px
from database.models import get_session, Issue

def render_dashboard():
    st.title("📊 Audit & Revenue Assurance Dashboard")
    st.markdown("---")

    session = get_session()
    
    # Fetch Data
    issues = session.query(Issue).all()
    session.close()

    if not issues:
        st.info("No audit logs found. Start by adding an issue in the 'Add Issue' tab.")
        return

    # Convert to DataFrame for easier analysis
    df = pd.DataFrame([{
        'Issue ID': i.issue_id,
        'Date': pd.to_datetime(i.date),
        'Category': i.category,
        'Priority': i.priority,
        'Status': i.status,
        'Amount': i.amount or 0.0
    } for i in issues])

    # 1. KPIs
    col1, col2, col3, col4 = st.columns(4)
    total_issues = len(df)
    open_issues = len(df[df['Status'] != 'Resolved'])
    resolved_issues = len(df[df['Status'] == 'Resolved'])
    total_revenue_impact = df['Amount'].sum()

    with col1:
        st.metric(label="Total Issues Logged", value=total_issues)
    with col2:
        st.metric(label="Open / Pending", value=open_issues, delta=f"{-resolved_issues} Resolved" if resolved_issues else None, delta_color="inverse")
    with col3:
        st.metric(label="Resolved", value=resolved_issues)
    with col4:
        st.metric(label="Est. Revenue Impact", value=f"₵{total_revenue_impact:,.2f}")

    st.markdown("<br>", unsafe_allow_html=True)

    # 2. Charts
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
            xaxis_title="", 
            yaxis_title="Issues"
        )
        st.plotly_chart(fig_time, use_container_width=False, width=900)

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
            showlegend=False,
            xaxis_title=""
        )
        st.plotly_chart(fig_bar, use_container_width=False, width=900)

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
        fig_pie_status.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig_pie_status, use_container_width=False, width=900)

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
        fig_pie_prio.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig_pie_prio, use_container_width=False, width=900)
