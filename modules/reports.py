import streamlit as st
import pandas as pd
from docx import Document
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import io
import datetime
from database.models import get_session, Issue

def generate_word_report(df, month_year):
    doc = Document()
    doc.add_heading(f'Audit & Revenue Assurance Monthly Report - {month_year}', 0)
    
    # Executive Summary
    doc.add_heading('Executive Summary', level=1)
    
    total_issues = len(df)
    resolved = len(df[df['Status'] == 'Resolved'])
    total_amount = df['Amount'].sum()
    
    doc.add_paragraph(
        f"During the month of {month_year}, a total of {total_issues} issues were logged. "
        f"Out of these, {resolved} have been successfully resolved. "
        f"The total estimated revenue impact identified stands at GHS ₵{total_amount:,.2f}."
    )
    
    # By Category
    doc.add_heading('Breakdown by Category', level=1)
    cat_counts = df['Category'].value_counts()
    for cat, count in cat_counts.items():
        doc.add_paragraph(f"- {cat}: {count} issue(s)", style='List Bullet')
        
    # Key Incidents (Critical / High)
    doc.add_heading('Key Incidents (Critical & High Priority)', level=1)
    high_priority = df[df['Priority'].isin(['High', 'Critical'])]
    
    if not high_priority.empty:
        for idx, row in high_priority.iterrows():
            p = doc.add_paragraph(style='List Bullet')
            p.add_run(f"[{row['Issue ID']}] {row['Title']}: ").bold = True
            p.add_run(f"Affected {row['Affected System']}, Status: {row['Status']}")
    else:
        doc.add_paragraph("No high or critical priority incidents reported this month.")
        
    # Outstanding Issues
    doc.add_heading('Outstanding Issues requiring follow-up', level=1)
    open_issues = df[df['Status'] != 'Resolved']
    
    if not open_issues.empty:
        for idx, row in open_issues.iterrows():
            doc.add_paragraph(f"[{row['Issue ID']}] {row['Title']} - Status: {row['Status']}", style='List Number')
    else:
        doc.add_paragraph("No outstanding issues. Excellent work.")

    doc.add_heading('Recommendations', level=1)
    doc.add_paragraph("1. Continue monitoring failed transactions across major payment channels.")
    doc.add_paragraph("2. Ensure all 'Open' issues have an assigned owner for follow-up.")

    bio = io.BytesIO()
    doc.save(bio)
    return bio.getvalue()

def generate_pdf_report(df, month_year):
    # A simplified PDF generation with reportlab
    bio = io.BytesIO()
    c = canvas.Canvas(bio, pagesize=letter)
    width, height = letter
    
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, height - 50, f"Audit Monthly Report - {month_year}")
    
    c.setFont("Helvetica", 12)
    y = height - 80
    
    total_issues = len(df)
    total_amount = df['Amount'].sum()
    
    lines = [
        "Executive Summary:",
        f"Total Issues: {total_issues}",
        f"Estimated Revenue Impact: GHS ₵{total_amount:,.2f}",
        "",
        "Categories Breakdown:"
    ]
    
    cat_counts = df['Category'].value_counts()
    for cat, count in cat_counts.items():
        lines.append(f"- {cat}: {count}")
        
    lines.append("")
    lines.append("Key Incidents:")
    
    high_priority = df[df['Priority'].isin(['High', 'Critical'])]
    for idx, row in high_priority.iterrows():
        id_title = f"{row['Issue ID']} - {row['Title']} ({row['Status']})"
        if len(id_title) > 80:
            id_title = id_title[:77] + "..."
        lines.append(f"- {id_title}")
        
    for line in lines:
        c.drawString(50, y, line)
        y -= 20
        if y < 50:
            c.showPage()
            c.setFont("Helvetica", 12)
            y = height - 50
    
    c.save()
    return bio.getvalue()

def render_reports():
    st.title("📄 Monthly Audit Reports")
    st.markdown("Generate and export structured monthly audit reports.")
    st.markdown("---")
    
    session = get_session()
    issues = session.query(Issue).all()
    session.close()
    
    if not issues:
        st.info("No audit data available to generate reports.")
        return
        
    df = pd.DataFrame([{
        'Issue ID': i.issue_id,
        'Date': pd.to_datetime(i.date),
        'Title': i.title,
        'Category': i.category,
        'Priority': i.priority,
        'Affected System': i.affected_system,
        'Status': i.status,
        'Amount': i.amount or 0.0
    } for i in issues])
    
    df['Month-Year'] = df['Date'].dt.strftime('%B %Y')
    available_months = df['Month-Year'].unique().tolist()
    
    st.subheader("Report Generator")
    
    col_r1, col_r2 = st.columns(2)
    
    with col_r1:
        selected_month = st.selectbox("Select Month for Report", available_months)
        
    month_data = df[df['Month-Year'] == selected_month]
    
    st.markdown(f"**Data points ready for {selected_month}: {len(month_data)} issues found.**")
    
    st.write("### Preview - Executive Data")
    prev_col1, prev_col2, prev_col3 = st.columns(3)
    prev_col1.metric("Issues in Month", len(month_data))
    prev_col2.metric("Critical / High", len(month_data[month_data['Priority'].isin(['High', 'Critical'])]))
    prev_col3.metric("Revenue Impact", f"₵{month_data['Amount'].sum():,.2f}")
    
    st.markdown("### Export Report")
    exp_col1, exp_col2, exp_col3 = st.columns(3)
    
    # Word DOCX
    docx_data = generate_word_report(month_data, selected_month)
    with exp_col1:
        st.download_button(
            label="📄 Download Word (DOCX)",
            data=docx_data,
            file_name=f"Audit_Report_{selected_month.replace(' ', '_')}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            type="primary"
        )
        
    # PDF
    pdf_data = generate_pdf_report(month_data, selected_month)
    with exp_col2:
        st.download_button(
            label="📕 Download PDF",
            data=pdf_data,
            file_name=f"Audit_Report_{selected_month.replace(' ', '_')}.pdf",
            mime="application/pdf"
        )
        
    # CSV Data
    csv_data = month_data.to_csv(index=False).encode('utf-8')
    with exp_col3:
        st.download_button(
            label="📊 Download Excel/CSV Data",
            data=csv_data,
            file_name=f"Audit_Data_{selected_month.replace(' ', '_')}.csv",
            mime="text/csv"
        )
