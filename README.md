# 🛡️ Audit & Revenue Assurance Tracker (Audit Hub v1.0)

A professional, high-fidelity Streamlit application designed for auditing, issue logging, and revenue assurance tracking. This tool provides a centralized platform to manage audit issues, track email communications, and generate executive reports with cloud synchronization capabilities.

---

## 🚀 Features

- **📊 Interactive Dashboard**: Real-time visualization of audit metrics, issue status distributions, and revenue impact analysis.
- **📝 Issue Logging**: Comprehensive form for capturing detailed audit findings, including severity, category, and potential financial impact.
- **🔍 Issue Management**: Advanced filtering and search capabilities to track and update existing audit issues.
- **📧 Email Tracker**: Integrated module to monitor and log communications related to specific audit findings.
- **📄 Generative Reports**: Automated generation of professional PDF and DOCX executive summary reports.
- **☁️ Cloud Sync**: Bi-directional synchronization with Google Sheets for persistent cloud storage and collaborative data management.
- **⚙️ Custom Styling**: Premium UI design with tailored CSS for a sleek, professional experience.

---

## 🛠️ Tech Stack

- **Frontend/App Framework**: [Streamlit](https://streamlit.io/)
- **Data Manipulation**: [Pandas](https://pandas.pydata.org/)
- **Database/ORM**: [SQLAlchemy](https://www.sqlalchemy.org/) (Local SQLite for caching/speed)
- **Visualizations**: [Plotly](https://plotly.com/)
- **Report Generation**: [python-docx](https://python-docx.readthedocs.io/), [ReportLab](https://www.reportlab.com/)
- **Cloud Integration**: [gspread](https://docs.gspread.org/), [Google Auth](https://google-auth.readthedocs.io/)

---

## 📥 Installation & Setup

### 1. Clone the Repository
```bash
git clone <repository-url>
cd Issue-Logs
```

### 2. Create a Virtual Environment (Recommended)
```bash
python -m venv .venv
# On Windows
.venv\Scripts\activate
# On macOS/Linux
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configuration

To enable **Cloud Synchronization** with Google Sheets, you have two options for authentication:

#### Option A: Streamlit Secrets (Recommended for Cloud Deployment)
Create a `.streamlit/secrets.toml` file in the root directory and add:
```toml
gs_sheet_id = "your_google_sheet_id_here"
gcp_service_account = '''
{
  "type": "service_account",
  "project_id": "...",
  "private_key_id": "...",
  "private_key": "...",
  "client_email": "...",
  "client_id": "...",
  "auth_uri": "...",
  "token_uri": "...",
  "auth_provider_x509_cert_url": "...",
  "client_x509_cert_url": "..."
}
'''
```

#### Option B: Local Service Account File
1. Place your `service_account.json` file in the root directory.
2. Enter your **Spreadsheet ID** in the **Settings & Sync** page within the application UI.

---

## 🚦 Usage

### Running Locally
```bash
streamlit run app.py
```

### Navigation Modules
1. **📊 Dashboard Overview**: Visual summary of audit progress, financial impact, and issue aging.
2. **📝 Log New Issue**: Entry point for new audit findings and revenue leakage points.
3. **🔍 Manage Issues**: Edit, update status, or delete existing logs.
4. **📧 Email Tracker**: Log stakeholder communications and set follow-up reminders.
5. **📄 Generative Reports**: Export professional executive summaries in PDF or DOCX format.
6. **⚙️ Settings & Sync**: Manage your Google Sheets connection and system preferences.

---

## 📂 Project Structure

```text
Issue-Logs/
├── app.py              # Main entry point and routing logic
├── requirements.txt    # Project dependencies
├── database/           # DB models and Google Sheets sync logic
│   ├── models.py
│   └── sheets_sync.py
├── modules/            # Feature-specific UI components
│   ├── dashboard.py
│   ├── emails.py
│   ├── issues.py
│   ├── reports.py
│   └── settings.py
├── utils/              # Helper functions and UI styling
│   ├── helpers.py
│   └── styling.py
└── .gitignore          # Git exclusion rules
```

---

## 📄 License
[Specify License Type, e.g., MIT]

## 👥 Authors
[Your Name/Organization]
