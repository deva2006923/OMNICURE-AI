/* OmniCure AI - Clinical Dashboard System Script */
let currentUser = null;
let currentReportId = null;
let authMode = 'login'; // 'login' or 'register'
let verifyingEmail = null;
let activeTab = 'dashboard';

document.addEventListener('DOMContentLoaded', () => {
    // Initialize session state
    currentUser = JSON.parse(localStorage.getItem('currentUser')) || null;
    initSession();

    const dropZone = document.getElementById('dropZone');
    const fileInput = document.getElementById('fileInput');

    if (dropZone) {
        dropZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropZone.classList.add('dragover');
        });

        dropZone.addEventListener('dragleave', () => {
            dropZone.classList.remove('dragover');
        });

        dropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropZone.classList.remove('dragover');
            if (e.dataTransfer.files.length) {
                handleFileUpload(e.dataTransfer.files[0]);
            }
        });
    }

    if (fileInput) {
        fileInput.addEventListener('change', (e) => {
            if (e.target.files.length) {
                handleFileUpload(e.target.files[0]);
            }
        });
    }
});

function initSession() {
    const authOverlay = document.getElementById('authOverlay');
    const sidebar = document.getElementById('appSidebar');

    if (currentUser) {
        // Logged In State
        authOverlay.classList.add('hidden');
        sidebar.classList.remove('hidden');
        
        document.getElementById('navUsername').innerText = currentUser.username;
        document.getElementById('sidebarAvatar').innerText = currentUser.username.charAt(0).toUpperCase();
        
        const roleBadge = document.getElementById('navRoleBadge');
        roleBadge.innerText = currentUser.role;
        
        const adminTabBtn = document.getElementById('btnNav-admin');
        const settingsTabBtn = document.getElementById('btnNav-settings');
        if (currentUser.role === 'admin') {
            adminTabBtn.classList.remove('hidden');
            settingsTabBtn.classList.remove('hidden');
            showTab('admin');
        } else {
            adminTabBtn.classList.add('hidden');
            settingsTabBtn.classList.add('hidden');
            showTab('dashboard');
        }
    } else {
        // Not Logged In State
        authOverlay.classList.remove('hidden');
        sidebar.classList.add('hidden');
        
        // Hide all tabs
        document.querySelectorAll('.tab-content').forEach(tab => {
            tab.classList.add('hidden');
        });
    }
    
    if (window.lucide) {
        window.lucide.createIcons();
    }
}

// SPA Tab Navigation Router
function showTab(tabName) {
    activeTab = tabName;
    
    // Hide all tabs
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.classList.add('hidden');
    });
    
    // Deactivate all sidebar items
    document.querySelectorAll('.sidebar-item').forEach(btn => {
        btn.classList.remove('active');
    });
    
    // Show selected tab content
    const activeTabEl = document.getElementById(`tab-${tabName}`);
    if (activeTabEl) {
        activeTabEl.classList.remove('hidden');
    }
    
    // Mark sidebar navigation item as active
    const activeBtn = document.getElementById(`btnNav-${tabName}`);
    if (activeBtn) {
        activeBtn.classList.add('active');
    }
    
    // Load dynamic telemetry based on tab context
    if (tabName === 'history') {
        fetchReportHistory();
    } else if (tabName === 'admin') {
        fetchAdminUsers();
        fetchMockEmails();
    } else if (tabName === 'settings') {
        fetchConfig();
    }
}

// Authentication toggle
function toggleAuthMode(isRegister) {
    const title = document.getElementById('authTitle');
    const subtitle = document.getElementById('authSubtitle');
    const btn = document.getElementById('btnAuthSubmit');
    const toggleText = document.getElementById('authToggleText');
    const roleSelectorGroup = document.getElementById('authRoleSelectorGroup');

    // Reset verification states
    document.getElementById('authVerifyForm').classList.add('hidden');
    document.getElementById('authMainForm').classList.remove('hidden');
    document.getElementById('authToggleContainer').classList.remove('hidden');
    document.getElementById('authOtp').value = '';
    verifyingEmail = null;

    if (isRegister) {
        authMode = 'register';
        title.innerText = 'Create Account';
        subtitle.innerText = 'Register to index and analyze your medical sheets';
        btn.innerText = 'Register';
        toggleText.innerHTML = 'Already have an account? <span onclick="toggleAuthMode(false)">Sign In</span>';
        if (roleSelectorGroup) {
            roleSelectorGroup.classList.remove('hidden');
            setSignUpRole('user');
        }
    } else {
        authMode = 'login';
        title.innerText = 'Sign In';
        subtitle.innerText = 'Access your medical report intelligence suite';
        btn.innerText = 'Sign In';
        toggleText.innerHTML = 'Don\'t have an account? <span onclick="toggleAuthMode(true)">Create Account</span>';
        if (roleSelectorGroup) {
            roleSelectorGroup.classList.add('hidden');
        }
        document.getElementById('authRole').value = 'user';
    }
    
    if (window.lucide) {
        window.lucide.createIcons();
    }
}

function setSignUpRole(role) {
    document.getElementById('authRole').value = role;
    const buttons = document.querySelectorAll('.role-selector .role-btn');
    buttons.forEach(btn => {
        if (btn.getAttribute('data-role') === role) {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    });
}

// Submit Authentication Request
async function handleAuthSubmit(event) {
    event.preventDefault();
    const username = document.getElementById('authUsername').value.trim();
    const password = document.getElementById('authPassword').value;
    const role = document.getElementById('authRole').value;

    if (!username || !password) return;

    const endpoint = authMode === 'register' ? '/api/auth/register' : '/api/auth/login';
    const payload = authMode === 'register' 
        ? { username, password, role } 
        : { username, password };

    try {
        const res = await fetch(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || 'Authentication failed');
        }

        const data = await res.json();
        
        if (authMode === 'register') {
            if (data.verification_required === false) {
                currentUser = data.user;
                localStorage.setItem('currentUser', JSON.stringify(currentUser));
                
                // Clear forms
                document.getElementById('authUsername').value = '';
                document.getElementById('authPassword').value = '';
                
                initSession();
            } else {
                // Success response. The verification code is sent. Securely prompt verification screen.
                showVerificationScreen(username);
            }
        } else {
            if (data.verification_required) {
                showVerificationScreen(username);
            } else {
                currentUser = data;
                localStorage.setItem('currentUser', JSON.stringify(currentUser));
                
                // Clear forms
                document.getElementById('authUsername').value = '';
                document.getElementById('authPassword').value = '';
                
                initSession();
            }
        }
    } catch (err) {
        alert(err.message);
    }
}

function showVerificationScreen(email) {
    verifyingEmail = email;
    
    document.getElementById('authTitle').innerText = 'Confirm Email';
    document.getElementById('authSubtitle').innerText = `Enter the 6-digit OTP verification code sent to ${email}`;
    
    document.getElementById('authMainForm').classList.add('hidden');
    document.getElementById('authToggleContainer').classList.add('hidden');
    document.getElementById('authVerifyForm').classList.remove('hidden');
    document.getElementById('authOtp').value = '';
    document.getElementById('authOtp').focus();
}

async function handleVerifySubmit(event) {
    event.preventDefault();
    const otp = document.getElementById('authOtp').value.trim();
    if (!otp || !verifyingEmail) return;

    try {
        const res = await fetch('/api/auth/verify', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username: verifyingEmail, otp: otp })
        });

        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || 'Verification code invalid');
        }

        const user = await res.json();
        currentUser = user;
        localStorage.setItem('currentUser', JSON.stringify(currentUser));

        // Reset forms
        document.getElementById('authVerifyForm').classList.add('hidden');
        document.getElementById('authMainForm').classList.remove('hidden');
        document.getElementById('authToggleContainer').classList.remove('hidden');
        
        document.getElementById('authUsername').value = '';
        document.getElementById('authPassword').value = '';
        document.getElementById('authOtp').value = '';
        verifyingEmail = null;

        initSession();
    } catch (err) {
        alert(err.message);
    }
}

function cancelVerification() {
    verifyingEmail = null;
    toggleAuthMode(false);
}

function logout() {
    localStorage.removeItem('currentUser');
    currentUser = null;
    currentReportId = null;
    initSession();
}

// Fetch Reports History list
async function fetchReportHistory(filterUserId = null) {
    if (!currentUser) return;
    try {
        const res = await fetch('/api/reports', {
            headers: {
                'X-User-Id': currentUser.id,
                'X-User-Role': currentUser.role
            }
        });
        if (!res.ok) throw new Error("Failed to fetch reports archive");

        const data = await res.json();
        let reports = data.reports || [];

        if (filterUserId !== null) {
            reports = reports.filter(r => r.user_id === filterUserId);
        }

        const listEl = document.getElementById('sidebarReportList');
        listEl.innerHTML = '';

        if (reports.length === 0) {
            listEl.innerHTML = '<p style="color: var(--text-muted); font-size: 0.9rem; text-align: center; grid-column: 1/-1; padding: 3rem 0;">No reports found in archive.</p>';
            return;
        }

        reports.forEach(r => {
            const formattedDate = new Date(r.uploaded_at).toLocaleDateString(undefined, {
                month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit'
            });
            const sub = r.username ? `Patient: ${r.username}` : 'Processed';
            const activeClass = currentReportId === r.id ? 'active' : '';
            
            listEl.innerHTML += `
                <div class="report-card ${activeClass}" onclick="loadReport(${r.id})">
                    <div class="report-card-header">
                        <i data-lucide="file-text" style="color: var(--accent); margin-top: 0.1rem; width: 18px; height: 18px;"></i>
                        <div class="report-card-info">
                            <strong>${r.filename}</strong>
                            <span>${sub}</span>
                        </div>
                    </div>
                    <div class="report-card-footer">
                        <span>${formattedDate}</span>
                        <span style="color: var(--accent); font-weight: 600; display: inline-flex; align-items: center; gap: 0.2rem;">
                            View Metrics <i data-lucide="chevron-right" style="width: 12px; height: 12px;"></i>
                        </span>
                    </div>
                </div>
            `;
        });
        
        if (window.lucide) {
            window.lucide.createIcons();
        }
    } catch (err) {
        console.error("Error loading report archive:", err);
    }
}

// Load a specific Report
async function loadReport(reportId) {
    try {
        const res = await fetch(`/api/reports/${reportId}`, {
            headers: {
                'X-User-Id': currentUser.id,
                'X-User-Role': currentUser.role
            }
        });
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || "Failed to load report file");
        }

        const report = await res.json();
        currentReportId = report.id;

        // Switch active SPA tab to Dashboard
        showTab('dashboard');

        // Hide upload view panel, display analysis dashboard panels
        document.getElementById('uploadPanel').classList.add('hidden');
        document.getElementById('dashboardPanel').classList.remove('hidden');
        document.getElementById('dashboardReportName').innerText = report.filename;
        document.getElementById('dashboardReportDate').innerText = new Date(report.uploaded_at).toLocaleString();

        // Populate dashboard components
        populateDashboard(report.analysis || { metrics: [], abnormalities: [], predictions: [] });

        // Load Chat logs
        const chatWindow = document.getElementById('chatWindow');
        chatWindow.innerHTML = '';
        
        chatWindow.innerHTML = `
            <div class="chat-message bot">
                <p>I have processed the lab report. Ask me any clinical questions regarding ranges, flags, or potential recommendations.</p>
            </div>
        `;

        if (report.chat_history && report.chat_history.length > 0) {
            report.chat_history.forEach(msg => {
                appendMessage(msg.message, msg.sender);
            });
        }
    } catch (err) {
        alert("Error loading report: " + err.message);
    }
}

// Reset panel to fresh upload state
function resetToUpload() {
    currentReportId = null;
    document.getElementById('dashboardPanel').classList.add('hidden');
    document.getElementById('uploadPanel').classList.remove('hidden');
    document.getElementById('dropZone').classList.remove('hidden');
    document.getElementById('uploadStatus').classList.add('hidden');
}

// File Upload handler
async function handleFileUpload(file) {
    if (!currentUser) return;
    if (!file.name.toLowerCase().endsWith('.pdf') && !file.name.toLowerCase().endsWith('.txt')) {
        alert("Supported formats are PDF and TXT laboratory files only.");
        return;
    }

    document.getElementById('dropZone').classList.add('hidden');
    document.getElementById('uploadStatus').classList.remove('hidden');

    const formData = new FormData();
    formData.append('file', file);

    try {
        const uploadRes = await fetch('/api/upload', {
            method: 'POST',
            headers: {
                'X-User-Id': currentUser.id
            },
            body: formData
        });
        
        if (!uploadRes.ok) {
            const err = await uploadRes.json();
            throw new Error(err.detail || "Upload failed");
        }

        const result = await uploadRes.json();
        await fetchAnalysis(result.report_id);

    } catch (err) {
        alert("Error: " + err.message);
        resetToUpload();
    }
}

// Run report analysis API
async function fetchAnalysis(reportId) {
    try {
        currentReportId = reportId;
        const res = await fetch(`/api/analyze?report_id=${reportId}`);
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || "Diagnostic analysis query failed");
        }
        
        const data = await res.json();
        const analysis = data.analysis;
        
        document.getElementById('uploadPanel').classList.add('hidden');
        document.getElementById('dashboardPanel').classList.remove('hidden');
        document.getElementById('uploadStatus').classList.add('hidden');
        
        document.getElementById('dashboardReportName').innerText = "Analyzing finished";
        document.getElementById('dashboardReportDate').innerText = new Date().toLocaleString();
        
        const demoBanner = document.getElementById('demoBanner');
        if (analysis && analysis.demo_mode) {
            demoBanner.classList.remove('hidden');
        } else {
            demoBanner.classList.add('hidden');
        }
        
        populateDashboard(analysis);
        
    } catch (err) {
        alert("Error: " + err.message);
        resetToUpload();
    }
}

// Populate UI Dashboard widgets
function populateDashboard(data) {
    // 1. Predictions Stack
    const predList = document.getElementById('predictionsList');
    predList.innerHTML = '';
    if (data.predictions && data.predictions.length > 0) {
        data.predictions.forEach(p => {
            const riskStr = (p.risk_level || 'low').toLowerCase();
            const riskClass = 'risk-' + riskStr;
            predList.innerHTML += `
                <div class="prediction-item">
                    <div class="pred-header">
                        <h4>${p.disease}</h4>
                        <span class="risk-badge ${riskClass}">${p.risk_level} Risk</span>
                    </div>
                    <p style="color: var(--text-muted); font-size: 0.9rem;">${p.reason}</p>
                </div>
            `;
        });
    } else {
        predList.innerHTML = '<p style="color: var(--text-muted); font-size: 0.9rem;">No diagnostic conditions identified.</p>';
    }

    // 2. Detected Abnormalities
    const abList = document.getElementById('abnormalitiesList');
    abList.innerHTML = '';
    if (data.abnormalities && data.abnormalities.length > 0) {
        data.abnormalities.forEach(a => {
            abList.innerHTML += `
                <li>
                    <i data-lucide="alert-circle" style="width: 14px; height: 14px; flex-shrink: 0; color: #f87171; margin-top: 2px;"></i>
                    <span>${a}</span>
                </li>
            `;
        });
    } else {
        abList.innerHTML = '<p style="color: var(--text-muted); font-size: 0.9rem; padding: 0.5rem 0;">No laboratory ranges marked abnormal.</p>';
    }

    // 3. Lab Metrics
    const mList = document.getElementById('metricsList');
    mList.innerHTML = '';
    if (data.metrics && data.metrics.length > 0) {
        data.metrics.forEach(m => {
            mList.innerHTML += `
                <div class="metric-box">
                    <span>${m.name}</span>
                    <strong>${m.value}</strong>
                </div>
            `;
        });
    } else {
        mList.innerHTML = '<p style="color: var(--text-muted); font-size: 0.9rem; grid-column: 1/-1;">No metrics extracted.</p>';
    }
    
    if (window.lucide) {
        window.lucide.createIcons();
    }
}

// Chat functions
async function sendChatMessage() {
    if (!currentUser || !currentReportId) return;
    const input = document.getElementById('chatInput');
    const text = input.value.trim();
    if (!text) return;
    
    appendMessage(text, 'user');
    input.value = '';
    
    try {
        const res = await fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-User-Id': currentUser.id
            },
            body: JSON.stringify({ 
                report_id: currentReportId,
                message: text 
            })
        });
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || "Chat request failed");
        }
        const data = await res.json();
        appendMessage(data.reply, 'bot');
    } catch(err) {
        appendMessage("Error communicating with AI: " + err.message, 'bot');
    }
}

function handleChatEnter(e) {
    if (e.key === 'Enter') {
        sendChatMessage();
    }
}

function sendQuickPrompt(promptText) {
    document.getElementById('chatInput').value = promptText;
    sendChatMessage();
}

// Admin Users table fetcher
async function fetchAdminUsers() {
    if (!currentUser || currentUser.role !== 'admin') return;
    try {
        const res = await fetch('/api/admin/users', {
            headers: {
                'X-User-Role': currentUser.role
            }
        });
        if (!res.ok) throw new Error("Failed to load user directory");

        const data = await res.json();
        const users = data.users || [];

        const tableBody = document.getElementById('adminUsersTableBody');
        tableBody.innerHTML = '';

        users.forEach(u => {
            const formattedDate = u.created_at
                ? new Date(u.created_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
                : 'N/A';
            const badgeStyle = u.role === 'admin' 
                ? 'background: rgba(239, 68, 68, 0.1); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.2);'
                : 'background: rgba(6, 182, 212, 0.1); color: var(--accent); border: 1px solid rgba(6, 182, 212, 0.2);';

            tableBody.innerHTML += `
                <tr>
                    <td><strong>${u.username}</strong></td>
                    <td><span class="status-indicator" style="${badgeStyle}">${u.role}</span></td>
                    <td style="color: var(--text-muted);">${formattedDate}</td>
                    <td><span style="font-weight: bold; color: var(--accent);">${u.report_count}</span> files</td>
                    <td>
                        <button class="btn-action" onclick="viewUserHistory(${u.id}, '${u.username}')">
                            <i data-lucide="eye" style="vertical-align: middle; margin-right: 4px; width: 14px; height: 14px;"></i> Open Archive
                        </button>
                    </td>
                </tr>
            `;
        });
        
        if (window.lucide) {
            window.lucide.createIcons();
        }
    } catch (err) {
        console.error("Error fetching user lists:", err);
    }
}

function viewUserHistory(userId, username) {
    showTab('history');
    fetchReportHistory(userId);
    const searchBar = document.getElementById('historySearchInput');
    if (searchBar) {
        searchBar.value = '';
    }
}

// Fetch Admin Mock Verification Inbox
async function fetchMockEmails() {
    if (!currentUser || currentUser.role !== 'admin') return;
    try {
        const res = await fetch('/api/admin/mock-emails', {
            headers: {
                'X-User-Role': currentUser.role
            }
        });
        if (!res.ok) throw new Error("Failed to load mock sandbox inbox logs");
        const data = await res.json();
        
        const listEl = document.getElementById('adminMockEmailsList');
        listEl.innerHTML = '';
        
        if (!data.emails || data.emails.length === 0) {
            listEl.innerHTML = '<p style="color: var(--text-muted); font-size: 0.9rem; text-align: center; padding: 2rem 0;">Sandbox inbox is clean.</p>';
            return;
        }
        
        data.emails.forEach(email => {
            if (email.raw) {
                listEl.innerHTML += `
                    <div class="mock-email-card">
                        <div class="mock-email-card-body">${email.raw}</div>
                    </div>
                `;
            } else {
                listEl.innerHTML += `
                    <div class="mock-email-card">
                        <div class="mock-email-card-header">
                            <span>To: <strong>${email.to}</strong></span>
                            <span>${email.timestamp}</span>
                        </div>
                        <div class="mock-email-card-body">
                            <span>OTP verification generated</span>
                            <span class="mock-otp-badge">${email.otp}</span>
                        </div>
                    </div>
                `;
            }
        });
    } catch (err) {
        console.error("Error loading mock inbox:", err);
    }
}

// Fetch API config settings
async function fetchConfig() {
    if (!currentUser || currentUser.role !== 'admin') return;
    try {
        const res = await fetch('/api/admin/config', {
            headers: {
                'X-User-Role': currentUser.role
            }
        });
        if (!res.ok) throw new Error("Failed to load system config details");
        const config = await res.json();
        
        document.getElementById('configApiKey').value = config.groq_api_key;
        document.getElementById('configSmtpEmail').value = config.smtp_email;
        document.getElementById('configSmtpPassword').value = config.smtp_password;
        document.getElementById('configSmtpHost').value = config.smtp_host || 'smtp.gmail.com';
        document.getElementById('configSmtpPort').value = config.smtp_port || '465';
        
        // Status badges updates
        const gBadge = document.getElementById('statusGroqBadge');
        if (config.groq_api_key_configured) {
            gBadge.className = 'status-indicator ok';
            gBadge.innerText = 'Connected';
        } else {
            gBadge.className = 'status-indicator unconfigured';
            gBadge.innerText = 'Demo Mock Mode';
        }
        
        const sBadge = document.getElementById('statusSmtpBadge');
        if (config.smtp_configured) {
            sBadge.className = 'status-indicator ok';
            sBadge.innerText = 'Active (Live)';
        } else {
            sBadge.className = 'status-indicator unconfigured';
            sBadge.innerText = 'Mock Fallback';
        }
    } catch (err) {
        console.error("Error loading configuration values:", err);
    }
}

// Submit configurations changes
async function handleConfigSubmit(event) {
    event.preventDefault();
    if (!currentUser || currentUser.role !== 'admin') return;
    
    const apiKey = document.getElementById('configApiKey').value.trim();
    const smtpHost = document.getElementById('configSmtpHost').value.trim();
    const smtpPort = document.getElementById('configSmtpPort').value.trim();
    const smtpEmail = document.getElementById('configSmtpEmail').value.trim();
    const smtpPassword = document.getElementById('configSmtpPassword').value.trim();
    
    try {
        const res = await fetch('/api/admin/config', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-User-Role': currentUser.role
            },
            body: JSON.stringify({
                groq_api_key: apiKey,
                smtp_host: smtpHost,
                smtp_port: smtpPort,
                smtp_email: smtpEmail,
                smtp_password: smtpPassword
            })
        });
        
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || "Failed to save configuration settings");
        }
        
        alert("Configuration changes saved successfully!");
        fetchConfig();
    } catch (err) {
        alert("Error: " + err.message);
    }
}

// Filter Report list in Search
function filterHistoryList() {
    const q = document.getElementById('historySearchInput').value.toLowerCase();
    const cards = document.querySelectorAll('#sidebarReportList .report-card');
    cards.forEach(card => {
        const text = card.querySelector('strong').innerText.toLowerCase();
        if (text.includes(q)) {
            card.classList.remove('hidden');
        } else {
            card.classList.add('hidden');
        }
    });
}

function appendMessage(text, sender) {
    const windowEl = document.getElementById('chatWindow');
    const msgDiv = document.createElement('div');
    msgDiv.className = `chat-message ${sender}`;
    msgDiv.innerText = text;
    windowEl.appendChild(msgDiv);
    windowEl.scrollTop = windowEl.scrollHeight;
}

function togglePasswordVisibility(e) {
    e.preventDefault();
    const passwordInput = document.getElementById('authPassword');
    const icon = document.getElementById('togglePasswordIcon');
    if (passwordInput.type === 'password') {
        passwordInput.type = 'text';
        icon.setAttribute('data-lucide', 'eye-off');
    } else {
        passwordInput.type = 'password';
        icon.setAttribute('data-lucide', 'eye');
    }
    if (window.lucide) {
        window.lucide.createIcons();
    }
}
