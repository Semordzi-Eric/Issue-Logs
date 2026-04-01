import gspread
from google.oauth2.service_account import Credentials
import os
import json
import streamlit as st
import datetime
from database.models import get_setting

# Scopes required for Google Sheets API
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

class SheetsSync:
    def __init__(self, credentials_path='service_account.json', sheet_id=None):
        self.credentials_path = credentials_path
        self.sheet_id = sheet_id
        self.client = None
        self.spreadsheet = None

    def connect(self):
        """ESTABLISH CONNECTION TO GOOGLE SHEETS."""
        creds = None
        
        # 1. Check Streamlit Secrets (Recommended for Cloud Deployment)
        try:
            if "gcp_service_account" in st.secrets:
                creds_info = st.secrets["gcp_service_account"]
                if isinstance(creds_info, str):
                    creds_info = json.loads(creds_info)
                creds = Credentials.from_service_account_info(creds_info, scopes=SCOPES)
        except Exception:
            # Fallback for local dev if secrets.toml doesn't exist or other error
            pass
        
        # 2. Fallback to Local JSON File (Recommended for Local Dev)
        if not creds and os.path.exists(self.credentials_path):
            try:
                creds = Credentials.from_service_account_file(self.credentials_path, scopes=SCOPES)
            except Exception as e:
                st.error(f"❌ Google Sheets: Error reading {self.credentials_path}: {e}")

        if not creds:
            st.warning(f"⚠️ Google Sheets Sync: No credentials found (check Secrets or `{self.credentials_path}`). Sync disabled.")
            return False
            
        if not self.sheet_id:
            st.warning("⚠️ Google Sheets Sync: Spreadsheet ID not configured. Sync disabled.")
            return False

        try:
            self.client = gspread.authorize(creds)
            self.spreadsheet = self.client.open_by_key(self.sheet_id)
            return True
        except Exception as e:
            st.error(f"❌ Google Sheets Connection Error: {str(e)}")
            return False

    def _get_or_create_worksheet(self, title, headers):
        """Get an existing worksheet or create it with headers if not found."""
        try:
            sheet = self.spreadsheet.worksheet(title)
        except gspread.exceptions.WorksheetNotFound:
            sheet = self.spreadsheet.add_worksheet(title=title, rows="1000", cols=len(headers) + 2)
            sheet.insert_row(headers, 1)
            # Bold headers
            sheet.format("A1:Z1", {"textFormat": {"bold": True}})
        return sheet

    def sync_issue(self, issue, action="INSERT"):
        """Sync a single issue to the 'Issues' tab."""
        if not self.connect(): return

        headers = [
            "ID", "Issue ID", "Date", "Title", "Category", 
            "Priority", "System", "Status", "Amount", "Root Cause"
        ]
        sheet = self._get_or_create_worksheet("Issues", headers)
        
        row_data = [
            issue.id, issue.issue_id, str(issue.date), issue.title, issue.category,
            issue.priority, issue.affected_system, issue.status, issue.amount or 0, issue.root_cause or ""
        ]

        if action == "INSERT":
            sheet.append_row(row_data)
        elif action == "UPDATE":
            try:
                cell = sheet.find(str(issue.issue_id), in_column=2)
                if cell:
                    sheet.update(f"A{cell.row}:J{cell.row}", [row_data])
                else:
                    sheet.append_row(row_data)
            except gspread.exceptions.CellNotFound:
                sheet.append_row(row_data)
        elif action == "DELETE":
            try:
                # 1. Delete Issue
                cell = sheet.find(str(issue.issue_id), in_column=2)
                if cell:
                    sheet.delete_rows(cell.row)
                
                # 2. Cascading Delete: Email Logs
                try:
                    email_sheet = self.spreadsheet.worksheet("Email Logs")
                    # Find all rows matched by Issue ID in column 2
                    email_cells = email_sheet.findall(str(issue.issue_id), in_column=2)
                    # Delete rows from bottom to top to avoid index shifting
                    for c in sorted(email_cells, key=lambda x: x.row, reverse=True):
                        email_sheet.delete_rows(c.row)
                except gspread.exceptions.WorksheetNotFound: pass

                # 3. Cascading Delete: Responses
                try:
                    resp_sheet = self.spreadsheet.worksheet("Responses")
                    resp_cells = resp_sheet.findall(str(issue.issue_id), in_column=3) # Issue ID is col 3 in Responses
                    for c in sorted(resp_cells, key=lambda x: x.row, reverse=True):
                        resp_sheet.delete_rows(c.row)
                except gspread.exceptions.WorksheetNotFound: pass

            except gspread.exceptions.CellNotFound:
                pass

    def sync_email(self, email, issue_id_str, action="INSERT"):
        """Sync an email log to the 'Email Logs' tab."""
        if not self.connect(): return

        headers = ["ID", "Issue ID", "Date Sent", "Recipient", "Subject", "Status", "Follow-up", "Summary"]
        sheet = self._get_or_create_worksheet("Email Logs", headers)
        
        row_data = [
            email.id, issue_id_str, str(email.date_sent), email.recipient, 
            email.subject, email.response_status, str(email.follow_up_date or ""), email.email_summary
        ]

        if action == "INSERT":
            sheet.append_row(row_data)
        elif action == "UPDATE":
            try:
                # Find by local ID (column 1)
                cell = sheet.find(str(email.id), in_column=1)
                if cell:
                    sheet.update(f"A{cell.row}:H{cell.row}", [row_data])
                else:
                    sheet.append_row(row_data)
            except gspread.exceptions.CellNotFound:
                sheet.append_row(row_data)
        elif action == "DELETE":
            try:
                # 1. Delete Email Log
                cell = sheet.find(str(email.id), in_column=1)
                if cell:
                    sheet.delete_rows(cell.row)
                
                # 2. Cascading Delete: Responses (via Email Log ID)
                try:
                    resp_sheet = self.spreadsheet.worksheet("Responses")
                    resp_cells = resp_sheet.findall(str(email.id), in_column=2) # Email Log ID is col 2
                    for c in sorted(resp_cells, key=lambda x: x.row, reverse=True):
                        resp_sheet.delete_rows(c.row)
                except gspread.exceptions.WorksheetNotFound: pass

            except gspread.exceptions.CellNotFound:
                pass

    def sync_response(self, response, issue_id_str, action="INSERT"):
        """Sync an email response to the 'Responses' tab."""
        if not self.connect(): return

        headers = ["ID", "Email Log ID", "Issue ID", "Date", "Direction", "From/To", "Summary"]
        sheet = self._get_or_create_worksheet("Responses", headers)
        
        row_data = [
            response.id, response.email_log_id, issue_id_str, str(response.date), 
            response.direction, response.from_to, response.summary
        ]

        if action == "INSERT":
            sheet.append_row(row_data)

    def pull_all_data(self):
        """Fetch all data from Google Sheets to populate local SQLite."""
        if not self.connect(): return None
        
        data = {"issues": [], "emails": [], "responses": []}
        
        # 1. Pull Issues
        try:
            issues_sheet = self.spreadsheet.worksheet("Issues")
            rows = issues_sheet.get_all_records()
            for r in rows:
                # Handle types
                if r.get("Date"):
                    # Cast string '2025-03-31' to date object
                    try:
                        r["Date"] = datetime.datetime.strptime(str(r["Date"]), "%Y-%m-%d").date()
                    except: pass
                data["issues"].append(r)
        except gspread.exceptions.WorksheetNotFound: pass

        # 2. Pull Email Logs
        try:
            emails_sheet = self.spreadsheet.worksheet("Email Logs")
            rows = emails_sheet.get_all_records()
            for r in rows:
                if r.get("Date Sent"):
                    try:
                        r["Date Sent"] = datetime.datetime.strptime(str(r["Date Sent"]), "%Y-%m-%d").date()
                    except: pass
                if r.get("Follow-up") and r["Follow-up"] != "":
                    try:
                        r["Follow-up"] = datetime.datetime.strptime(str(r["Follow-up"]), "%Y-%m-%d").date()
                    except: pass
                data["emails"].append(r)
        except gspread.exceptions.WorksheetNotFound: pass

        # 3. Pull Responses
        try:
            resp_sheet = self.spreadsheet.worksheet("Responses")
            rows = resp_sheet.get_all_records()
            for r in rows:
                if r.get("Date"):
                    try:
                        r["Date"] = datetime.datetime.strptime(str(r["Date"]), "%Y-%m-%d").date()
                    except: pass
                data["responses"].append(r)
        except gspread.exceptions.WorksheetNotFound: pass
        
        return data

    def full_sync(self, all_issues, all_emails, all_responses, issue_map):
        """Initial sync to push ALL local data to the sheet."""
        if not self.connect(): return

        # Issues
        issues_sheet = self._get_or_create_worksheet("Issues", ["ID", "Issue ID", "Date", "Title", "Category", "Priority", "System", "Status", "Amount", "Root Cause"])
        issues_sheet.clear()
        issues_sheet.append_row(["ID", "Issue ID", "Date", "Title", "Category", "Priority", "System", "Status", "Amount", "Root Cause"])
        issue_rows = [[i.id, i.issue_id, str(i.date), i.title, i.category, i.priority, i.affected_system, i.status, i.amount or 0, i.root_cause or ""] for i in all_issues]
        if issue_rows: issues_sheet.append_rows(issue_rows)

        # Email Logs
        emails_sheet = self._get_or_create_worksheet("Email Logs", ["ID", "Issue ID", "Date Sent", "Recipient", "Subject", "Status", "Follow-up", "Summary"])
        emails_sheet.clear()
        emails_sheet.append_row(["ID", "Issue ID", "Date Sent", "Recipient", "Subject", "Status", "Follow-up", "Summary"])
        email_rows = [[e.id, issue_map.get(e.issue_id, "N/A"), str(e.date_sent), e.recipient, e.subject, e.response_status, str(e.follow_up_date or ""), e.email_summary] for e in all_emails]
        if email_rows: emails_sheet.append_rows(email_rows)

        # Responses
        resp_sheet = self._get_or_create_worksheet("Responses", ["ID", "Email Log ID", "Issue ID", "Date", "Direction", "From/To", "Summary"])
        resp_sheet.clear()
        resp_sheet.append_row(["ID", "Email Log ID", "Issue ID", "Date", "Direction", "From/To", "Summary"])
        resp_rows = []
        for r in all_responses:
            resp_rows.append([r.id, r.email_log_id, issue_map.get(r.email_log_id, "N/A"), str(r.date), r.direction, r.from_to, r.summary])
        if resp_rows: resp_sheet.append_rows(resp_rows)

def get_sheets_sync():
    """Helper to get a SheetsSync instance, prioritizing Streamlit Secrets for persistence."""
    # 1. Highest priority: Streamlit Secrets (Survives reboots)
    sheet_id = None
    try:
        if "gs_sheet_id" in st.secrets:
            sheet_id = st.secrets["gs_sheet_id"]
    except: pass

    # 2. Second priority: Database
    if not sheet_id:
        sheet_id = get_setting("gs_sheet_id")
    
    # 3. Third priority: Session state
    if not sheet_id:
        sheet_id = st.session_state.get("gs_sheet_id", "")
    
    return SheetsSync(sheet_id=sheet_id)
