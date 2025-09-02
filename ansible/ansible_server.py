from flask import Flask, request, jsonify
import subprocess
import json
import yaml
import os

app = Flask(__name__)

@app.route('/run-playbook', methods=['POST'])
def run_playbook():
    try:
        data = request.json
        playbook = data.get('playbook')
        inventory = data.get('inventory')
        extra_vars = data.get('extra_vars', {})
        
        # Validate playbook exists
        playbook_path = f'/ansible/playbooks/{playbook}'
        if not os.path.exists(playbook_path):
            return jsonify({'error': f'Playbook {playbook} not found'}), 404
        
        # Build ansible-playbook command
        cmd = [
            'ansible-playbook',
            playbook_path,
            '-i', ','.join(inventory) + ',',
        ]
        
        # Add extra variables if provided
        if extra_vars:
            cmd.extend(['--extra-vars', json.dumps(extra_vars)])
        
        # Execute playbook
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        return jsonify({
            'success': result.returncode == 0,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'return_code': result.returncode
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy'}), 200

@app.route('/test-connectivity', methods=['POST'])
def test_connectivity():
    try:
        data = request.json
        host = data.get('host')
        
        cmd = ['ansible', host, '-m', 'ping', '-i', f'{host},']
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        return jsonify({
            'success': result.returncode == 0,
            'output': result.stdout
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5555, debug=False)
