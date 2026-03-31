import streamlit as st

def apply_custom_css():
    st.markdown("""
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

            /* ─── Base & Background ─── */
            html, body, [class*="css"] {
                font-family: 'Inter', sans-serif !important;
                color: #E8EAF0 !important;
            }
            .stApp,
            [data-testid="stAppViewContainer"],
            [data-testid="stMain"] {
                background-color: #0F1117 !important;
            }

            /* ─── Header / top bar ─── */
            header[data-testid="stHeader"] {
                background-color: #0F1117 !important;
                border-bottom: 1px solid rgba(255,255,255,0.08) !important;
                box-shadow: none !important;
            }

            /* ─── Sidebar ─── */
            section[data-testid="stSidebar"] > div:first-child {
                background-color: #1A1D27 !important;
                border-right: 1px solid rgba(255,255,255,0.07) !important;
                box-shadow: 2px 0 12px rgba(0,0,0,0.4) !important;
            }
            section[data-testid="stSidebar"] * {
                color: #E8EAF0 !important;
            }
            section[data-testid="stSidebar"] .stCaption {
                color: #7B849A !important;
                font-size: 0.77rem !important;
            }

            /* ─── Metric Cards ─── */
            div[data-testid="stMetric"] {
                background-color: rgba(255,255,255,0.04);
                border: 1px solid rgba(255,255,255,0.09);
                padding: 16px 20px;
                border-radius: 12px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.3);
                transition: transform 0.2s ease, box-shadow 0.2s ease;
            }
            div[data-testid="stMetric"]:hover {
                transform: translateY(-4px);
                box-shadow: 0 10px 24px rgba(0,0,0,0.4);
                background-color: rgba(255,255,255,0.07);
            }
            div[data-testid="stMetricLabel"] p {
                color: #9BA3B5 !important;
                font-size: 0.78rem;
                text-transform: uppercase;
                letter-spacing: 0.6px;
                font-weight: 500;
            }
            div[data-testid="stMetricValue"] {
                color: #E8EAF0 !important;
                font-weight: 700 !important;
            }

            /* ─── Buttons ─── */
            .stButton > button {
                border-radius: 8px;
                font-weight: 600;
                transition: all 0.25s ease;
                font-family: 'Inter', sans-serif;
                background-color: rgba(255,255,255,0.05) !important;
                border-color: rgba(255,255,255,0.12) !important;
                color: #E8EAF0 !important;
            }
            .stButton > button:hover {
                border-color: #4CAF50 !important;
                color: #4CAF50 !important;
                transform: scale(1.02);
                box-shadow: 0 4px 12px rgba(0,0,0,0.3);
            }
            .stButton > button[kind="primary"] {
                background-color: #2E7D32 !important;
                color: #FFFFFF !important;
                border-color: #2E7D32 !important;
            }
            .stButton > button[kind="primary"]:hover {
                background-color: #388E3C !important;
                border-color: #388E3C !important;
                color: #FFFFFF !important;
            }

            /* ─── Inputs ─── */
            div[data-baseweb="input"] input,
            div[data-baseweb="textarea"] textarea {
                background-color: #22263A !important;
                color: #E8EAF0 !important;
                border: 1.5px solid rgba(255,255,255,0.13) !important;
                border-radius: 8px !important;
            }
            div[data-baseweb="input"] input:focus,
            div[data-baseweb="textarea"] textarea:focus {
                border-color: #4CAF50 !important;
                box-shadow: 0 0 0 2px rgba(76,175,80,0.2) !important;
            }
            div[data-baseweb="select"] > div {
                background-color: #22263A !important;
                border: 1.5px solid rgba(255,255,255,0.13) !important;
                border-radius: 8px !important;
                color: #E8EAF0 !important;
            }
            div[data-testid="stDateInput"] input,
            div[data-testid="stNumberInput"] input {
                background-color: #22263A !important;
                color: #E8EAF0 !important;
                border: 1.5px solid rgba(255,255,255,0.13) !important;
            }

            /* ─── Form container ─── */
            div[data-testid="stForm"] {
                background-color: #1A1D27 !important;
                border: 1px solid rgba(255,255,255,0.08) !important;
                border-radius: 14px !important;
                padding: 20px !important;
                box-shadow: 0 4px 20px rgba(0,0,0,0.35) !important;
            }

            /* ─── Labels ─── */
            .stTextInput label, .stSelectbox label,
            .stTextArea label, .stDateInput label,
            .stNumberInput label, .stMultiSelect label,
            .stCheckbox label, .stRadio label {
                color: #9BA3B5 !important;
                font-size: 0.84rem;
                font-weight: 500;
            }

            /* ─── Dataframes ─── */
            .dataframe { font-size: 0.88rem !important; }
            [data-testid="stDataFrame"] {
                background-color: #1A1D27 !important;
                border-radius: 10px;
                border: 1px solid rgba(255,255,255,0.08);
                overflow: hidden;
            }

            /* ─── Dividers ─── */
            hr { border-color: rgba(255,255,255,0.08) !important; margin: 1rem 0; }

            /* ─── Expanders ─── */
            .streamlit-expanderHeader {
                font-weight: 600;
                background-color: rgba(255,255,255,0.03) !important;
                border-radius: 8px;
                color: #E8EAF0 !important;
            }

            /* ─── Headers ─── */
            h1, h2, h3, h4, h5, h6 { color: #E8EAF0 !important; font-weight: 700; }
            p, .stMarkdown p, .stMarkdown li { color: #E8EAF0 !important; }

            /* ─── Alert boxes ─── */
            div[data-testid="stAlert"] {
                border-radius: 10px !important;
                background-color: #1A1D27 !important;
                border: 1px solid rgba(255,255,255,0.09) !important;
            }

            /* ─── Status Badges ─── */
            .status-badge {
                padding: 3px 10px;
                border-radius: 12px;
                font-size: 0.78rem;
                font-weight: 600;
                display: inline-block;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }
            .status-open         { background-color: #3E2000; color: #FFB74D; border: 1px solid #5C3000; }
            .status-investigating { background-color: #0D2747; color: #64B5F6; border: 1px solid #1A3D6E; }
            .status-resolved     { background-color: #0D2E12; color: #81C784; border: 1px solid #1B4C20; }
            .status-escalated    { background-color: #2D0A0A; color: #E57373; border: 1px solid #4A1010; }

            /* ─── Scrollbar ─── */
            ::-webkit-scrollbar { width: 6px; }
            ::-webkit-scrollbar-track { background: #0F1117; }
            ::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.15); border-radius: 4px; }
            ::-webkit-scrollbar-thumb:hover { background: rgba(255,255,255,0.25); }
        </style>
    """, unsafe_allow_html=True)


def render_status_badge(status: str) -> str:
    status_lower = status.lower().replace(" ", "-")
    return f'<span class="status-badge status-{status_lower}">{status}</span>'
