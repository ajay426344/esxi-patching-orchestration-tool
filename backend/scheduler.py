from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import requests

scheduler = BackgroundScheduler()

def scheduled_phase2_check():
    """Check hosts that need Phase 2 execution"""
    try:
        # Get hosts in phase1_completed state
        response = requests.get("http://localhost:8000/api/hosts")
        hosts = response.json()
        
        phase1_hosts = [h for h in hosts if h['status'] == 'phase1_completed']
        
        for host in phase1_hosts:
            # Check if threshold window passed
            completed_time = datetime.fromisoformat(host['last_checked'])
            if (datetime.utcnow() - completed_time).seconds > 600:  # 10 minutes
                # Trigger Phase 2
                requests.post(
                    "http://localhost:8000/api/patch/phase2",
                    json={"hosts": [host['ip_address']]},
                    auth=("ajay", "Ajay@426344")
                )
    except Exception as e:
        print(f"Scheduled check error: {e}")

# Schedule job every 12 hours
scheduler.add_job(scheduled_phase2_check, 'interval', hours=12)
scheduler.start()

if __name__ == "__main__":
    import time
    while True:
        time.sleep(1)
