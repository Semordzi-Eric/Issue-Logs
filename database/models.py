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
    
    emails = relationship("EmailLog", back_populates="issue")

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
                             order_by="EmailResponse.date", cascade="all, delete-orphan")

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
                issue_id=r.get("Issue ID"),
                date=r.get("Date"),
                title=r.get("Title"),
                description=r.get("Description", ""), # Handle potential missing field
                category=r.get("Category"),
                priority=r.get("Priority"),
                affected_system=r.get("System"),
                transaction_id=r.get("Transaction ID"),
                amount=r.get("Amount"),
                root_cause=r.get("Root Cause"),
                status=r.get("Status")
            )
            session.add(new_i)
            session.flush() # Get the new ID
            issue_id_map[r.get("Issue ID")] = new_i.id

        # 3. Reload Email Logs
        email_id_map = {} # Sheets ID -> SQLite Object
        # Note: In SheetsSync we use the local ID as the ID column in Sheets
        for r in data.get("emails", []):
            # Find the link to the Issue ID string from the sheet
            # We stored Issue IDs like 'AUD-20250401-001' in the 'Issue ID' col of Email Logs sheet
            linked_issue_id = None
            if r.get("Issue ID") and r.get("Issue ID") != "N/A":
                # We need to query again or use the map
                # The issue_id_map maps Issue ID string -> SQLite primary key
                linked_issue_id = issue_id_map.get(r.get("Issue ID"))

            new_e = EmailLog(
                id=r.get("ID"),
                issue_id=linked_issue_id,
                date_sent=r.get("Date Sent"),
                recipient=r.get("Recipient"),
                subject=r.get("Subject"),
                email_summary=r.get("Summary"),
                response_status=r.get("Status"),
                follow_up_date=r.get("Follow-up")
            )
            session.add(new_e)
            email_id_map[r.get("ID")] = new_e.id

        # 4. Reload Responses
        for r in data.get("responses", []):
            # Since we now have 'Email Log ID' in the sheets, we can link directly.
            # However, we must ensure the local EmailLog exists with that ID.
            new_r = EmailResponse(
                id=r.get("ID"),
                email_log_id=r.get("Email Log ID"),
                date=r.get("Date"),
                direction=r.get("Direction"),
                from_to=r.get("From/To"),
                summary=r.get("Summary")
            )
            session.add(new_r)

        session.commit()
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()
