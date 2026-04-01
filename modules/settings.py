import streamlit as st
import os
import json
from database.sheets_sync import SheetsSync, get_sheets_sync
from database.models import get_session, Issue, EmailLog, EmailResponse, reload_from_sheets_data

def render_settings():
    st.title("⚙️ Settings & External Sync")
    st.markdown("---")

    st.subheader("📊 Google Sheets External Database")
    st.caption("Synchronize your local audit logs with a Google Sheet for external visibility and reporting.")

    # ── Configuration Form ────────────────────────
    with st.expander("🛠️ API Configuration", expanded=True):
        st.markdown("#### 1. Spreadsheet ID")
        current_id = st.session_state.get("gs_sheet_id", "")
        sheet_id = st.text_input(
            "Enter Google Sheet ID*",
            value=current_id,
            help="The long string of characters in the Sheet URL after /d/",
            placeholder="e.g. 1aBC-dEf_GhIjKlMnOpQrStUvWxYz",
        )

        st.markdown("#### 2. Service Account Credentials")
        
        # Check both local file and Streamlit secrets
        file_exists = os.path.exists("service_account.json")
        secrets_exists = False
        try:
            if "gcp_service_account" in st.secrets:
                secrets_exists = True
        except:
            pass

        if secrets_exists:
            st.success("✅ **Cloud Secrets Detected**: `gcp_service_account` found in Streamlit Cloud.")
        elif file_exists:
            st.success("✅ **Local File Detected**: `service_account.json` found in root directory.")
        else:
            st.error("❌ **No Credentials Found**")
            st.info(
                "💡 **How to set up:**  \n"
                "**Local:** Place `service_account.json` in the `LOGS/` folder.  \n"
                "**Cloud:** Add your JSON content to Streamlit Cloud **Secrets** as `gcp_service_account`."
            )

        creds_ready = file_exists or secrets_exists

        if st.button("💾 Save Configuration", type="primary"):
            st.session_state.gs_sheet_id = sheet_id
            st.success("Configuration saved!")
            st.rerun()

    st.markdown("---")

    # ── Connection Test & Initial Sync ─────────────
    st.subheader("🚀 Operations")
    col1, col2 = st.columns(2)

    with col1:
        if st.button("🔌 Test Connection", use_container_width=True):
            if not sheet_id or not creds_ready:
                st.warning("Please complete the configuration first.")
            else:
                with st.spinner("Testing connection..."):
                    sync = SheetsSync(sheet_id=sheet_id)
                    if sync.connect():
                        st.success("✅ Successfully connected to Google Sheet!")
                        st.toast("Connection successful!", icon="✅")
                    else:
                        st.error("❌ Connection failed. Check logs or credentials.")

    with col2:
        tooltip = "Sync all existing local data to the Google Sheet. This will overwrite existing data in the sheet."
        if st.button("📤 Push All (Local → Cloud)", use_container_width=True, help=tooltip):
            if not sheet_id:
                st.warning("Sheet ID not set.")
            else:
                with st.spinner("Pushing all data to Google Sheets..."):
                    session = get_session()
                    try:
                        all_issues    = session.query(Issue).all()
                        all_emails    = session.query(EmailLog).all()
                        all_responses = session.query(EmailResponse).all()
                        issue_map = {i.id: i.issue_id for i in all_issues}
                        sync = SheetsSync(sheet_id=sheet_id)
                        sync.full_sync(all_issues, all_emails, all_responses, issue_map)
                        st.success(f"✅ Full Push complete!")
                        st.toast("Push complete!", icon="📤")
                    except Exception as e:
                        st.error(f"❌ Push failed: {str(e)}")
                    finally:
                        session.close()

    st.markdown("---")
    st.subheader("📥 Cloud Recovery")
    st.caption("Pull data from Google Sheets to restore your local database. Use this to restore data on a new deployment.")
    
    if st.button("📥 Pull All (Cloud → Local)", type="primary", use_container_width=True):
        if not sheet_id:
            st.warning("Sheet ID not set.")
        else:
            with st.spinner("Pulling data from Google Sheets..."):
                try:
                    sync = SheetsSync(sheet_id=sheet_id)
                    data = sync.pull_all_data()
                    if data:
                        reload_from_sheets_data(data)
                        st.success("✅ Database reloaded from Google Sheets!")
                        st.toast("Pull complete!", icon="📥")
                        st.rerun()
                    else:
                        st.error("Failed to pull data. Check connection and Sheet tabs.")
                except Exception as e:
                    st.error(f"❌ Pull failed: {str(e)}")

    st.markdown("---")
    st.markdown("#### 💡 Sync Status")
    if st.session_state.get("gs_sheet_id"):
        st.info("⚡ Real-time sync is **ENABLED**. New logs and updates will be automatically pushed to Google Sheets.")
    else:
        st.warning("⚡ Real-time sync is **DISABLED**. Configure a Sheet ID to enable.")
