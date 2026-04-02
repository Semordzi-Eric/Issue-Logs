import gspread
from google.oauth2.service_account import Credentials
import os
import json
import streamlit as st
import datetime
from database.models import get_setting, set_setting

# Scopes required for Google Sheets API
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

class SheetsSync:
    REQUIRED_HEADERS = {
        "Issues": ["ID", "Issue ID", "Date", "Title", "Category", "Priority", "System", "Status", "Amount", "Root Cause", "Description", "Transaction ID"],
        "Email Logs": ["ID", "Issue ID", "Date Sent", "Recipient", "Subject", "Status", "Follow-up", "Summary"],
        "Responses": ["ID", "Email Log ID", "Issue ID", "Date", "Direction", "From/To", "Summary"]
    }

    def __init__(self, credentials_path='service_account.json', sheet_id=None):
        self.credentials_path = credentials_path
        self.sheet_id = sheet_id
        self.client = None
        self.spreadsheet = None

    def connect(self):
        """Authenticate and connect to the spreadsheet."""
        if not self.sheet_id: return False
        try:
            creds = None
            # Prioritize Streamlit Secrets
            try:
                if "gcp_service_account" in st.secrets:
                    creds_info = json.loads(st.secrets["gcp_service_account"], strict=False)
                    creds = Credentials.from_service_account_info(creds_info, scopes=SCOPES)
            except: pass
            
            # Fallback to local file
            if not creds and os.path.exists(self.credentials_path):
                creds = Credentials.from_service_account_file(self.credentials_path, scopes=SCOPES)
            
            if not creds: return False
            
            self.client = gspread.authorize(creds)
            self.spreadsheet = self.client.open_by_key(self.sheet_id)
            self.ensure_headers() # Validate structure on connect
            return True
        except Exception as e:
            st.error(f"Google Sheets Sync Error: {e}")
            return False

    def ensure_headers(self):
        """Ensure all required sheets and headers exist and match expected structure."""
        if not self.spreadsheet: return
        for name, expected in self.REQUIRED_HEADERS.items():
            try:
                ws = self.spreadsheet.worksheet(name)
                actual_headers = ws.row_values(1)
                
                # Check for missing headers
                missing = [h for h in expected if h not in actual_headers]
                if missing:
                    # Append missing headers to the end of the existing row
                    new_row = actual_headers + missing
                    ws.update("A1", [new_row])
                elif not actual_headers:
                    ws.append_row(expected)
            except gspread.exceptions.WorksheetNotFound:
                # Create it with correct headers
                ws = self.spreadsheet.add_worksheet(title=name, rows="100", cols=str(len(expected)))
                ws.append_row(expected)

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

    def _get_row_from_dict(self, ws, data_dict):
        """Construct a row list matching the worksheet's actual header order."""
        try:
            actual_headers = ws.row_values(1)
            # If empty, use our canonical ones as fallback
            if not actual_headers:
                actual_headers = self.REQUIRED_HEADERS.get(ws.title, [])
            
            row = []
            for h in actual_headers:
                row.append(data_dict.get(h, ""))
            return row
        except Exception:
            # Fallback to static list if header fetch fails
            return list(data_dict.values())

    def sync_issue(self, issue, action="INSERT"):
        """Sync an issue record to the 'Issues' sheet with robust mapping."""
        if not self.connect(): return
        try:
            sheet = self.spreadsheet.worksheet("Issues")
        except: return
        
        data = {
            "ID": issue.id, "Issue ID": issue.issue_id, "Date": str(issue.date), 
            "Title": issue.title, "Description": issue.description or "", 
            "Category": issue.category, "Priority": issue.priority, "System": issue.affected_system, 
            "Transaction ID": issue.transaction_id or "", "Amount": issue.amount or 0, 
            "Root Cause": issue.root_cause or "", "Status": issue.status
        }
        row_data = self._get_row_from_dict(sheet, data)

        if action == "INSERT":
            sheet.append_row(row_data)
        elif action == "UPDATE":
            try:
                cell = sheet.find(str(issue.issue_id), in_column=2)
                if cell:
                    # Update row (dynamic column mapping handles position)
                    sheet.update(f"A{cell.row}", [row_data])
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
        """Sync an email log to the 'Email Logs' sheet with robust mapping."""
        if not self.connect(): return
        try:
            sheet = self.spreadsheet.worksheet("Email Logs")
        except: return
        
        if action == "INSERT":
            data = {
                "ID": email.id, "Issue ID": issue_id_str, "Date Sent": str(email.date_sent), 
                "Recipient": email.recipient, "Subject": email.subject, "Status": email.response_status,
                "Follow-up": str(email.follow_up_date) if email.follow_up_date else "",
                "Summary": email.email_summary
            }
            row_data = self._get_row_from_dict(sheet, data)
            sheet.append_row(row_data)
        elif action == "UPDATE":
            try:
                cell = sheet.find(str(email.id), in_column=1)
                if cell:
                    # Map headers for partial update
                    headers = sheet.row_values(1)
                    if "Status" in headers:
                        sheet.update_cell(cell.row, headers.index("Status") + 1, email.response_status)
                    if "Follow-up" in headers:
                        sheet.update_cell(cell.row, headers.index("Follow-up") + 1, str(email.follow_up_date) if email.follow_up_date else "")
            except gspread.exceptions.CellNotFound:
                # If not found, insert as fallback
                self.sync_email(email, issue_id_str, action="INSERT")
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
        """Sync an email response to the 'Responses' sheet with robust mapping."""
        if not self.connect(): return
        try:
            sheet = self.spreadsheet.worksheet("Responses")
        except: return
        
        if action == "INSERT":
            data = {
                "ID": response.id, "Email Log ID": response.email_log_id, "Issue ID": issue_id_str,
                "Date": str(response.date), "Direction": response.direction, 
                "From/To": response.from_to, "Summary": response.summary
            }
            row_data = self._get_row_from_dict(sheet, data)
            sheet.append_row(row_data)

    def pull_all_data(self):
        """Fetch all data from Google Sheets to populate local SQLite."""
        if not self.connect(): return None
        
        # Proactively ensure all required headers exist before pulling
        self.ensure_headers()
        
        data = {"issues": [], "emails": [], "responses": []}
        
        # Helper to safely parse dates
        def safe_date(val):
            if not val or val == "": return None
            try:
                # If already a date object (less likely from get_all_records but safe)
                if isinstance(val, (datetime.date, datetime.datetime)):
                    return val.date() if isinstance(val, datetime.datetime) else val
                return datetime.datetime.strptime(str(val), "%Y-%m-%d").date()
            except:
                return None

        # 1. Pull Issues
        try:
            issues_sheet = self.spreadsheet.worksheet("Issues")
            # Always ensure headers before pull to be robust
            rows = issues_sheet.get_all_records(expected_headers=self.REQUIRED_HEADERS["Issues"])
            for r in rows:
                r["Date"] = safe_date(r.get("Date"))
                data["issues"].append(r)
        except gspread.exceptions.WorksheetNotFound: pass

        # 2. Pull Email Logs
        try:
            emails_sheet = self.spreadsheet.worksheet("Email Logs")
            rows = emails_sheet.get_all_records(expected_headers=self.REQUIRED_HEADERS["Email Logs"])
            for r in rows:
                r["Date Sent"] = safe_date(r.get("Date Sent"))
                r["Follow-up"] = safe_date(r.get("Follow-up"))
                data["emails"].append(r)
        except gspread.exceptions.WorksheetNotFound: pass

        # 3. Pull Responses
        try:
            resp_sheet = self.spreadsheet.worksheet("Responses")
            rows = resp_sheet.get_all_records(expected_headers=self.REQUIRED_HEADERS["Responses"])
            for r in rows:
                r["Date"] = safe_date(r.get("Date"))
                data["responses"].append(r)
        except gspread.exceptions.WorksheetNotFound: pass
        
        # Record sync time for Dashboard
        set_setting("last_sync_time", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        return data

    def full_sync(self, all_issues, all_emails, all_responses, issue_map):
        """Initial sync to push ALL local data to the sheet."""
        if not self.connect(): return

        # Issues
        issues_sheet = self.spreadsheet.worksheet("Issues")
        issues_sheet.clear()
        issues_sheet.append_row(self.REQUIRED_HEADERS["Issues"])
        issue_rows = []
        for i in all_issues:
            data = {
                "ID": i.id, "Issue ID": i.issue_id, "Date": str(i.date), 
                "Title": i.title, "Description": i.description or "", 
                "Category": i.category, "Priority": i.priority, "System": i.affected_system, 
                "Transaction ID": i.transaction_id or "", "Amount": i.amount or 0, 
                "Root Cause": i.root_cause or "", "Status": i.status
            }
            issue_rows.append(self._get_row_from_dict(issues_sheet, data))
        
        if issue_rows: issues_sheet.append_rows(issue_rows)

        # Email Logs
        emails_sheet = self.spreadsheet.worksheet("Email Logs")
        emails_sheet.clear()
        emails_sheet.append_row(self.REQUIRED_HEADERS["Email Logs"])
        email_rows = []
        for e in all_emails:
            data = {
                "ID": e.id, "Issue ID": issue_map.get(e.issue_id, "N/A"), "Date Sent": str(e.date_sent), 
                "Recipient": e.recipient, "Subject": e.subject, "Status": e.response_status, 
                "Follow-up": str(e.follow_up_date or ""), "Summary": e.email_summary
            }
            email_rows.append(self._get_row_from_dict(emails_sheet, data))
            
        if email_rows: emails_sheet.append_rows(email_rows)

        # Responses
        resp_sheet = self.spreadsheet.worksheet("Responses")
        resp_sheet.clear()
        resp_sheet.append_row(self.REQUIRED_HEADERS["Responses"])
        resp_rows = []
        for r in all_responses:
            data = {
                "ID": r.id, "Email Log ID": r.email_log_id, "Issue ID": issue_map.get(r.email_log_id, "N/A"), 
                "Date": str(r.date), "Direction": r.direction, "From/To": r.from_to, "Summary": r.summary
            }
            resp_rows.append(self._get_row_from_dict(resp_sheet, data))
        
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
