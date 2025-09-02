const API_URL = 'http://localhost:8000/api';
let authToken = null;
let isAdmin = false;
let refreshInterval = null;

// Authentication
function showLogin() {
    document.getElementById('login-modal').style.display = 'block';
}

function closeLogin() {
    document.getElementById('login-modal').style.display = 'none';
}

async function login() {
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;
    
    authToken = btoa(`${username}:${password}`);
    
    try {
        const response = await fetch(`${API_URL}/hosts`, {
            headers: {
                'Authorization': `Basic ${authToken}`
            }
        });
        
        if (response.ok) {
            isAdmin = true;
            document.getElementById('admin-controls').style.display = 'block';
            document.getElementById('login-btn').style.display = 'none';
            document.getElementById('logout-btn').style.display = 'block';
            document.getElementById('user-info').textContent = `Logged in as: ${username}`;
            closeLogin();
            loadData();
        } else {
            alert('Invalid credentials');
            authToken = null;
        }
    } catch (error) {
        alert('Login failed');
        authToken = null;
    }
}

function logout() {
    isAdmin = false;
    authToken = null;
    document.getElementById('admin-controls').style.display = 'none';
    document.getElementById('login-btn').style.display = 'block';
    document.getElementById('logout-btn').style.display = 'none';
    document.getElementById('user-info').textContent = '';
}

// Data Loading
async function loadData() {
    await loadHosts();
    await loadJobs();
}

async function loadHosts() {
    try {
        const response = await fetch(`${API_URL}/hosts`);
        const hosts = await response.json();
        
        updateHostsTable(hosts);
        updateStatistics(hosts);
    } catch (error) {
        console.error('Failed to load hosts:', error);
    }
}

async function loadJobs() {
    const filter = document.getElementById('date-filter').value;
    let url = `${API_URL}/jobs`;
    
    if (filter !== 'all') {
        url += `?filter_days=${parseInt(filter) / 24}`;
    }
    
    try {
        const response = await fetch(url);
        const jobs = await response.json();
        
        updateJobsTable(jobs);
        updateRunningJobs(jobs.filter(j => j.status === 'running'));
    } catch (error) {
        console.error('Failed to load jobs:', error);
    }
}

// UI Updates
function updateHostsTable(hosts) {
    const tbody = document.getElementById('hosts-tbody');
    tbody.innerHTML = '';
    
    hosts.forEach(host => {
        const row = tbody.insertRow();
        row.innerHTML = `
            <td><input type="checkbox" class="host-checkbox" data-ip="${host.ip_address}"></td>
            <td>${host.ip_address}</td>
            <td>${host.hostname || '-'}</td>
            <td>${host.current_build || '-'}</td>
            <td>${host.target_build || '-'}</td>
            <td><span class="status ${host.status}">${host.status}</span></td>
            <td>${host.ssh_enabled ? '✓' : '✗'}</td>
            <td>${new Date(host.last_checked).toLocaleString()}</td>
            <td>
                <button onclick="refreshHost('${host.ip_address}')">Refresh</button>
            </td>
        `;
    });
}

function updateStatistics(hosts) {
    document.getElementById('total-hosts').textContent = hosts.length;
    document.getElementById('precheck-passed').textContent = 
        hosts.filter(h => h.status === 'pre_check_passed').length;
    document.getElementById('phase1-complete').textContent = 
        hosts.filter(h => h.status === 'phase1_completed').length;
    document.getElementById('fully-patched').textContent = 
        hosts.filter(h => h.status === 'patching_completed').length;
}

function updateJobsTable(jobs) {
    const tbody = document.getElementById('jobs-tbody');
    tbody.innerHTML = '';
    
    jobs.forEach(job => {
        const row = tbody.insertRow();
        row.innerHTML = `
            <td>${job.host_ip}</td>
            <td>${job.job_type}</td>
            <td><span class="status ${job.status}">${job.status}</span></td>
            <td>${new Date(job.started_at).toLocaleString()}</td>
            <td>${job.completed_at ? new Date(job.completed_at).toLocaleString() : '-'}</td>
            <td>${job.error_message || '-'}</td>
        `;
    });
}

function updateRunningJobs(jobs) {
    const container = document.getElementById('running-jobs');
    
    if (jobs.length === 0) {
        container.innerHTML = '<p>No running jobs</p>';
        return;
    }
    
    container.innerHTML = jobs.map(job => `
        <div class="job-card">
            <h4>${job.job_type} - ${job.host_ip}</h4>
            <p>Started: ${new Date(job.started_at).toLocaleString()}</p>
            <div class="progress-bar">
                <div class="progress-fill"></div>
            </div>
        </div>
    `).join('');
}

// Actions
async function runPreChecks() {
    const selectedHosts = getSelectedHosts();
    if (selectedHosts.length === 0) {
        alert('Please select hosts');
        return;
    }
    
    try {
        const response = await fetch(`${API_URL}/precheck`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Basic ${authToken}`
            },
            body: JSON.stringify({ ip_addresses: selectedHosts })
        });
        
        if (response.ok) {
            alert('Pre-checks initiated');
            loadData();
        }
    } catch (error) {
        alert('Failed to initiate pre-checks');
    }
}

async function runPhase1() {
    const selectedHosts = getSelectedHosts();
    const patchFile = document.getElementById('patch-file').files[0];
    
    if (!patchFile) {
        alert('Please upload a patch file first');
        return;
    }
    
    if (selectedHosts.length === 0) {
        alert('Please select hosts');
        return;
    }
    
    try {
        const response = await fetch(`${API_URL}/patch/phase1`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Basic ${authToken}`
            },
            body: JSON.stringify({ 
                hosts: selectedHosts,
                patch_file: patchFile.name
            })
        });
        
        if (response.ok) {
            alert('Phase 1 initiated');
            loadData();
        }
    } catch (error) {
        alert('Failed to initiate Phase 1');
    }
}

async function runPhase2() {
    const selectedHosts = getSelectedHosts();
    
    if (selectedHosts.length === 0) {
        alert('Please select hosts');
        return;
    }
    
    try {
        const response = await fetch(`${API_URL}/patch/phase2`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Basic ${authToken}`
            },
            body: JSON.stringify({ hosts: selectedHosts })
        });
        
        if (response.ok) {
            alert('Phase 2 initiated');
            loadData();
        }
    } catch (error) {
        alert('Failed to initiate Phase 2');
    }
}

async function refreshHost(ip) {
    try {
        const response = await fetch(`${API_URL}/refresh/${ip}`, {
            method: 'POST'
        });
        
        if (response.ok) {
            loadData();
        }
    } catch (error) {
        console.error('Failed to refresh host:', error);
    }
}

async function refreshAll() {
    try {
        const response = await fetch(`${API_URL}/hosts`);
        const hosts = await response.json();
        
        for (const host of hosts) {
            await refreshHost(host.ip_address);
        }
        
        loadData();
    } catch (error) {
        console.error('Failed to refresh all hosts:', error);
    }
}

async function saveSettings() {
    const settings = {
        'auto_phase2_window': document.getElementById('threshold-window').value,
        'reboot_grace_period': document.getElementById('grace-period').value
    };
    
    try {
        const response = await fetch(`${API_URL}/settings`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Basic ${authToken}`
            },
            body: JSON.stringify(settings)
        });
        
        if (response.ok) {
            alert('Settings saved');
        }
    } catch (error) {
        alert('Failed to save settings');
    }
}

// Helper Functions
function getSelectedHosts() {
    const checkboxes = document.querySelectorAll('.host-checkbox:checked');
    return Array.from(checkboxes).map(cb => cb.dataset.ip);
}

function filterData() {
    loadJobs();
}

// Select All functionality
document.getElementById('select-all').addEventListener('change', function() {
    const checkboxes = document.querySelectorAll('.host-checkbox');
    checkboxes.forEach(cb => cb.checked = this.checked);
});

// Auto-refresh every 2 seconds
function startAutoRefresh() {
    refreshInterval = setInterval(() => {
        loadData();
    }, 2000);
}

function stopAutoRefresh() {
    if (refreshInterval) {
        clearInterval(refreshInterval);
        refreshInterval = null;
    }
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    loadData();
    startAutoRefresh();
});
