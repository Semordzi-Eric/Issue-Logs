from sqlalchemy import create_engine, Column, Integer, String, Date, Text, Float, ForeignKey
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from datetime import datetime

Base = declarative_base()

class Issue(Base):
    __tablename__ = 'issues'
    
    id = Column(Integer, primary_key=True)
    issue_id = Column(String, unique=True, index=True)
    date = Column(Date, default=datetime.utcnow().date)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    category = Column(String, nullable=False)
    priority = Column(String, nullable=False)
    affected_system = Column(String, nullable=False)
    transaction_id = Column(String, nullable=True)
    amount = Column(Float, nullable=True)
    root_cause = Column(String, nullable=True)
    status = Column(String, nullable=False, default='Open')
    resolution_notes = Column(Text, nullable=True)
    
    emails = relationship("EmailLog", back_populates="issue", 
                          cascade="all, delete-orphan")

class EmailLog(Base):
    __tablename__ = 'email_logs'
    
    id = Column(Integer, primary_key=True)
    issue_id = Column(Integer, ForeignKey('issues.id'))
    date_sent = Column(Date, default=datetime.utcnow().date)
    recipient = Column(String, nullable=False)
    subject = Column(String, nullable=False)
    email_summary = Column(Text, nullable=False)
    response_status = Column(String, nullable=False, default='No Response')
    response_summary = Column(Text, nullable=True)
    follow_up_date = Column(Date, nullable=True)
    
    issue = relationship("Issue", back_populates="emails")
    responses = relationship("EmailResponse", back_populates="email_log",
                             order_by="EmailResponse.date", 
                             cascade="all, delete-orphan")

class EmailResponse(Base):
    __tablename__ = 'email_responses'
    
    id = Column(Integer, primary_key=True)
    email_log_id = Column(Integer, ForeignKey('email_logs.id'), nullable=False)
    date = Column(Date, default=datetime.utcnow().date, nullable=False)
    direction = Column(String, nullable=False)   # 'Sent' or 'Received'
    from_to = Column(String, nullable=False)     # sender if Received, recipient if Sent
    summary = Column(Text, nullable=False)
    
    email_log = relationship("EmailLog", back_populates="responses")

class SystemSetting(Base):
    __tablename__ = 'system_settings'
    
    key = Column(String, primary_key=True)
    value = Column(String, nullable=False)

engine = create_engine('sqlite:///audit_logs.db')
SessionLocal = sessionmaker(bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)

def get_session():
    return SessionLocal()

def get_setting(key, default=None):
    """Get a persistent setting from the database."""
    session = SessionLocal()
    try:
        setting = session.query(SystemSetting).filter_by(key=key).first()
        return setting.value if setting else default
    finally:
        session.close()

def set_setting(key, value):
    """Set a persistent setting in the database."""
    session = SessionLocal()
    try:
        setting = session.query(SystemSetting).filter_by(key=key).first()
        if setting:
            setting.value = str(value)
        else:
            session.add(SystemSetting(key=key, value=str(value)))
        session.commit()
    finally:
        session.close()

def reload_from_sheets_data(data):
    """Wipe local DB and reload with data from Google Sheets."""
    session = SessionLocal()
    try:
        # 1. Clear everything
        session.query(EmailResponse).delete()
        session.query(EmailLog).delete()
        session.query(Issue).delete()
        session.commit()

        # 2. Reload Issues
        issue_id_map = {} # Sheets ID -> SQLite Object
        for r in data.get("issues", []):
            new_i = Issue(
                id=r.get("ID"),
                issue_id=r.get("Issue ID") or f"TEMP-{r.get('ID')}",
                date=r.get("Date"),
                title=r.get("Title") or "Untitled Issue",
                description=r.get("Description") or "",
                category=r.get("Category") or "Other",
                priority=r.get("Priority") or "Medium",
                affected_system=r.get("System") or "Unknown",
                transaction_id=str(r.get("Transaction ID", "")),
                amount=r.get("Amount") if isinstance(r.get("Amount"), (int, float)) else 0.0,
                root_cause=r.get("Root Cause") or "",
                status=r.get("Status") or "Open"
            )
            session.add(new_i)
            session.flush() # Get the new ID
            issue_id_map[str(r.get("Issue ID"))] = new_i.id

        # 3. Reload Email Logs
        email_id_map = {} # Sheets ID -> SQLite Object
        for r in data.get("emails", []):
            linked_issue_id = None
            issue_id_str = str(r.get("Issue ID"))
            if issue_id_str and issue_id_str != "N/A":
                linked_issue_id = issue_id_map.get(issue_id_str)

            new_e = EmailLog(
                id=r.get("ID"),
                issue_id=linked_issue_id,
                date_sent=r.get("Date Sent"),
                recipient=r.get("Recipient") or "Unknown",
                subject=r.get("Subject") or "No Subject",
                email_summary=r.get("Summary") or "",
                response_status=r.get("Status") or "No Response",
                follow_up_date=r.get("Follow-up")
            )
            session.add(new_e)
            email_id_map[r.get("ID")] = new_e.id

        # 4. Reload Responses
        for r in data.get("responses", []):
            new_r = EmailResponse(
                id=r.get("ID"),
                email_log_id=r.get("Email Log ID"),
                date=r.get("Date"),
                direction=r.get("Direction") or "Received",
                from_to=r.get("From/To") or "Unknown",
                summary=r.get("Summary") or ""
            )
            session.add(new_r)

        session.commit()
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()
