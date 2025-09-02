FROM python:3.11-slim

WORKDIR /ansible

# Install Ansible and dependencies
RUN apt-get update && apt-get install -y \
    openssh-client \
    sshpass \
    git \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    ansible==8.5.0 \
    ansible-core==2.15.5 \
    paramiko==3.4.0 \
    pyvmomi==8.0.2.0 \
    flask==3.0.0

# Copy Ansible configuration
COPY ansible.cfg /etc/ansible/ansible.cfg

# Copy playbooks and inventory
COPY . /ansible

# Create ansible server script
RUN cat > /ansible/ansible_server.py << 'EOF'
from flask import Flask, request, jsonify
import subprocess
import json

app = Flask(__name__)

@app.route('/run-playbook', methods=['POST'])
def run_playbook():
    data = request.json
    playbook = data.get('playbook')
    inventory = data.get('inventory')
    extra_vars = data.get('extra_vars', {})
    
    cmd = [
        'ansible-playbook',
        f'/ansible/playbooks/{playbook}',
        '-i', ','.join(inventory) + ',',
        '--extra-vars', json.dumps(extra_vars)
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    return jsonify({
        'success': result.returncode == 0,
        'stdout': result.stdout,
        'stderr': result.stderr
    })

@app.route('/health', methods=['GET'])
def health():
    return 'OK', 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5555)
EOF

EXPOSE 5555

CMD ["python", "/ansible/ansible_server.py"]
