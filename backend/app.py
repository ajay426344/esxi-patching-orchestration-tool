from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, UploadFile, File
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
import shutil
import json
import secrets
from auth import get_current_user

app = FastAPI(title="ESXi Patching Orchestrator API")
security = HTTPBasic()

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request Models
class HostRequest(BaseModel):
    ip_addresses: List[str]
    
class PatchRequest(BaseModel):
    hosts: List[str]
    patch_file: str

class SettingsRequest(BaseModel):
    auto_phase2_window: Optional[str] = "10"
    reboot_grace_period: Optional[str] = "2"

# Database dependency
def get_db():
    from database import SessionLocal
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Authentication
def authenticate(credentials: HTTPBasicCredentials = Depends(security)):
    correct_username = secrets.compare_digest(
        credentials.username, os.getenv("ADMIN_USERNAME", "ajay")
    )
    correct_password = secrets.compare_digest(
        credentials.password, os.getenv("ADMIN_PASSWORD", "Ajay@426344")
    )
    
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

# Helper Functions
def run_ansible_playbook(playbook: str, hosts: List[str], extra_vars: dict = None):
    """Execute Ansible playbook via ansible_server API"""
    import requests
    
    ansible_url = f"http://{os.getenv('ANSIBLE_HOST', 'ansible')}:{os.getenv('ANSIBLE_PORT', '5555')}/run-playbook"
    
    payload = {
        "playbook": playbook,
        "inventory": hosts,
        "extra_vars": extra_vars or {}
    }
    
    try:
        response = requests.post(ansible_url, json=payload, timeout=300)
        if response.status_code == 200:
            return response.json()
        else:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Ansible server returned status {response.status_code}"
            }
    except Exception as e:
        # Fallback to direct execution if ansible server is not available
        inventory = ",".join(hosts) + ","
        cmd = [
            "ansible-playbook",
            f"ansible/playbooks/{playbook}",
            "-i", inventory,
        ]
        
        if extra_vars:
            cmd.extend(["--extra-vars", json.dumps(extra_vars)])
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr
        }

def check_ssh_connectivity(host_ip: str, username: str = None, password: str = None):
    """Check if SSH is enabled on host"""
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        username = username or os.getenv("ESXI_USERNAME", "root")
        password = password or os.getenv("ESXI_PASSWORD", "")
        
        ssh.connect(host_ip, username=username, password=password, timeout=10)
        ssh.close()
        return True
    except Exception as e:
        print(f"SSH connectivity check failed for {host_ip}: {e}")
        return False

def get_host_info(host_ip: str, username: str = None, password: str = None):
    """Get ESXi host information"""
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        username = username or os.getenv("ESXI_USERNAME", "root")
        password = password or os.getenv("ESXI_PASSWORD", "")
        
        ssh.connect(host_ip, username=username, password=password, timeout=10)
        
        # Get build version
        stdin, stdout, stderr = ssh.exec_command("vmware -v")
        build_info = stdout.read().decode().strip()
        
        # Get hostname
        stdin, stdout, stderr = ssh.exec_command("hostname")
        hostname = stdout.read().decode().strip()
        
        # Get datastore info
        stdin, stdout, stderr = ssh.exec_command("df -h | grep vmfs")
        datastore_info = stdout.read().decode().strip()
        
        ssh.close()
        return {
            "build": build_info,
            "hostname": hostname,
            "datastore": datastore_info
        }
    except Exception as e:
        return {"error": str(e)}

# API Endpoints

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.utcnow()}

@app.get("/api/hosts")
async def get_hosts(db: Session = Depends(get_db)):
    """Get all hosts with their current status"""
    from models import Host
    hosts = db.query(Host).all()
    return hosts
@app.post("/api/hosts/add")
async def add_hosts(request: HostRequest, 
                   background_tasks: BackgroundTasks,
                   auto_precheck: bool = True,  # New parameter
                   username: str = Depends(authenticate),
                   db: Session = Depends(get_db)):
    """Add new hosts to inventory with optional auto pre-check"""
    from models import Host, PatchingJob
    
    added_hosts = []
    for ip in request.ip_addresses:
        # Validate IP format
        import re
        if not re.match(r'^(\d{1,3}\.){3}\d{1,3}$', ip):
            continue
            
        existing = db.query(Host).filter_by(ip_address=ip).first()
        if not existing:
            # Get initial host info
            info = get_host_info(ip)
            
            host = Host(
                ip_address=ip,
                hostname=info.get("hostname", ""),
                current_build=info.get("build", ""),
                ssh_enabled=check_ssh_connectivity(ip),
                status="pending"  # Initial status
            )
            db.add(host)
            db.commit()  # Commit to get host ID
            
            added_hosts.append(ip)
            
            # Auto-trigger pre-check if enabled
            if auto_precheck and host.ssh_enabled:
                job = PatchingJob(
                    host_ip=ip,
                    job_type="pre_check",
                    status="running"
                )
                db.add(job)
                db.commit()
                
                # Run pre-check in background
                background_tasks.add_task(execute_precheck, ip, job.id, db)
    
    db.commit()
    
    response = {
        "message": f"Added {len(added_hosts)} hosts",
        "hosts": added_hosts
    }
    
    if auto_precheck:
        response["precheck_status"] = f"Pre-checks automatically initiated for {len(added_hosts)} hosts"
    
    return response
@app.post("/api/hosts/add")
async def add_hosts(request: HostRequest, 
                   username: str = Depends(authenticate),
                   db: Session = Depends(get_db)):
    """Add new hosts to inventory"""
    from models import Host
    
    added_hosts = []
    for ip in request.ip_addresses:
        # Validate IP format
        import re
        if not re.match(r'^(\d{1,3}\.){3}\d{1,3}$', ip):
            continue
            
        existing = db.query(Host).filter_by(ip_address=ip).first()
        if not existing:
            # Get initial host info
            info = get_host_info(ip)
            
            host = Host(
                ip_address=ip,
                hostname=info.get("hostname", ""),
                current_build=info.get("build", ""),
                ssh_enabled=check_ssh_connectivity(ip)
            )
            db.add(host)
            added_hosts.append(ip)
    
    db.commit()
    return {"message": f"Added {len(added_hosts)} hosts", "hosts": added_hosts}

@app.delete("/api/hosts/{ip}")
async def remove_host(ip: str,
                     username: str = Depends(authenticate),
                     db: Session = Depends(get_db)):
    """Remove a host from inventory"""
    from models import Host
    
    host = db.query(Host).filter_by(ip_address=ip).first()
    if not host:
        raise HTTPException(status_code=404, detail="Host not found")
    
    db.delete(host)
    db.commit()
    return {"message": f"Removed host {ip}"}

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
        # Check SSH
        ssh_enabled = check_ssh_connectivity(host_ip)
        
        if not ssh_enabled:
            raise Exception("SSH is not enabled on host")
        
        host.ssh_enabled = True
        
        # Get host info
        info = get_host_info(host_ip)
        if "error" in info:
            raise Exception(info["error"])
        
        host.current_build = info.get("build", "")
        host.hostname = info.get("hostname", "")
        
        # Parse datastore info to check free space
        datastore_info = info.get("datastore", "")
        has_sufficient_space = False
        
        if datastore_info:
            # Simple check for any datastore with >2GB free
            lines = datastore_info.split('\n')
            for line in lines:
                if 'G' in line:  # Look for GB values
                    parts = line.split()
                    for part in parts:
                        if part.endswith('G'):
                            try:
                                size = float(part[:-1])
                                if size > 2:
                                    has_sufficient_space = True
                                    host.datastore = line.split()[0]
                                    host.datastore_free_gb = size
                                    break
                            except:
                                continue
        
        if not has_sufficient_space:
            raise Exception("Insufficient datastore space (need >2GB free)")
        
        # Run ansible pre-check playbook
        result = run_ansible_playbook("pre_checks.yml", [host_ip])
        
        if result["success"]:
            job.status = "success"
            host.status = "pre_check_passed"
        else:
            job.status = "failed"
            job.error_message = result.get("stderr", "Pre-check failed")
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
        
        if not host:
            continue
            
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
        # Determine datastore to use
        datastore = host.datastore or "datastore1"
        
        # Run phase 1 playbook
        extra_vars = {
            "patch_file": patch_file,
            "target_host": host_ip,
            "datastore": datastore
        }
        
        result = run_ansible_playbook("phase1_stage.yml", [host_ip], extra_vars)
        
        if result["success"]:
            job.status = "success"
            host.status = "phase1_completed"
            # Extract build number from patch filename
            if '-' in patch_file:
                parts = patch_file.split('-')
                if len(parts) > 2:
                    host.target_build = parts[2]
        else:
            job.status = "failed"
            job.error_message = result.get("stderr", "Phase 1 failed")
            host.status = "phase1_failed"
            
    except Exception as e:
        job.status = "failed"
        job.error_message = str(e)
        host.status = "phase1_failed"
    
    job.completed_at = datetime.utcnow()
    host.last_checked = datetime.utcnow()
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
        
        if not host:
            continue
            
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
            raise Exception(result.get("stderr", "Phase 2 playbook failed"))
        
        # Wait for reboot with grace period
        grace_period = int(os.getenv("REBOOT_GRACE_PERIOD", "120"))
        time.sleep(grace_period)
        
        # Verify host is back online
        max_retries = 20  # 10 minutes total
        for i in range(max_retries):
            if check_ssh_connectivity(host_ip):
                # Verify build version
                info = get_host_info(host_ip)
                current_build = info.get("build", "")
                
                if host.target_build and host.target_build in current_build:
                    job.status = "success"
                    host.status = "patching_completed"
                    host.current_build = current_build
                    break
                elif i == max_retries - 1:
                    raise Exception(f"Build verification failed. Expected: {host.target_build}, Got: {current_build}")
            
            time.sleep(30)  # Retry every 30 seconds
        else:
            raise Exception("Host did not come back online within timeout")
            
    except Exception as e:
        job.status = "failed"
        job.error_message = str(e)
        host.status = "phase2_failed"
    
    job.completed_at = datetime.utcnow()
    host.last_checked = datetime.utcnow()
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
    
    jobs = query.order_by(PatchingJob.started_at.desc()).limit(100).all()
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
            setting.value = str(value)
            setting.updated_at = datetime.utcnow()
        else:
            setting = Settings(key=key, value=str(value))
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
    if not host:
        return
    
    # Check SSH and get info
    ssh_enabled = check_ssh_connectivity(host_ip)
    host.ssh_enabled = ssh_enabled
    
    if ssh_enabled:
        info = get_host_info(host_ip)
        if "build" in info:
            host.current_build = info["build"]
        if "hostname" in info:
            host.hostname = info["hostname"]
    
    host.last_checked = datetime.utcnow()
    db.commit()

# Patch Management Endpoints

@app.post("/api/upload-patch")
async def upload_patch(
    file: UploadFile = File(...),
    username: str = Depends(authenticate),
    db: Session = Depends(get_db)
):
    """Upload ESXi patch file"""
    try:
        # Validate file extension
        if not file.filename.endswith('.zip'):
            raise HTTPException(status_code=400, detail="Only .zip files are allowed")
        
        # Create patches directory if it doesn't exist
        patch_dir = Path("/app/patches")
        patch_dir.mkdir(exist_ok=True)
        
        # Save the file
        file_path = patch_dir / file.filename
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Also copy to ansible patches directory if it exists
        ansible_patch_dir = Path("/ansible/patches")
        if ansible_patch_dir.exists():
            shutil.copy(file_path, ansible_patch_dir / file.filename)
        
        # Record in database (optional)
        from models import Settings
        patch_record = Settings(
            key=f"patch_{file.filename}",
            value=str(datetime.utcnow()),
            updated_at=datetime.utcnow()
        )
        db.add(patch_record)
        db.commit()
        
        return {
            "message": f"Successfully uploaded {file.filename}",
            "filename": file.filename,
            "size": file_path.stat().st_size
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/patches")
async def list_patches(username: str = Depends(authenticate)):
    """List available patch files"""
    try:
        patches = []
        
        # Check both directories
        for patch_dir_path in ["/app/patches", "/ansible/patches"]:
            patch_dir = Path(patch_dir_path)
            if patch_dir.exists():
                for patch_file in patch_dir.glob("*.zip"):
                    if not any(p['filename'] == patch_file.name for p in patches):
                        patches.append({
                            "filename": patch_file.name,
                            "size": round(patch_file.stat().st_size / (1024*1024), 2),  # Size in MB
                            "uploaded": patch_file.stat().st_mtime
                        })
                break  # Use first directory that exists
        
        return patches
    except Exception as e:
        print(f"Error listing patches: {e}")
        return []

@app.delete("/api/patches/{filename}")
async def delete_patch(
    filename: str,
    username: str = Depends(authenticate),
    db: Session = Depends(get_db)
):
    """Delete a patch file"""
    try:
        deleted = False
        
        # Delete from both locations
        for patch_dir_path in ["/app/patches", "/ansible/patches"]:
            patch_path = Path(patch_dir_path) / filename
            if patch_path.exists():
                patch_path.unlink()
                deleted = True
        
        if not deleted:
            raise HTTPException(status_code=404, detail="Patch file not found")
        
        # Remove from database
        from models import Settings
        patch_record = db.query(Settings).filter_by(key=f"patch_{filename}").first()
        if patch_record:
            db.delete(patch_record)
            db.commit()
            
        return {"message": f"Deleted {filename}"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Cleanup old jobs (runs periodically)
@app.post("/api/cleanup")
async def cleanup_old_data(
    days: int = 30,
    username: str = Depends(authenticate),
    db: Session = Depends(get_db)
):
    """Clean up old job data"""
    from models import PatchingJob
    
    cutoff = datetime.utcnow() - timedelta(days=days)
    deleted = db.query(PatchingJob).filter(PatchingJob.started_at < cutoff).delete()
    db.commit()
    
    return {"message": f"Deleted {deleted} old job records"}

# API Documentation
@app.get("/")
async def root():
    """Root endpoint - redirects to API documentation"""
    return {
        "message": "ESXi Patching Orchestrator API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }

if __name__ == "__main__":
    import uvicorn
    
    # Initialize database on startup
    from database import init_db
    init_db()
    
    uvicorn.run(app, host="0.0.0.0", port=8000)
