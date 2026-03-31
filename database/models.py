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

engine = create_engine('sqlite:///audit_logs.db')
SessionLocal = sessionmaker(bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)

def get_session():
    return SessionLocal()
