import datetime
from database.models import Issue, get_session

def generate_issue_id():
    """Generates a new issue ID structured as AUD-{YYYYMMDD}-{001}"""
    today = datetime.datetime.now().strftime("%Y%m%d")
    
    # query database to find the last issue of today
    session = get_session()
    last_issue = session.query(Issue).filter(Issue.issue_id.like(f"AUD-{today}-%")).order_by(Issue.issue_id.desc()).first()
    session.close()
    
    if last_issue:
        # Extract the sequence number and increment
        last_seq = int(last_issue.issue_id.split('-')[-1])
        new_seq = last_seq + 1
    else:
        new_seq = 1
        
    return f"AUD-{today}-{new_seq:03d}"

def predict_category(description: str) -> str:
    """Basic keyword matching to suggest a category"""
    desc_lower = description.lower()
    
    keywords = {
        "Revenue Leakage": ["leakage", "loss", "shortfall", "missing revenue", "unbilled"],
        "Failed Transactions": ["failed", "failure", "timeout", "declined", "error"],
        "Suspicious Activity": ["fraud", "suspicious", "unauthorized", "anomaly", "phishing"],
        "Reversals": ["reversed", "reversal", "chargeback", "refund"],
        "System Errors": ["bug", "crash", "down", "outage", "system error", "api"]
    }
    
    for category, words in keywords.items():
        if any(word in desc_lower for word in words):
            return category
            
    return "Others"

def calculate_days_pending(start_date) -> int:
    """Calculate how many days an issue has been pending"""
    if not start_date:
        return 0
    delta = datetime.datetime.utcnow().date() - start_date
    return max(0, delta.days)
