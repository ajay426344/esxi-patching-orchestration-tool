from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel
from typing import List, Optional
import subprocess
import asyncio
import yaml
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
import os
import paramiko
from pathlib import Path

app = FastAPI()
security = HTTPBasic()

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Authentication
def authenticate(credentials: HTTPBasicCredentials = Depends(security)):
    if credentials.username != "ajay" or credentials.password != "Ajay@426344":
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return credentials.username

# Request Models
class HostRequest(BaseModel):
    ip_addresses: List[str]
    
class PatchRequest(BaseModel):
    hosts: List[str]
    patch_file: str
    phase: int

# Database dependency
def get_db():
    from database import SessionLocal
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Helper Functions
def run_ansible_playbook(playbook: str, hosts: List[str], extra_vars: dict = None):
    """Execute Ansible playbook"""
    inventory = ",".join(hosts) + ","
    cmd = [
        "ansible-playbook",
        f"ansible/playbooks/{playbook}",
        "-i", inventory,
        "--extra-vars", f"@ansible/group_vars/all.yml"
    ]
    
    if extra_vars:
        cmd.extend(["--extra-vars", yaml.dump(extra_vars)])
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    return {
        "success": result.returncode == 0,
        "stdout": result.stdout,
        "stderr": result.stderr
    }

def check_ssh_connectivity(host_ip: str, username: str, password: str):
    """Check if SSH is enabled on host"""
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(host_ip, username=username, password=password, timeout=10)
        ssh.close()
        return True
    except:
        return False

def get_host_info(host_ip: str, username: str, password: str):
    """Get ESXi host information"""
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(host_ip, username=username, password=password)
        
        # Get build version
        stdin, stdout, stderr = ssh.exec_command("vmware -v")
        build_info = stdout.read().decode().strip()
        
        # Get datastore info
        stdin, stdout, stderr = ssh.exec_command("df -h | grep vmfs")
        datastore_info = stdout.read().decode().strip()
        
        ssh.close()
        return {
            "build": build_info,
            "datastore": datastore_info
        }
    except Exception as e:
        return {"error": str(e)}

# API Endpoints
@app.get("/api/hosts")
async def get_hosts(db: Session = Depends(get_db)):
    """Get all hosts with their current status"""
    from models import Host
    hosts = db.query(Host).all()
    return hosts

@app.post("/api/hosts/add")
async def add_hosts(request: HostRequest, 
                   username: str = Depends(authenticate),
                   db: Session = Depends(get_db)):
    """Add new hosts to inventory"""
    from models import Host
    
    added_hosts = []
    for ip in request.ip_addresses:
        existing = db.query(Host).filter_by(ip_address=ip).first()
        if not existing:
            host = Host(ip_address=ip)
            db.add(host)
            added_hosts.append(ip)
    
    db.commit()
    return {"message": f"Added {len(added_hosts)} hosts", "hosts": added_hosts}

@app.post("/api/precheck")
async def run_precheck(request: HostRequest,
                       background_tasks: BackgroundTasks,
                       username: str = Depends(authenticate),
                       db: Session = Depends(get_db)):
    """Run pre-checks on selected hosts"""
    from models import Host, PatchingJob
    
    for host_ip in request.ip_addresses:
        # Create job record
        job = PatchingJob(
            host_ip=host_ip,
            job_type="pre_check",
            status="running"
        )
        db.add(job)
        db.commit()
        
        # Run pre-check in background
        background_tasks.add_task(execute_precheck, host_ip, job.id, db)
    
    return {"message": f"Pre-checks initiated for {len(request.ip_addresses)} hosts"}

async def execute_precheck(host_ip: str, job_id: int, db: Session):
    """Execute pre-check tasks"""
    from models import Host, PatchingJob
    
    job = db.query(PatchingJob).filter_by(id=job_id).first()
    host = db.query(Host).filter_by(ip_address=host_ip).first()
    
    try:
        # Load credentials
        with open("ansible/group_vars/all.yml", "r") as f:
            creds = yaml.safe_load(f)
        
        # Check SSH
        ssh_enabled = check_ssh_connectivity(
            host_ip, 
            creds['esxi_username'], 
            creds['esxi_password']
        )
        
        if not ssh_enabled:
            raise Exception("SSH is not enabled on host")
        
        host.ssh_enabled = True
        
        # Get host info
        info = get_host_info(host_ip, creds['esxi_username'], creds['esxi_password'])
        if "error" in info:
            raise Exception(info["error"])
        
        host.current_build = info.get("build", "")
        
        # Run ansible pre-check playbook
        result = run_ansible_playbook("pre_checks.yml", [host_ip])
        
        if result["success"]:
            job.status = "success"
            host.status = "pre_check_passed"
        else:
            job.status = "failed"
            job.error_message = result["stderr"]
            host.status = "pre_check_failed"
            
    except Exception as e:
        job.status = "failed"
        job.error_message = str(e)
        host.status = "pre_check_failed"
    
    job.completed_at = datetime.utcnow()
    host.last_checked = datetime.utcnow()
    db.commit()

@app.post("/api/patch/phase1")
async def run_phase1(request: PatchRequest,
                     background_tasks: BackgroundTasks,
                     username: str = Depends(authenticate),
                     db: Session = Depends(get_db)):
    """Stage patches on hosts (Phase 1)"""
    from models import Host, PatchingJob
    
    for host_ip in request.hosts:
        host = db.query(Host).filter_by(ip_address=host_ip).first()
        
        # Check if pre-check passed
        if host.status != "pre_check_passed":
            continue
        
        job = PatchingJob(
            host_ip=host_ip,
            job_type="phase1",
            status="running",
            patch_file=request.patch_file
        )
        db.add(job)
        db.commit()
        
        background_tasks.add_task(execute_phase1, host_ip, job.id, request.patch_file, db)
    
    return {"message": f"Phase 1 initiated for {len(request.hosts)} hosts"}

async def execute_phase1(host_ip: str, job_id: int, patch_file: str, db: Session):
    """Execute Phase 1 - Stage patches"""
    from models import Host, PatchingJob
    
    job = db.query(PatchingJob).filter_by(id=job_id).first()
    host = db.query(Host).filter_by(ip_address=host_ip).first()
    
    try:
        # Run phase 1 playbook
        extra_vars = {
            "patch_file": patch_file,
            "target_host": host_ip
        }
        
        result = run_ansible_playbook("phase1_stage.yml", [host_ip], extra_vars)
        
        if result["success"]:
            job.status = "success"
            host.status = "phase1_completed"
            host.target_build = patch_file.split("-")[2]  # Extract build number
        else:
            job.status = "failed"
            job.error_message = result["stderr"]
            host.status = "phase1_failed"
            
    except Exception as e:
        job.status = "failed"
        job.error_message = str(e)
        host.status = "phase1_failed"
    
    job.completed_at = datetime.utcnow()
    db.commit()

@app.post("/api/patch/phase2")
async def run_phase2(request: PatchRequest,
                     background_tasks: BackgroundTasks,
                     username: str = Depends(authenticate),
                     db: Session = Depends(get_db)):
    """Reboot and verify hosts (Phase 2)"""
    from models import Host, PatchingJob
    
    for host_ip in request.hosts:
        host = db.query(Host).filter_by(ip_address=host_ip).first()
        
        # Check if phase 1 completed
        if host.status != "phase1_completed":
            continue
        
        job = PatchingJob(
            host_ip=host_ip,
            job_type="phase2",
            status="running"
        )
        db.add(job)
        db.commit()
        
        background_tasks.add_task(execute_phase2, host_ip, job.id, db)
    
    return {"message": f"Phase 2 initiated for {len(request.hosts)} hosts"}

async def execute_phase2(host_ip: str, job_id: int, db: Session):
    """Execute Phase 2 - Reboot and verify"""
    from models import Host, PatchingJob
    import time
    
    job = db.query(PatchingJob).filter_by(id=job_id).first()
    host = db.query(Host).filter_by(ip_address=host_ip).first()
    
    try:
        # Run phase 2 playbook
        result = run_ansible_playbook("phase2_reboot.yml", [host_ip])
        
        if not result["success"]:
            raise Exception(result["stderr"])
        
        # Wait for reboot with grace period
        time.sleep(120)  # 2 minutes grace period
        
        # Verify host is back online
        max_retries = 20  # 10 minutes total
        for i in range(max_retries):
            with open("ansible/group_vars/all.yml", "r") as f:
                creds = yaml.safe_load(f)
            
            if check_ssh_connectivity(host_ip, creds['esxi_username'], creds['esxi_password']):
                # Verify build version
                info = get_host_info(host_ip, creds['esxi_username'], creds['esxi_password'])
                if host.target_build in info.get("build", ""):
                    job.status = "success"
                    host.status = "patching_completed"
                    host.current_build = info.get("build", "")
                    break
            
            time.sleep(30)  # Retry every 30 seconds
        else:
            raise Exception("Host did not come back online within timeout")
            
    except Exception as e:
        job.status = "failed"
        job.error_message = str(e)
        host.status = "phase2_failed"
    
    job.completed_at = datetime.utcnow()
    db.commit()

@app.get("/api/jobs")
async def get_jobs(db: Session = Depends(get_db), 
                   filter_days: Optional[int] = None):
    """Get patching jobs with optional filtering"""
    from models import PatchingJob
    
    query = db.query(PatchingJob)
    
    if filter_days:
        cutoff = datetime.utcnow() - timedelta(days=filter_days)
        query = query.filter(PatchingJob.started_at >= cutoff)
    
    jobs = query.order_by(PatchingJob.started_at.desc()).all()
    return jobs

@app.get("/api/settings")
async def get_settings(db: Session = Depends(get_db)):
    """Get all configuration settings"""
    from models import Settings
    settings = db.query(Settings).all()
    return {s.key: s.value for s in settings}

@app.post("/api/settings")
async def update_settings(settings: dict,
                         username: str = Depends(authenticate),
                         db: Session = Depends(get_db)):
    """Update configuration settings"""
    from models import Settings
    
    for key, value in settings.items():
        setting = db.query(Settings).filter_by(key=key).first()
        if setting:
            setting.value = value
            setting.updated_at = datetime.utcnow()
        else:
            setting = Settings(key=key, value=value)
            db.add(setting)
    
    db.commit()
    return {"message": "Settings updated successfully"}

@app.post("/api/refresh/{host_ip}")
async def refresh_host(host_ip: str,
                       background_tasks: BackgroundTasks,
                       db: Session = Depends(get_db)):
    """Refresh single host status"""
    from models import Host
    
    host = db.query(Host).filter_by(ip_address=host_ip).first()
    if not host:
        raise HTTPException(status_code=404, detail="Host not found")
    
    background_tasks.add_task(refresh_host_status, host_ip, db)
    return {"message": f"Refresh initiated for {host_ip}"}

async def refresh_host_status(host_ip: str, db: Session):
    """Refresh host status"""
    from models import Host
    
    host = db.query(Host).filter_by(ip_address=host_ip).first()
    
    with open("ansible/group_vars/all.yml", "r") as f:
        creds = yaml.safe_load(f)
    
    # Check SSH and get info
    ssh_enabled = check_ssh_connectivity(host_ip, creds['esxi_username'], creds['esxi_password'])
    host.ssh_enabled = ssh_enabled
    
    if ssh_enabled:
        info = get_host_info(host_ip, creds['esxi_username'], creds['esxi_password'])
        if "build" in info:
            host.current_build = info["build"]
    
    host.last_checked = datetime.utcnow()
    db.commit()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
