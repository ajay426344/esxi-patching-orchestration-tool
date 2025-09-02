from sqlalchemy import Column, Integer, String, DateTime, Boolean, Float, Text, create_engine
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class Host(Base):
    __tablename__ = 'hosts'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    ip_address = Column(String(15), unique=True, nullable=False, index=True)
    hostname = Column(String(255))
    current_build = Column(String(50))
    target_build = Column(String(50))
    status = Column(String(50), default='pending')
    last_checked = Column(DateTime, default=datetime.utcnow)
    datastore = Column(String(255))
    datastore_free_gb = Column(Float)
    ssh_enabled = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
class PatchingJob(Base):
    __tablename__ = 'patching_jobs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    host_ip = Column(String(15), index=True)
    job_type = Column(String(50))  # pre_check, phase1, phase2
    status = Column(String(50), index=True)  # running, success, failed
    started_at = Column(DateTime, default=datetime.utcnow, index=True)
    completed_at = Column(DateTime)
    error_message = Column(Text)
    patch_file = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)
    
class Settings(Base):
    __tablename__ = 'settings'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(50), unique=True, index=True)
    value = Column(String(255))
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
