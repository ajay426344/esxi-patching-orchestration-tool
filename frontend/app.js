// Complete Frontend JavaScript for ESXi Orchestrator
const API_URL = 'http://localhost:8000/api';
let authToken = null;
let isAdmin = false;
let refreshInterval = null;

// Authentication Functions
function showLogin() {
    document.getElementById('login-modal').style.display = 'block';
}

function closeLogin() {
    document.getElementById('login-modal').style.display = 'none';
}
async function addHosts() {
    const hostIPs = document.getElementById('host-ips').value
        .split('\n')
        .map(ip => ip.trim())
        .filter(ip => ip);
    
    // Check if auto-precheck checkbox is checked (add this to HTML)
    const autoPrecheck = document.getElementById('auto-precheck')?.checked ?? true;
    
    if (hostIPs.length === 0) {
        alert('Please enter at least one IP address');
        return;
    }
    
    // Show loading indicator
    const addButton = event.target;
    addButton.disabled = true;
    addButton.textContent = 'Adding hosts...';
    
    try {
        const response = await fetch(`${API_URL}/hosts/add?auto_precheck=${autoPrecheck}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Basic ${authToken}`
            },
            body: JSON.stringify({ ip_addresses: hostIPs })
        });
        
        if (response.ok) {
            const result = await response.json();
            
            let message = `Successfully added ${result.hosts.length} hosts`;
            if (result.precheck_status) {
                message += '\n' + result.precheck_status;
            }
            
            alert(message);
            document.getElementById('host-ips').value = '';
            loadHosts();
            
            // If auto-precheck is enabled, switch to job monitoring view
            if (autoPrecheck && result.hosts.length > 0) {
                // Scroll to running jobs section
                document.getElementById('running-jobs')?.scrollIntoView({ behavior: 'smooth' });
            }
        } else {
            const error = await response.json();
            alert('Failed to add hosts: ' + (error.detail || 'Unknown error'));
        }
    } catch (error) {
        alert('Error adding hosts: ' + error);
    } finally {
        addButton.disabled = false;
        addButton.textContent = 'Add Hosts';
    }
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
            loginSuccess();
        } else {
            alert('Invalid credentials');
            authToken = null;
        }
    } catch (error) {
        alert('Login failed: ' + error);
        authToken = null;
    }
}

function loginSuccess() {
    isAdmin = true;
    document.getElementById('admin-controls').style.display = 'block';
    
    // Show additional admin sections if they exist
    const addHostsSection = document.getElementById('add-hosts-section');
    if (addHostsSection) addHostsSection.style.display = 'block';
    
    const patchUploadSection = document.getElementById('patch-upload-section');
    if (patchUploadSection) patchUploadSection.style.display = 'block';
    
    document.getElementById('login-btn').style.display = 'none';
    document.getElementById('logout-btn').style.display = 'block';
    document.getElementById('user-info').textContent = `Logged in as: ${document.getElementById('username').value}`;
    closeLogin();
    loadData();
    loadPatchList();
}

function logout() {
    isAdmin = false;
    authToken = null;
    document.getElementById('admin-controls').style.display = 'none';
    
    const addHostsSection = document.getElementById('add-hosts-section');
    if (addHostsSection) addHostsSection.style.display = 'none';
    
    const patchUploadSection = document.getElementById('patch-upload-section');
    if (patchUploadSection) patchUploadSection.style.display = 'none';
    
    document.getElementById('login-btn').style.display = 'block';
    document.getElementById('logout-btn').style.display = 'none';
    document.getElementById('user-info').textContent = '';
}

// Host Management Functions
async function addHosts() {
    const hostIPs = document.getElementById('host-ips').value
        .split('\n')
        .map(ip => ip.trim())
        .filter(ip => ip);
    
    if (hostIPs.length === 0) {
        alert('Please enter at least one IP address');
        return;
    }
    
    // Validate IP addresses
    const ipRegex = /^(\d{1,3}\.){3}\d{1,3}$/;
    const invalidIPs = hostIPs.filter(ip => !ipRegex.test(ip));
    if (invalidIPs.length > 0) {
        alert('Invalid IP addresses: ' + invalidIPs.join(', '));
        return;
    }
    
    try {
        const response = await fetch(`${API_URL}/hosts/add`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Basic ${authToken}`
            },
            body: JSON.stringify({ ip_addresses: hostIPs })
        });
        
        if (response.ok) {
            const result = await response.json();
            alert(`Successfully added hosts: ${result.hosts.join(', ')}`);
            document.getElementById('host-ips').value = '';
            loadHosts();
        } else {
            const error = await response.json();
            alert('Failed to add hosts: ' + (error.detail || 'Unknown error'));
        }
    } catch (error) {
        alert('Error adding hosts: ' + error);
    }
}

// Patch Management Functions
async function uploadPatch() {
    const fileInput = document.getElementById('patch-file');
    const file = fileInput.files[0];
    
    if (!file) {
        alert('Please select a patch file');
        return;
    }
    
    // Validate file extension
    if (!file.name.endsWith('.zip')) {
        alert('Please select a valid ESXi depot file (.zip)');
        return;
    }
    
    const formData = new FormData();
    formData.append('file', file);
    
    // Show progress bar
    const progressDiv = document.getElementById('upload-progress');
    const statusDiv = document.getElementById('upload-status');
    
    if (progressDiv) progressDiv.style.display = 'block';
    if (statusDiv) statusDiv.innerHTML = `<span style="color: blue">Uploading ${file.name}...</span>`;
    
    try {
        const xhr = new XMLHttpRequest();
        
        // Track upload progress
        xhr.upload.addEventListener('progress', (e) => {
            if (e.lengthComputable) {
                const percentComplete = Math.round((e.loaded / e.total) * 100);
                const progressFill = document.getElementById('progress-fill');
                const progressText = document.getElementById('progress-text');
                
                if (progressFill) progressFill.style.width = percentComplete + '%';
                if (progressText) progressText.textContent = percentComplete + '%';
            }
        });
        
        xhr.onload = function() {
            if (xhr.status === 200) {
                if (statusDiv) {
                    statusDiv.innerHTML = `<span style="color: green">✓ Successfully uploaded ${file.name}</span>`;
                }
                fileInput.value = '';
                loadPatchList();
                alert('Patch uploaded successfully!');
            } else {
                if (statusDiv) {
                    statusDiv.innerHTML = `<span style="color: red">✗ Failed to upload ${file.name}</span>`;
                }
                alert('Failed to upload patch file');
            }
            if (progressDiv) progressDiv.style.display = 'none';
        };
        
        xhr.onerror = function() {
            if (statusDiv) {
                statusDiv.innerHTML = `<span style="color: red">✗ Upload error</span>`;
            }
            if (progressDiv) progressDiv.style.display = 'none';
            alert('Upload error occurred');
        };
        
        xhr.open('POST', `${API_URL}/upload-patch`);
        xhr.setRequestHeader('Authorization', `Basic ${authToken}`);
        xhr.send(formData);
        
    } catch (error) {
        if (statusDiv) {
            statusDiv.innerHTML = `<span style="color: red">✗ Error: ${error}</span>`;
        }
        if (document.getElementById('upload-progress')) {
            document.getElementById('upload-progress').style.display = 'none';
        }
        alert('Error uploading patch: ' + error);
    }
}

async function loadPatchList() {
    try {
        const response = await fetch(`${API_URL}/patches`, {
            headers: {
                'Authorization': `Basic ${authToken}`
            }
        });
        
        if (response.ok) {
            const patches = await response.json();
            const patchListDiv = document.getElementById('patch-list');
            
            if (patchListDiv) {
                if (patches.length === 0) {
                    patchListDiv.innerHTML = '<p>No patches uploaded yet</p>';
                } else {
                    patchListDiv.innerHTML = '<ul>' + 
                        patches.map(patch => 
                            `<li>
                                <strong>${patch.filename}</strong> (${patch.size} MB)
                                <br>Uploaded: ${new Date(patch.uploaded * 1000).toLocaleString()}
                                <button onclick="deletePatch('${patch.filename}')" style="margin-left: 10px;">Delete</button>
                            </li>`
                        ).join('') + 
                        '</ul>';
                }
            }
        }
    } catch (error) {
        console.error('Failed to load patches:', error);
    }
}

async function deletePatch(filename) {
    if (!confirm(`Are you sure you want to delete ${filename}?`)) {
        return;
    }
    
    try {
        const response = await fetch(`${API_URL}/patches/${filename}`, {
            method: 'DELETE',
            headers: {
                'Authorization': `Basic ${authToken}`
            }
        });
        
        if (response.ok) {
            alert('Patch deleted successfully');
            loadPatchList();
        } else {
            alert('Failed to delete patch');
        }
    } catch (error) {
        alert('Error deleting patch: ' + error);
    }
}

// Data Loading Functions
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
    const filter = document.getElementById('date-filter')?.value || 'all';
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

// UI Update Functions
function updateHostsTable(hosts) {
    const tbody = document.getElementById('hosts-tbody');
    if (!tbody) return;
    
    tbody.innerHTML = '';
    
    hosts.forEach(host => {
        const row = tbody.insertRow();
        row.innerHTML = `
            <td><input type="checkbox" class="host-checkbox" data-ip="${host.ip_address}"></td>
            <td>${host.ip_address}</td>
            <td>${host.hostname || '-'}</td>
            <td>${host.current_build || '-'}</td>
            <td>${host.target_build || '-'}</td>
            <td><span class="status ${host.status}">${host.status || 'pending'}</span></td>
            <td>${host.ssh_enabled ? '✓' : '✗'}</td>
            <td>${host.last_checked ? new Date(host.last_checked).toLocaleString() : '-'}</td>
            <td>
                <button onclick="refreshHost('${host.ip_address}')">Refresh</button>
                ${isAdmin ? `<button onclick="removeHost('${host.ip_address}')">Remove</button>` : ''}
            </td>
        `;
    });
}

function updateStatistics(hosts) {
    const totalElement = document.getElementById('total-hosts');
    const precheckElement = document.getElementById('precheck-passed');
    const phase1Element = document.getElementById('phase1-complete');
    const patchedElement = document.getElementById('fully-patched');
    
    if (totalElement) totalElement.textContent = hosts.length;
    if (precheckElement) precheckElement.textContent = hosts.filter(h => h.status === 'pre_check_passed').length;
    if (phase1Element) phase1Element.textContent = hosts.filter(h => h.status === 'phase1_completed').length;
    if (patchedElement) patchedElement.textContent = hosts.filter(h => h.status === 'patching_completed').length;
}

function updateJobsTable(jobs) {
    const tbody = document.getElementById('jobs-tbody');
    if (!tbody) return;
    
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
    if (!container) return;
    
    if (jobs.length === 0) {
        container.innerHTML = '<p>No running jobs</p>';
        return;
    }
    
    container.innerHTML = jobs.map(job => `
        <div class="job-card">
            <h4>${job.job_type} - ${job.host_ip}</h4>
            <p>Started: ${new Date(job.started_at).toLocaleString()}</p>
            <div class="progress-bar">
                <div class="progress-fill animated"></div>
            </div>
        </div>
    `).join('');
}

// Patching Actions
async function runPreChecks() {
    const selectedHosts = getSelectedHosts();
    if (selectedHosts.length === 0) {
        alert('Please select hosts');
        return;
    }
    
    if (!confirm(`Run pre-checks on ${selectedHosts.length} hosts?`)) {
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
        } else {
            alert('Failed to initiate pre-checks');
        }
    } catch (error) {
        alert('Failed to initiate pre-checks: ' + error);
    }
}

async function runPhase1() {
    const selectedHosts = getSelectedHosts();
    const patchFile = document.getElementById('patch-file')?.files[0];
    
    // Check for selected patch in dropdown if file not selected
    const selectedPatch = document.getElementById('selected-patch')?.value;
    
    if (!patchFile && !selectedPatch) {
        alert('Please select or upload a patch file first');
        return;
    }
    
    if (selectedHosts.length === 0) {
        alert('Please select hosts');
        return;
    }
    
    if (!confirm(`Execute Phase 1 on ${selectedHosts.length} hosts?`)) {
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
                patch_file: patchFile?.name || selectedPatch
            })
        });
        
        if (response.ok) {
            alert('Phase 1 initiated');
            loadData();
        } else {
            alert('Failed to initiate Phase 1');
        }
    } catch (error) {
        alert('Failed to initiate Phase 1: ' + error);
    }
}

async function runPhase2() {
    const selectedHosts = getSelectedHosts();
    
    if (selectedHosts.length === 0) {
        alert('Please select hosts');
        return;
    }
    
    if (!confirm(`Execute Phase 2 (reboot) on ${selectedHosts.length} hosts?`)) {
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
            alert('Phase 2 initiated - hosts will reboot');
            loadData();
        } else {
            alert('Failed to initiate Phase 2');
        }
    } catch (error) {
        alert('Failed to initiate Phase 2: ' + error);
    }
}

// Host Actions
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

async function removeHost(ip) {
    if (!confirm(`Remove host ${ip}?`)) {
        return;
    }
    
    try {
        const response = await fetch(`${API_URL}/hosts/${ip}`, {
            method: 'DELETE',
            headers: {
                'Authorization': `Basic ${authToken}`
            }
        });
        
        if (response.ok) {
            alert('Host removed');
            loadData();
        } else {
            alert('Failed to remove host');
        }
    } catch (error) {
        alert('Error removing host: ' + error);
    }
}

async function refreshAll() {
    if (!confirm('Refresh all hosts? This may take a while.')) {
        return;
    }
    
    try {
        const response = await fetch(`${API_URL}/hosts`);
        const hosts = await response.json();
        
        for (const host of hosts) {
            await refreshHost(host.ip_address);
        }
        
        loadData();
        alert('All hosts refreshed');
    } catch (error) {
        console.error('Failed to refresh all hosts:', error);
    }
}

// Settings Functions
async function saveSettings() {
    const thresholdWindow = document.getElementById('threshold-window')?.value;
    const gracePeriod = document.getElementById('grace-period')?.value;
    
    const settings = {
        'auto_phase2_window': thresholdWindow || '10',
        'reboot_grace_period': gracePeriod || '2'
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
            alert('Settings saved successfully');
        } else {
            alert('Failed to save settings');
        }
    } catch (error) {
        alert('Failed to save settings: ' + error);
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

// Auto-refresh Functions
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

// Select All Functionality
document.addEventListener('DOMContentLoaded', function() {
    // Select all checkbox
    const selectAllCheckbox = document.getElementById('select-all');
    if (selectAllCheckbox) {
        selectAllCheckbox.addEventListener('change', function() {
            const checkboxes = document.querySelectorAll('.host-checkbox');
            checkboxes.forEach(cb => cb.checked = this.checked);
        });
    }
    
    // Initialize application
    loadData();
    startAutoRefresh();
    
    // Check for existing auth (development)
    const savedAuth = localStorage.getItem('authToken');
    if (savedAuth) {
        authToken = savedAuth;
        // Verify token is still valid
        fetch(`${API_URL}/hosts`, {
            headers: { 'Authorization': `Basic ${authToken}` }
        }).then(response => {
            if (response.ok) {
                loginSuccess();
            } else {
                localStorage.removeItem('authToken');
                authToken = null;
            }
        });
    }
});

// Export functions for testing (optional)
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        addHosts,
        uploadPatch,
        runPreChecks,
        runPhase1,
        runPhase2
    };
}
