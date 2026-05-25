/* ═══════════════════════════════════════════════════════════════
   AI Recruitment System — Testing Dashboard JavaScript
   Handles all API calls, UI updates, and event management
   ═══════════════════════════════════════════════════════════════ */

const API_BASE = window.location.origin + '/api';

// ── App State ────────────────────────────────────────────
let state = {
    jobs: [],
    candidates: [],
    events: [],
};

// ── Initialization ───────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    checkHealth();
    loadOverviewData();
    setupUploadZone();
    setupNavToggle();
    setupStageHeaderLift();

    // Auto-refresh events every 10 seconds
    setInterval(loadEvents, 10000);
});

function setupStageHeaderLift() {
    let ticking = false;

    const updateLift = () => {
        const lift = Math.min(window.scrollY * 0.14, 24);
        document.documentElement.style.setProperty('--stage-lift', `${lift}px`);
        document.body.classList.toggle('page-scrolled', window.scrollY > 8);
        ticking = false;
    };

    const onScroll = () => {
        if (!ticking) {
            window.requestAnimationFrame(updateLift);
            ticking = true;
        }
    };

    updateLift();
    window.addEventListener('scroll', onScroll, { passive: true });
    window.addEventListener('resize', updateLift);
}

function setupNavToggle() {
    const nav = document.getElementById('tab-nav');
    const headerToggle = document.getElementById('nav-toggle');
    const navClose = document.getElementById('nav-close');
    const overlay = document.getElementById('nav-overlay');

    if (!nav || !headerToggle || !navClose || !overlay) return;

    // Mobile specific logic
    const openMobile = () => {
        nav.classList.add('mobile-open');
        overlay.classList.add('visible');
    };

    const closeMobile = () => {
        nav.classList.remove('mobile-open');
        overlay.classList.remove('visible');
    };

    headerToggle.addEventListener('click', () => {
        if (window.innerWidth <= 768) {
            openMobile();
        } else {
            // Optional: Toggle permanent expansion on desktop
            document.body.classList.toggle('sidebar-expanded');
        }
    });

    navClose.addEventListener('click', closeMobile);
    overlay.addEventListener('click', closeMobile);

    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            if (window.innerWidth <= 768) closeMobile();
        });
    });
}

// ── Tab Navigation ───────────────────────────────────────
function switchTab(tabId) {
    // Update buttons
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.tab === tabId);
    });

    // Update content
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.toggle('active', content.id === `tab-${tabId}`);
    });

    // Load data for the tab
    switch (tabId) {
        case 'overview': loadOverviewData(); break;
        case 'stage1': loadJobs(); loadJobsForSelect(); break;
        case 'stage2': loadCandidates(); loadJobsForSelect(); break;
        case 'stage3': loadScreeningData(); break;
        case 'stage4': loadOutreachData(); break;
        case 'stage5': loadPrescreeningData(); break;
        case 'stage6': loadInterviewResults(); break;
        case 'stage8': loadOffers(); break;
        case 'stage9': loadOnboarding(); break;
        case 'stage10': loadAnalyticsDashboard(); break;
    }
}

// ── Health Check ─────────────────────────────────────────
async function checkHealth() {
    const badge = document.getElementById('api-status');
    try {
        const res = await fetch(`${API_BASE}/system/health`);
        if (res.ok) {
            badge.className = 'status-badge online';
            badge.querySelector('span:last-child').textContent = 'System Online';
        }
    } catch {
        badge.className = 'status-badge error';
        badge.querySelector('span:last-child').textContent = 'Offline';
    }
}

// ── Overview Data ────────────────────────────────────────
async function loadOverviewData() {
    await Promise.all([loadJobs(), loadCandidates(), loadEvents()]);
    updateStats();
}

function updateStats() {
    document.getElementById('stat-jobs').textContent = state.jobs.length;
    document.getElementById('stat-candidates').textContent = state.candidates.length;
    document.getElementById('stat-events').textContent = state.events.length;
    // Count unique postings from events
    const postings = state.events.filter(e => e.topic === 'job.posted').length;
    document.getElementById('stat-postings').textContent = postings;
}

// ── Jobs ─────────────────────────────────────────────────
async function loadJobs() {
    try {
        const res = await fetch(`${API_BASE}/intake/jobs`);
        state.jobs = await res.json();
        renderJobs();
        loadJobsForSelect();
    } catch (e) {
        console.error('Failed to load jobs:', e);
    }
}

function renderJobs() {
    const list = document.getElementById('jobs-list');
    if (!state.jobs.length) {
        list.innerHTML = '<div class="empty-state">No jobs created yet. Use the form above to create one.</div>';
        return;
    }
    list.innerHTML = state.jobs.map(j => `
        <div class="item-card">
            <div class="item-card-info">
                <h4>${j.title}</h4>
                <p>${j.department || 'N/A'} • ${j.location || 'N/A'} • ${j.experience_min}-${j.experience_max} yrs</p>
                <div>${(j.skills || []).map(s => `<span class="skill-tag">${s}</span>`).join('')}</div>
            </div>
            <div class="item-card-actions">
                <span class="status-tag ${j.status}">${j.status}</span>
                ${j.description ? `
                    <button class="btn btn-ghost btn-sm" onclick="quickPostJob('${j.id}')">Post</button>
                ` : ''}
            </div>
        </div>
    `).join('');
}

function loadJobsForSelect() {
    const selects = ['post-job-select', 'resume-job-select', 'candidate-job-select'];
    selects.forEach(id => {
        const el = document.getElementById(id);
        if (!el) return;
        el.innerHTML = '<option value="">-- Select a job --</option>' +
            state.jobs.map(j => `<option value="${j.id}">${j.title} (${j.status})</option>`).join('');
    });
}

async function createJob(e) {
    e.preventDefault();
    const btn = document.getElementById('btn-create-job');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> Creating job with AI description...';

    try {
        const skills = document.getElementById('job-skills').value
            .split(',').map(s => s.trim()).filter(Boolean);

        const body = {
            title: document.getElementById('job-title').value,
            department: document.getElementById('job-dept').value,
            location: document.getElementById('job-location').value,
            employment_type: document.getElementById('job-type').value,
            experience_min: parseInt(document.getElementById('job-exp-min').value) || 0,
            experience_max: parseInt(document.getElementById('job-exp-max').value) || 5,
            salary_min: parseFloat(document.getElementById('job-salary-min').value) || 0,
            salary_max: parseFloat(document.getElementById('job-salary-max').value) || 0,
            skills: skills,
        };

        const res = await fetch(`${API_BASE}/intake/jobs`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });

        const data = await res.json();
        if (res.ok) {
            const apiText = data.api_used ? 'with Groq AI' : 'with fallback template';
            showToast(`Job "${body.title}" created ${apiText}!`, 'success');
            document.getElementById('job-form').reset();

            // Show generated description in result panel
            const resultPanel = document.getElementById('jd-result');
            const content = document.getElementById('jd-content');
            if (resultPanel && content && data.description) {
                resultPanel.classList.remove('hidden');
                content.innerHTML = formatMarkdown(data.description);
            }

            await loadJobs();
        } else {
            showToast(data.detail || 'Failed to create job', 'error');
        }
    } catch (e) {
        showToast('Network error: ' + e.message, 'error');
    }

    btn.disabled = false;
    btn.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18">
        <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
    </svg> Create Job with AI Description`;
}

// ── Job Posting ──────────────────────────────────────────
async function postJob(e) {
    e.preventDefault();
    const jobId = document.getElementById('post-job-select').value;
    if (!jobId) { showToast('Please select a job first', 'error'); return; }

    const platforms = Array.from(document.querySelectorAll('input[name="platform"]:checked'))
        .map(el => el.value);
    console.log('Selected platforms:', platforms); // Debug log
    if (!platforms.length) { showToast('Select at least one platform', 'error'); return; }

    await doPostJob(jobId, platforms);
}

async function quickPostJob(jobId) {
    await doPostJob(jobId, ['linkedin', 'indeed']);
}

async function doPostJob(jobId, platforms) {
    console.log('Posting job to platforms:', platforms); // Debug log

    const btn = document.getElementById('btn-post-job');
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner"></span> Posting...';
    }

    try {
        const res = await fetch(`${API_BASE}/intake/post-job`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ job_id: jobId, platforms: platforms }),
        });

        const data = await res.json();
        console.log('Posting response:', data); // Debug log

        if (res.ok) {
            showToast(data.message, 'success');
            renderPostingResults(data.postings || []);
        } else {
            showToast(data.detail || 'Failed to post job', 'error');
        }
    } catch (e) {
        showToast('Network error: ' + e.message, 'error');
    }

    if (btn) {
        btn.disabled = false;
        btn.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18">
            <circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/>
            <line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/>
            <line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/>
        </svg> Post to Selected Platforms`;
    }
}

function renderPostingResults(postings) {
    const panel = document.getElementById('posting-result');
    const content = document.getElementById('posting-content');
    if (!panel || !content) return;

    panel.classList.remove('hidden');
    content.innerHTML = `<div class="posting-cards">${postings.map(p => `
        <div class="posting-card">
            <div class="posting-card-header">
                <span class="platform-icon ${p.platform}">${p.platform === 'linkedin' ? 'in' : p.platform === 'indeed' ? 'I' : p.platform === 'adzuna' ? 'AZ' : 'X'}</span>
                <h4>${p.platform.charAt(0).toUpperCase() + p.platform.slice(1)}</h4>
                <span class="status-tag ${p.status}">${p.status === 'manual_required' ? 'manual' : p.status}</span>
            </div>
            ${p.post_url ? `<p class="posting-detail"><strong>URL:</strong> <a href="${p.post_url}" target="_blank">${p.post_url}</a></p>` : ''}
            ${p.external_id ? `<p class="posting-detail"><strong>Job ID:</strong> <code>${p.external_id}</code></p>` : ''}
            ${p.posted_at ? `<p class="posting-detail"><strong>Posted:</strong> ${new Date(p.posted_at).toLocaleString()}</p>` : ''}
            ${p.expires_at ? `<p class="posting-detail"><strong>Expires:</strong> ${new Date(p.expires_at).toLocaleString()}</p>` : ''}
            ${p.note ? `<p class="posting-detail" style="color:var(--accent-blue)"><strong>Note:</strong> ${p.note}</p>` : ''}
            ${p.error ? `<p class="posting-detail" style="color:var(--accent-red)"><strong>Error:</strong> ${p.error}</p>` : ''}
            ${p.manual_url ? `<p class="posting-detail"><a href="${p.manual_url}" target="_blank">Manual Posting Required →</a></p>` : ''}
            ${p.job_details ? `<div class="posting-detail"><strong>Job Details:</strong><br>
                Title: ${p.job_details.title}<br>
                Location: ${p.job_details.location}<br>
                Experience: ${p.job_details.experience}<br>
                Salary: ${p.job_details.salary}
            </div>` : ''}
            ${p.instructions ? `<div class="posting-detail"><strong>Instructions:</strong><br>${p.instructions.join('<br>')}</div>` : ''}
        </div>
    `).join('')}</div>`;
}

// ── Resume Upload ────────────────────────────────────────
function setupUploadZone() {
    const zone = document.getElementById('upload-zone');
    const input = document.getElementById('resume-file');

    zone.addEventListener('click', () => input.click());

    zone.addEventListener('dragover', (e) => {
        e.preventDefault();
        zone.classList.add('dragover');
    });

    zone.addEventListener('dragleave', () => {
        zone.classList.remove('dragover');
    });

    zone.addEventListener('drop', (e) => {
        e.preventDefault();
        zone.classList.remove('dragover');
        const files = e.dataTransfer.files;
        if (files.length) uploadResume(files[0]);
    });

    input.addEventListener('change', () => {
        if (input.files.length) uploadResume(input.files[0]);
    });
}

async function uploadResume(file) {
    const progressContainer = document.getElementById('upload-progress');
    const progressFill = document.getElementById('progress-fill');
    const statusText = document.getElementById('upload-status');
    const jobSelect = document.getElementById('resume-job-select');

    progressContainer.classList.remove('hidden');
    progressFill.style.width = '10%';
    statusText.textContent = `Uploading ${file.name}...`;

    try {
        const formData = new FormData();
        formData.append('file', file);

        // Add job_id if selected
        if (jobSelect && jobSelect.value) {
            formData.append('job_id', jobSelect.value);
        }

        progressFill.style.width = '40%';

        const res = await fetch(`${API_BASE}/sourcing/upload-resume`, {
            method: 'POST',
            body: formData,
        });

        progressFill.style.width = '60%';
        statusText.textContent = 'Processing with LlamaIndex + Groq AI...';

        const data = await res.json();
        if (res.ok) {
            const jobText = data.job_id ? ` (linked to job)` : '';
            showToast(`Resume uploaded: ${file.name}${jobText}`, 'success');
            progressFill.style.width = '80%';
            statusText.textContent = 'Auto-parsing with LlamaIndex...';

            // Wait a moment for auto-parsing to complete
            setTimeout(async () => {
                progressFill.style.width = '100%';
                statusText.textContent = '✅ Upload complete - Auto-parsing in progress';
                await loadCandidates();
            }, 2000);
        } else {
            showToast(data.detail || 'Upload failed', 'error');
            statusText.textContent = '❌ Upload failed';
        }
    } catch (e) {
        showToast('Network error: ' + e.message, 'error');
        statusText.textContent = '❌ Network error';
    }

    // Reset input
    document.getElementById('resume-file').value = '';
}

function renderParsedResume(data) {
    const panel = document.getElementById('parse-result');
    const content = document.getElementById('parse-content');
    if (!panel || !content) return;

    panel.classList.remove('hidden');

    const fields = [
        { label: 'Name', value: data.name },
        { label: 'Email', value: data.email },
        { label: 'Phone', value: data.phone },
        { label: 'Location', value: data.location },
        { label: 'Current Role', value: data.current_role },
        { label: 'Experience', value: data.experience_years ? `${data.experience_years} years` : null },
        { label: 'Parser Used', value: data._parser },
    ];

    content.innerHTML = `
        <div class="parsed-grid">
            ${fields.filter(f => f.value).map(f => `
                <div class="parsed-field">
                    <div class="parsed-field-label">${f.label}</div>
                    <div class="parsed-field-value">${f.value}</div>
                </div>
            `).join('')}
        </div>
        ${data.skills && data.skills.length ? `
            <div class="parsed-field" style="margin-top:12px">
                <div class="parsed-field-label">Skills</div>
                <div>${data.skills.map(s => `<span class="skill-tag">${s}</span>`).join('')}</div>
            </div>
        ` : ''}
        ${data.education && data.education.length ? `
            <div class="parsed-field" style="margin-top:12px">
                <div class="parsed-field-label">Education</div>
                <div class="parsed-field-value">${data.education.map(e =>
        typeof e === 'string' ? e : `${e.degree || ''} — ${e.institution || ''} ${e.year || ''}`
    ).join('<br>')}</div>
            </div>
        ` : ''}
        ${data.work_history && data.work_history.length ? `
            <div class="parsed-field" style="margin-top:12px">
                <div class="parsed-field-label">Work History</div>
                <div class="parsed-field-value">${data.work_history.map(w =>
        `<strong>${w.role || w.title || ''}</strong> at ${w.company || ''} (${w.duration || ''})`
    ).join('<br>')}</div>
            </div>
        ` : ''}
        ${data.summary ? `
            <div class="parsed-field" style="margin-top:12px">
                <div class="parsed-field-label">Summary</div>
                <div class="parsed-field-value">${data.summary}</div>
            </div>
        ` : ''}
    `;
}

// ── Candidates ───────────────────────────────────────────
async function loadCandidates() {
    try {
        const res = await fetch(`${API_BASE}/sourcing/candidates`);
        state.candidates = await res.json();
        renderCandidates();
    } catch (e) {
        console.error('Failed to load candidates:', e);
    }
}

function renderCandidates() {
    const list = document.getElementById('candidates-list');
    if (!list) return;
    if (!state.candidates.length) {
        list.innerHTML = '<div class="empty-state">No candidates yet. Upload a resume or enter candidate details.</div>';
        return;
    }
    list.innerHTML = state.candidates.map(c => `
        <div class="item-card">
            <div class="item-card-info">
                <h4>${c.name}</h4>
                <p>${c.current_role || 'N/A'} • ${c.location || 'N/A'} • ${c.experience_years || 0} yrs • Source: ${c.source}</p>
                <div>${(c.skills || []).slice(0, 8).map(s => `<span class="skill-tag">${s}</span>`).join('')}</div>
            </div>
            <div class="item-card-actions">
                <span class="status-tag ${c.status}">${c.status}</span>
                ${c.status === 'uploaded' || c.status === 'new' ?
            `<button class="btn btn-ghost btn-sm" onclick="parseCandidate('${c.id}')">Parse</button>` : ''}
            </div>
        </div>
    `).join('');
}

async function parseCandidate(candidateId) {
    showToast('Parsing resume with LlamaIndex...', 'info');
    try {
        const res = await fetch(`${API_BASE}/sourcing/parse-resume`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ candidate_id: candidateId }),
        });
        const data = await res.json();
        if (res.ok) {
            showToast(`Parsed with ${data.parser_used}!`, 'success');
            await loadCandidates();
        } else {
            showToast(data.detail || 'Parsing failed', 'error');
        }
    } catch (e) {
        showToast('Network error: ' + e.message, 'error');
    }
}

// ── Candidate Details Form ───────────────────────────────
async function addCandidateForm(e) {
    e.preventDefault();
    const btn = document.getElementById('btn-add-candidate');
    const resultPanel = document.getElementById('candidate-form-result');
    const resultContent = document.getElementById('candidate-form-content');

    const jobId = document.getElementById('candidate-job-select').value;
    if (!jobId) {
        showToast('Please select a job to apply for', 'error');
        return;
    }

    const skills = document.getElementById('candidate-skills').value
        .split(',').map(s => s.trim()).filter(Boolean);
    if (!skills.length) {
        showToast('Please enter at least one skill', 'error');
        return;
    }

    const education = document.getElementById('candidate-education').value || null;

    const body = {
        job_id: jobId,
        name: document.getElementById('candidate-name').value.trim(),
        email: document.getElementById('candidate-email').value.trim() || null,
        phone: document.getElementById('candidate-phone').value.trim() || null,
        location: document.getElementById('candidate-location').value.trim() || null,
        current_role: document.getElementById('candidate-role').value.trim() || null,
        experience_years: parseFloat(document.getElementById('candidate-experience').value) || 0,
        skills,
        education,
        source_profile_url: document.getElementById('candidate-linkedin').value.trim() || null,
    };

    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> Adding candidate...';

    try {
        const res = await fetch(`${API_BASE}/sourcing/add-candidate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
        const data = await res.json();

        if (res.ok) {
            showToast(data.message || 'Candidate added — queued for screening', 'success');
            resultPanel.classList.remove('hidden');
            resultContent.innerHTML = `
                <div class="parsed-grid">
                    <div class="parsed-field"><div class="parsed-field-label">Name</div><div class="parsed-field-value">${data.name}</div></div>
                    <div class="parsed-field"><div class="parsed-field-label">Candidate ID</div><div class="parsed-field-value">${data.candidate_id}</div></div>
                    <div class="parsed-field"><div class="parsed-field-label">Job ID</div><div class="parsed-field-value">${data.job_id}</div></div>
                    <div class="parsed-field"><div class="parsed-field-label">Status</div><div class="parsed-field-value"><span class="status-tag ${data.status}">${data.status}</span></div></div>
                </div>
                <p style="margin-top:12px;color:var(--text-secondary)">Candidate data flows to screening automatically.</p>
            `;
            document.getElementById('candidate-form').reset();
            document.getElementById('candidate-experience').value = '0';
            await loadCandidates();
            updateStats();
        } else {
            const detail = Array.isArray(data.detail)
                ? data.detail.map(d => d.msg || d).join(', ')
                : (data.detail || 'Failed to add candidate');
            showToast(detail, 'error');
        }
    } catch (err) {
        showToast('Network error: ' + err.message, 'error');
    }

    btn.disabled = false;
    btn.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18">
        <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
    </svg> Add Candidate`;
}

// ── Events / Activity Log ────────────────────────────────
async function loadEvents() {
    try {
        const res = await fetch(`${API_BASE}/system/events`);
        const data = await res.json();
        state.events = data.events || [];
        renderEvents();
        updateStats();
    } catch (e) {
        console.error('Failed to load events:', e);
    }
}

function renderEvents() {
    const list = document.getElementById('events-list');
    if (!list) return;
    if (!state.events.length) {
        list.innerHTML = '<div class="empty-state">No events yet. Perform actions to see the event log.</div>';
        return;
    }
    list.innerHTML = state.events.map(e => `
        <div class="event-item">
            <span class="event-type">${e.topic}</span>
            <span class="event-agent">${e.agent}</span>
            <span class="event-payload">${JSON.stringify(e.payload || {}).substring(0, 120)}</span>
            <span class="event-time">${e.timestamp ? new Date(e.timestamp).toLocaleTimeString() : ''}</span>
        </div>
    `).join('');
}

// ── Utility Functions ────────────────────────────────────

function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    container.appendChild(toast);

    setTimeout(() => {
        toast.classList.add('removing');
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

function formatMarkdown(text) {
    if (!text) return '';
    return text
        .replace(/^### (.*$)/gm, '<h3>$1</h3>')
        .replace(/^## (.*$)/gm, '<h2>$1</h2>')
        .replace(/^# (.*$)/gm, '<h1>$1</h1>')
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.*?)\*/g, '<em>$1</em>')
        .replace(/^- (.*$)/gm, '<li>$1</li>')
        .replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>')
        .replace(/\n{2,}/g, '<br><br>')
        .replace(/\n/g, '<br>');
}

// ── Stage 3: Screening Functions ─────────────────────────

let screeningState = {
    stats: null,
    candidates: [],
    jobs: []
};

async function loadScreeningData() {
    await Promise.all([
        loadScreeningStats(),
        loadScreeningCandidates(),
        loadScreeningJobs()
    ]);
    updateScreeningUI();
}

async function loadScreeningStats(jobId = null) {
    try {
        const url = jobId ? `${API_BASE}/screening/stats?job_id=${jobId}` : `${API_BASE}/screening/stats`;
        const res = await fetch(url);
        screeningState.stats = await res.json();
    } catch (e) {
        console.error('Failed to load screening stats:', e);
        screeningState.stats = {
            total_candidates: 0,
            screened: 0,
            shortlisted: 0,
            rejected: 0,
            duplicates: 0,
            avg_score: 0
        };
    }
}

async function loadScreeningCandidates(jobId = null, status = null) {
    try {
        let url = `${API_BASE}/screening/candidates?limit=200`;
        if (jobId) url += `&job_id=${jobId}`;
        if (status) url += `&status=${status}`;

        const res = await fetch(url);
        screeningState.candidates = await res.json();
    } catch (e) {
        console.error('Failed to load screening candidates:', e);
        screeningState.candidates = [];
    }
}

async function loadScreeningJobs() {
    try {
        const res = await fetch(`${API_BASE}/screening/jobs`);
        screeningState.jobs = await res.json();

        // Update job select dropdown
        const select = document.getElementById('screening-job-select');
        if (select) {
            select.innerHTML = '<option value="">-- All Jobs --</option>' +
                screeningState.jobs.map(j =>
                    `<option value="${j.id}">${j.title} (${j.candidate_count} candidates)</option>`
                ).join('');
        }
    } catch (e) {
        console.error('Failed to load screening jobs:', e);
        screeningState.jobs = [];
    }
}

function updateScreeningUI() {
    // Update stats cards
    if (screeningState.stats) {
        document.getElementById('stat-total-candidates').textContent = screeningState.stats.total_candidates;
        document.getElementById('stat-screened').textContent = screeningState.stats.screened;
        document.getElementById('stat-shortlisted').textContent = screeningState.stats.shortlisted;
        document.getElementById('stat-rejected').textContent = screeningState.stats.rejected;
        document.getElementById('stat-duplicates').textContent = screeningState.stats.duplicates;
        document.getElementById('stat-avg-score').textContent = screeningState.stats.avg_score;
    }

    // Show auto-detection banner if candidates exist
    const banner = document.getElementById('auto-detection-banner');
    const bannerText = document.getElementById('auto-detection-text');
    if (screeningState.stats && screeningState.stats.total_candidates > 0) {
        banner.classList.remove('hidden');
        bannerText.textContent = `${screeningState.stats.total_candidates} candidates detected from sourcing module and loaded automatically`;
    } else {
        banner.classList.add('hidden');
    }

    // Update flow steps
    updateScreeningFlow();

    // Render results table
    renderScreeningResults();
}

function updateScreeningFlow() {
    const steps = ['flow-duplicate', 'flow-scoring', 'flow-ranking', 'flow-shortlist'];
    const stats = screeningState.stats;

    if (!stats) return;

    // Mark steps as completed based on screening progress
    if (stats.screened > 0) {
        steps.forEach(stepId => {
            const step = document.getElementById(stepId);
            if (step) step.classList.add('completed');
        });
    }
}

function renderScreeningResults() {
    const container = document.getElementById('screening-results');
    if (!container) return;

    if (!screeningState.candidates.length) {
        container.innerHTML = '<div class="empty-state">No screening results yet. Run screening to see results.</div>';
        return;
    }

    // Sort candidates by score (highest first)
    const sortedCandidates = [...screeningState.candidates].sort((a, b) => {
        if (a.score === null && b.score === null) return 0;
        if (a.score === null) return 1;
        if (b.score === null) return -1;
        return b.score - a.score;
    });

    const tableHTML = `
        <table class="results-table">
            <thead>
                <tr>
                    <th>Candidate</th>
                    <th>Skills</th>
                    <th>Experience</th>
                    <th>Score</th>
                    <th>Match %</th>
                    <th>Status</th>
                    <th>Source</th>
                    <th>Actions</th>
                </tr>
            </thead>
            <tbody>
                ${sortedCandidates.map(c => `
                    <tr>
                        <td>
                            <div class="candidate-name">${c.name}</div>
                            <div class="candidate-role">${c.current_role || 'N/A'}</div>
                        </td>
                        <td>
                            <div class="candidate-skills">
                                ${(c.skills || []).slice(0, 3).map(s => `<span class="skill-tag">${s}</span>`).join('')}
                                ${c.skills && c.skills.length > 3 ? `<span class="skill-tag">+${c.skills.length - 3}</span>` : ''}
                            </div>
                        </td>
                        <td>${c.experience_years || 0} yrs</td>
                        <td class="score-cell">
                            ${c.score !== null ? `
                                <div class="score-value ${getScoreClass(c.score)}">${c.score}</div>
                            ` : '<span style="color:var(--text-muted)">-</span>'}
                        </td>
                        <td class="score-cell">
                            ${c.score !== null ? `
                                <div class="match-percentage">${c.score}%</div>
                            ` : '<span style="color:var(--text-muted)">-</span>'}
                        </td>
                        <td>
                            <span class="status-tag ${c.status}">${c.status}</span>
                            ${c.is_duplicate ? '<span class="status-tag duplicate">Duplicate</span>' : ''}
                        </td>
                        <td>${c.source}</td>
                        <td>
                            <div class="candidate-actions">
                                ${c.score === null ? `
                                    <button class="btn btn-ghost btn-xs" onclick="scoreSingleCandidate('${c.id}')">Score</button>
                                ` : ''}
                                <button class="btn btn-ghost btn-xs" onclick="viewCandidate('${c.id}')">View</button>
                                ${c.score !== null ? `
                                    <button class="btn btn-ghost btn-xs" onclick="resetCandidateScreening('${c.id}')">Reset</button>
                                ` : ''}
                            </div>
                        </td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;

    container.innerHTML = tableHTML;
}

function getScoreClass(score) {
    if (score >= 70) return 'score-high';
    if (score >= 50) return 'score-medium';
    return 'score-low';
}

async function runScreening(forceRescreen = false) {
    const btn = document.getElementById('btn-run-screening');
    const jobSelect = document.getElementById('screening-job-select');

    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner"></span> Running screening...';
    }

    try {
        const body = {
            force_rescreen: forceRescreen
        };

        if (jobSelect && jobSelect.value) {
            body.job_id = jobSelect.value;
        }

        const res = await fetch(`${API_BASE}/screening/run`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        });

        const data = await res.json();
        if (res.ok) {
            showToast(data.message, 'success');
            await loadScreeningData();
        } else {
            showToast(data.detail || 'Screening failed', 'error');
        }
    } catch (e) {
        showToast('Network error: ' + e.message, 'error');
    }

    if (btn) {
        btn.disabled = false;
        btn.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18">
            <polygon points="5 3 19 12 5 21 5 3"/>
        </svg> Run Screening`;
    }
}

async function scoreSingleCandidate(candidateId) {
    try {
        const res = await fetch(`${API_BASE}/screening/score/${candidateId}`, {
            method: 'POST'
        });

        const data = await res.json();
        if (res.ok) {
            showToast(`Candidate scored: ${data.total_score}`, 'success');
            await loadScreeningData();
        } else {
            showToast(data.detail || 'Scoring failed', 'error');
        }
    } catch (e) {
        showToast('Network error: ' + e.message, 'error');
    }
}

async function resetCandidateScreening(candidateId) {
    if (!confirm('Reset screening results for this candidate?')) return;

    try {
        const res = await fetch(`${API_BASE}/screening/reset/${candidateId}`, {
            method: 'DELETE'
        });

        const data = await res.json();
        if (res.ok) {
            showToast(data.message, 'success');
            await loadScreeningData();
        } else {
            showToast(data.detail || 'Reset failed', 'error');
        }
    } catch (e) {
        showToast('Network error: ' + e.message, 'error');
    }
}

function viewCandidate(candidateId) {
    const candidate = screeningState.candidates.find(c => c.id === candidateId);
    if (!candidate) return;

    const details = `
Name: ${candidate.name}
Email: ${candidate.email || 'N/A'}
Phone: ${candidate.phone || 'N/A'}
Location: ${candidate.location || 'N/A'}
Experience: ${candidate.experience_years || 0} years
Skills: ${(candidate.skills || []).join(', ')}
Status: ${candidate.status}
Score: ${candidate.score || 'Not scored'}
${candidate.rejection_reason ? `Rejection Reason: ${candidate.rejection_reason}` : ''}
${candidate.is_duplicate ? `Duplicate of: ${candidate.merged_into}` : ''}
    `.trim();

    alert(details);
}

async function filterCandidates() {
    const statusFilter = document.getElementById('status-filter');
    const jobSelect = document.getElementById('screening-job-select');

    const status = statusFilter ? statusFilter.value : null;
    const jobId = jobSelect ? jobSelect.value : null;

    await loadScreeningCandidates(jobId, status);
    renderScreeningResults();
}

function exportShortlist() {
    const shortlisted = screeningState.candidates.filter(c => c.status === 'shortlisted');

    if (!shortlisted.length) {
        showToast('No shortlisted candidates to export', 'error');
        return;
    }

    const csv = [
        'Name,Email,Phone,Current Role,Experience,Score,Skills',
        ...shortlisted.map(c => [
            c.name,
            c.email || '',
            c.phone || '',
            c.current_role || '',
            c.experience_years || 0,
            c.score || '',
            (c.skills || []).join('; ')
        ].map(field => `"${field}"`).join(','))
    ].join('\n');

    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `shortlisted-candidates-${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
    URL.revokeObjectURL(url);

    showToast(`Exported ${shortlisted.length} shortlisted candidates`, 'success');
}

// ── Stage 4: Outreach Functions ─────────────────────────

let outreachState = {
    stats: null,
    candidates: []
};

async function loadOutreachData() {
    await Promise.all([
        loadOutreachStats(),
        loadOutreachCandidates()
    ]);
    updateOutreachUI();
}

async function loadOutreachStats() {
    try {
        const res = await fetch(`${API_BASE}/outreach/stats`);
        outreachState.stats = await res.json();
    } catch (e) {
        console.error('Failed to load outreach stats:', e);
        outreachState.stats = {
            total_sent: 0,
            opened: 0,
            clicked: 0,
            replied: 0,
            unresponsive: 0
        };
    }
}

async function loadOutreachCandidates() {
    try {
        const res = await fetch(`${API_BASE}/outreach/candidates?limit=100`);
        outreachState.candidates = await res.json();
    } catch (e) {
        console.error('Failed to load outreach candidates:', e);
        outreachState.candidates = [];
    }
}

function updateOutreachUI() {
    if (outreachState.stats) {
        document.getElementById('outreach-sent').textContent = outreachState.stats.total_sent;
        document.getElementById('outreach-opened').textContent = outreachState.stats.opened;
        document.getElementById('outreach-replied').textContent = outreachState.stats.replied;
        document.getElementById('outreach-unresponsive').textContent = outreachState.stats.unresponsive;
    }

    renderOutreachCandidates();
}

function renderOutreachCandidates() {
    const tbody = document.getElementById('outreach-table-body');
    if (!tbody) return;

    if (!outreachState.candidates || !outreachState.candidates.length) {
        tbody.innerHTML = '<tr><td colspan="7" class="empty-state">No outreach emails sent yet. Shortlist candidates in screening to trigger outreach.</td></tr>';
        return;
    }

    tbody.innerHTML = outreachState.candidates.map(c => `
        <tr>
            <td><strong>${c.name || 'Unknown'}</strong></td>
            <td>${c.email || 'N/A'}</td>
            <td>${c.job_title || 'N/A'}</td>
            <td><span class="score-badge">${c.score || 0}</span></td>
            <td>${c.sent_at ? new Date(c.sent_at).toLocaleString() : 'N/A'}</td>
            <td>
                <span class="status-tag ${c.status || 'pending'}">${c.status || 'PENDING'}</span>
            </td>
            <td>
                <button class="btn-icon" onclick="viewCandidateDetails('${c.id}')" title="View Details">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
                        <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                        <circle cx="12" cy="12" r="3"/>
                    </svg>
                </button>
            </td>
        </tr>
    `).join('');
}

// ── Stage 5: Prescreening Functions ─────────────────────

let prescreeningState = {
    stats: null,
    sessions: []
};

async function loadPrescreeningData() {
    await Promise.all([
        loadPrescreeningStats(),
        loadPrescreeningSessions()
    ]);
    updatePrescreeningUI();
}

async function loadPrescreeningStats() {
    try {
        const res = await fetch(`${API_BASE}/prescreening/stats`);
        prescreeningState.stats = await res.json();
    } catch (e) {
        console.error('Failed to load prescreening stats:', e);
        prescreeningState.stats = {
            total_sessions: 0,
            completed: 0,
            passed: 0,
            failed: 0,
            in_progress: 0
        };
    }
}

async function loadPrescreeningSessions() {
    try {
        const res = await fetch(`${API_BASE}/prescreening/sessions?limit=100`);
        if (res.ok) {
            prescreeningState.sessions = await res.json();
        } else {
            console.warn('Prescreening sessions endpoint returned:', res.status);
            prescreeningState.sessions = [];
        }
    } catch (e) {
        console.error('Failed to load prescreening sessions:', e);
        prescreeningState.sessions = [];
    }
}

function updatePrescreeningUI() {
    if (prescreeningState.stats) {
        document.getElementById('prescreening-total').textContent = prescreeningState.stats.total_sessions;
        document.getElementById('prescreening-completed').textContent = prescreeningState.stats.completed;
        document.getElementById('prescreening-passed').textContent = prescreeningState.stats.passed;
        document.getElementById('bgv-cleared').textContent = prescreeningState.stats.bgv_cleared || 0;
    }

    renderPrescreeningSessions();
}

function renderPrescreeningSessions() {
    const container = document.getElementById('prescreening-candidates');
    if (!container) return;

    if (!prescreeningState.sessions.length) {
        container.innerHTML = '<div class="empty-state">No prescreening sessions yet. Candidates who respond to outreach emails will be invited to prescreening.</div>';
        return;
    }

    container.innerHTML = prescreeningState.sessions.map(s => `
        <div class="item-card">
            <div class="item-card-info">
                <h4>${s.candidate_name}</h4>
                <p>${s.job_title || 'N/A'} • ${s.total_questions || 0} questions</p>
                ${s.verdict ? `<p style="margin-top:4px;color:var(--text-secondary)">Verdict: <strong>${s.verdict}</strong> (Score: ${s.avg_score || 0})</p>` : ''}
            </div>
            <div class="item-card-actions">
                <span class="status-tag ${s.status === 'COMPLETED' ? 'active' : s.status === 'IN_PROGRESS' ? 'draft' : 'closed'}">${s.status}</span>
                ${s.status === 'COMPLETED' ? `<small style="color:var(--text-muted)">Completed: ${new Date(s.completed_at).toLocaleDateString()}</small>` : ''}
            </div>
        </div>
    `).join('');
}


// ── Stage 4: Outreach View Toggle ───────────────────────
function toggleOutreachView(view) {
    const adminView = document.getElementById('outreach-admin-view');
    const candidateView = document.getElementById('outreach-candidate-view');
    const listPanel = document.getElementById('outreach-list-panel');
    const adminBtn = document.getElementById('btn-outreach-admin');
    const candidateBtn = document.getElementById('btn-outreach-candidate');

    if (view === 'admin') {
        adminView.style.display = 'block';
        candidateView.style.display = 'none';
        listPanel.style.display = 'block';
        adminBtn.classList.remove('btn-primary');
        adminBtn.classList.add('btn-secondary');
        candidateBtn.classList.remove('btn-secondary');
        candidateBtn.classList.add('btn-primary');
    } else {
        adminView.style.display = 'none';
        candidateView.style.display = 'block';
        listPanel.style.display = 'none';
        adminBtn.classList.remove('btn-secondary');
        adminBtn.classList.add('btn-primary');
        candidateBtn.classList.remove('btn-primary');
        candidateBtn.classList.add('btn-secondary');

        // Load candidates for demo
        loadOutreachCandidatesForDemo();
    }
}

async function loadOutreachCandidatesForDemo() {
    const select = document.getElementById('demo-outreach-select');
    if (!select) return;

    try {
        const res = await fetch(`${API_BASE}/outreach/candidates?limit=50`);
        const candidates = await res.json();

        select.innerHTML = '<option value="">-- Choose a candidate --</option>' +
            candidates.map(c => `<option value="${c.id}">${c.name} - ${c.job_title || 'N/A'}</option>`).join('');
    } catch (e) {
        console.error('Failed to load candidates for demo:', e);
    }
}

function loadOutreachDemo() {
    const select = document.getElementById('demo-outreach-select');
    const candidateId = select.value;

    if (!candidateId) {
        document.getElementById('outreach-demo-container').style.display = 'none';
        return;
    }

    // Find candidate data
    const candidate = outreachState.candidates.find(c => c.id === candidateId);
    if (!candidate) return;

    // Show demo container
    document.getElementById('outreach-demo-container').style.display = 'block';

    // Populate email preview
    const firstName = candidate.name ? candidate.name.split(' ')[0] : 'Candidate';
    document.getElementById('demo-from-email').textContent = 'recruitment@company.com';
    document.getElementById('demo-to-email').textContent = candidate.email || 'candidate@example.com';
    document.getElementById('demo-email-subject').textContent = candidate.job_title || 'Position';
    document.getElementById('demo-first-name').textContent = firstName;
    document.getElementById('demo-job-position').textContent = candidate.job_title || 'Position';
    document.getElementById('demo-company-name').textContent = 'Our Company';
    document.getElementById('demo-company-footer').textContent = 'Our Company';

    // Generate demo chatbot link
    const demoLink = `/candidate/prescreening?token=demo-${candidateId}`;
    document.getElementById('demo-chatbot-link').href = demoLink;
    document.getElementById('demo-chatbot-link').textContent = 'Start Prescreening Interview →';
}

// ── Stage 5: Prescreening View Toggle ───────────────────
function togglePrescreeningView(view) {
    console.log('togglePrescreeningView called with view:', view);

    const adminView = document.getElementById('prescreening-admin-view');
    const candidateView = document.getElementById('prescreening-candidate-view');
    const listPanel = document.getElementById('prescreening-list-panel');
    const adminBtn = document.getElementById('btn-admin-view');
    const candidateBtn = document.getElementById('btn-candidate-view');

    console.log('Elements found:', {
        adminView: !!adminView,
        candidateView: !!candidateView,
        listPanel: !!listPanel,
        adminBtn: !!adminBtn,
        candidateBtn: !!candidateBtn
    });

    if (view === 'admin') {
        adminView.style.display = 'block';
        candidateView.style.display = 'none';
        listPanel.style.display = 'block';
        adminBtn.classList.remove('btn-primary');
        adminBtn.classList.add('btn-secondary');
        candidateBtn.classList.remove('btn-secondary');
        candidateBtn.classList.add('btn-primary');
    } else {
        console.log('Switching to candidate view...');
        adminView.style.display = 'none';
        candidateView.style.display = 'block';
        listPanel.style.display = 'none';
        adminBtn.classList.remove('btn-secondary');
        adminBtn.classList.add('btn-primary');
        candidateBtn.classList.remove('btn-primary');
        candidateBtn.classList.add('btn-secondary');

        // Load questions immediately
        console.log('About to load questions...');
        loadPrescreeningQuestions();
    }
}

function loadPrescreeningQuestions() {
    console.log('Loading prescreening questions...');

    // Fixed prescreening questions
    const questions = [
        "What motivated you to apply for this position at our company?",
        "Describe your most relevant work experience for this role.",
        "What are your key technical skills and how have you applied them?",
        "How do you handle tight deadlines and pressure in a work environment?",
        "What are your salary expectations for this position?",
        "When would you be available to start if selected?"
    ];

    // Render questions
    const container = document.getElementById('demo-questions-container');
    console.log('Container found:', container);

    if (!container) {
        console.error('demo-questions-container not found!');
        return;
    }

    container.innerHTML = questions.map((q, i) => `
        <div style="margin-bottom: 24px; padding: 20px; background: rgba(255,255,255,0.05); border-radius: 8px; border-left: 4px solid #3b82f6;">
            <div style="color: #94a3b8; font-size: 14px; margin-bottom: 8px;">Question ${i + 1} of ${questions.length}</div>
            <div style="font-size: 18px; font-weight: 600; margin-bottom: 16px; line-height: 1.4;">${q}</div>
            <textarea 
                style="width: 100%; min-height: 120px; padding: 12px; background: rgba(0,0,0,0.3); border: 1px solid rgba(255,255,255,0.1); border-radius: 6px; color: white; font-family: inherit; resize: vertical;"
                placeholder="Type your answer here (minimum 20 characters)..."
            ></textarea>
        </div>
    `).join('');

    console.log('Questions rendered successfully!');
}

async function loadPrescreeningCandidatesForDemo() {
    const select = document.getElementById('demo-candidate-select');
    if (!select) return;

    try {
        // Load candidates from outreach stage
        const res = await fetch(`${API_BASE}/outreach/candidates?limit=50`);
        const candidates = await res.json();

        select.innerHTML = '<option value="">-- Choose a candidate --</option>' +
            candidates.map(c => `<option value="${c.id}">${c.name} - ${c.job_title || 'N/A'}</option>`).join('');
    } catch (e) {
        console.error('Failed to load candidates for demo:', e);
    }
}

async function loadCandidateDemo() {
    const select = document.getElementById('demo-candidate-select');
    const candidateId = select.value;

    if (!candidateId) {
        document.getElementById('candidate-demo-container').style.display = 'none';
        return;
    }

    // Find candidate data
    const candidate = outreachState.candidates.find(c => c.id === candidateId);
    if (!candidate) return;

    // Show demo container
    document.getElementById('candidate-demo-container').style.display = 'block';

    // Populate candidate info
    const firstName = candidate.name ? candidate.name.split(' ')[0] : 'Candidate';
    document.getElementById('demo-job-title').textContent = `Prescreening for ${candidate.job_title || 'Position'}`;
    document.getElementById('demo-candidate-name').textContent = candidate.name || 'Unknown';
    document.getElementById('demo-position').textContent = candidate.job_title || 'N/A';
    document.getElementById('demo-status').textContent = 'DEMO MODE';
    document.getElementById('demo-status').className = 'status-tag active';

    // Load fixed questions
    const questions = [
        "What motivated you to apply for this position at our company?",
        "Describe your most relevant work experience for this role.",
        "What are your key technical skills and how have you applied them?",
        "How do you handle tight deadlines and pressure in a work environment?",
        "What are your salary expectations for this position?",
        "When would you be available to start if selected?"
    ];

    // Render questions
    const container = document.getElementById('demo-questions-container');
    container.innerHTML = questions.map((q, i) => `
        <div style="margin-bottom: 24px; padding: 20px; background: rgba(255,255,255,0.05); border-radius: 8px; border-left: 4px solid #3b82f6;">
            <div style="color: #94a3b8; font-size: 14px; margin-bottom: 8px;">Question ${i + 1} of ${questions.length}</div>
            <div style="font-size: 18px; font-weight: 600; margin-bottom: 16px;">${q}</div>
            <textarea 
                style="width: 100%; min-height: 100px; padding: 12px; background: rgba(0,0,0,0.3); border: 1px solid rgba(255,255,255,0.1); border-radius: 6px; color: white; font-family: inherit; resize: vertical;"
                placeholder="Candidate would type their answer here..."
                disabled
            ></textarea>
            <div style="margin-top: 8px; color: #10b981; font-size: 14px;">✓ Demo answer (not submitted)</div>
        </div>
    `).join('');
}

// Update renderPrescreeningSessions to use table format
function renderPrescreeningSessions() {
    const tbody = document.getElementById('prescreening-table-body');
    if (!tbody) return;

    if (!prescreeningState.sessions || !prescreeningState.sessions.length) {
        tbody.innerHTML = '<tr><td colspan="9" class="empty-state">No prescreening sessions yet. Candidates who respond to outreach emails will be invited to prescreening.</td></tr>';
        return;
    }

    tbody.innerHTML = prescreeningState.sessions.map(s => `
        <tr>
            <td><strong>${s.candidate_name || 'Unknown'}</strong></td>
            <td>${s.candidate_email || 'N/A'}</td>
            <td>${s.job_title || 'N/A'}</td>
            <td><span class="status-tag ${s.status === 'COMPLETED' ? 'active' : s.status === 'IN_PROGRESS' ? 'draft' : 'pending'}">${s.status || 'PENDING'}</span></td>
            <td>${s.answered_questions || 0} / ${s.total_questions || 6}</td>
            <td>${s.avg_score ? `<span class="score-badge">${s.avg_score.toFixed(1)}</span>` : 'N/A'}</td>
            <td>${s.verdict ? `<span class="status-tag ${s.verdict === 'PASS' ? 'active' : s.verdict === 'FAIL' ? 'closed' : 'draft'}">${s.verdict}</span>` : 'N/A'}</td>
            <td>${s.created_at ? new Date(s.created_at).toLocaleString() : 'N/A'}</td>
            <td>
                <button class="btn-icon" onclick="viewSessionDetails('${s.session_id}')" title="View Details">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
                        <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                        <circle cx="12" cy="12" r="3"/>
                    </svg>
                </button>
            </td>
        </tr>
    `).join('');
}

function viewSessionDetails(sessionId) {
    showToast('Session details view coming soon!', 'info');
}

function viewCandidateDetails(candidateId) {
    showToast('Candidate details view coming soon!', 'info');
}

// ── Enhanced Stage 4: Outreach Functions ─────────────────────────

// Enhanced outreach data loading with better stats
async function loadOutreachData() {
    await Promise.all([
        loadOutreachStats(),
        loadOutreachCandidates(),
        loadOutreachJobs()
    ]);
    updateOutreachUI();
}

async function loadOutreachJobs() {
    try {
        const res = await fetch(`${API_BASE}/outreach/jobs`);
        const jobs = await res.json();

        // Update job filter dropdown
        const select = document.getElementById('outreach-job-filter');
        if (select) {
            select.innerHTML = '<option value="">-- All Jobs --</option>' +
                jobs.map(j =>
                    `<option value="${j.id}">${j.title} (${j.outreach_sent_count} sent)</option>`
                ).join('');
        }
    } catch (e) {
        console.error('Failed to load outreach jobs:', e);
    }
}

function updateOutreachUI() {
    renderOutreachCandidates();
}

function renderOutreachCandidates() {
    const tbody = document.getElementById('outreach-table-body');
    if (!tbody) return;

    if (!outreachState.candidates || !outreachState.candidates.length) {
        tbody.innerHTML = '<tr><td colspan="4" class="empty-state">No outreach candidates available. Shortlist candidates in screening to see them here.</td></tr>';
        return;
    }

    tbody.innerHTML = outreachState.candidates.map(c => `
        <tr>
            <td><strong>${c.name || 'Unknown'}</strong></td>
            <td>${c.email || 'N/A'}</td>
            <td>${c.job_title || 'N/A'}</td>
            <td>
                <button class="btn btn-primary btn-sm" onclick="sendIndividualOutreach('${c.id}')">
                    Send Mail
                </button>
            </td>
        </tr>
    `).join('');
}

async function filterOutreachCandidates() {
    const jobFilter = document.getElementById('outreach-job-filter');
    const selectedJobId = jobFilter ? jobFilter.value : '';
    const filteredCandidates = (outreachState.candidates || []).filter(c => !selectedJobId || c.job_id === selectedJobId);

    const tbody = document.getElementById('outreach-table-body');
    if (!tbody) return;

    if (!filteredCandidates.length) {
        tbody.innerHTML = '<tr><td colspan="4" class="empty-state">No candidates found for the selected job.</td></tr>';
        return;
    }

    tbody.innerHTML = filteredCandidates.map(c => `
        <tr>
            <td><strong>${c.name || 'Unknown'}</strong></td>
            <td>${c.email || 'N/A'}</td>
            <td>${c.job_title || 'N/A'}</td>
            <td>
                <button class="btn btn-primary btn-sm" onclick="sendIndividualOutreach('${c.id}')">
                    Send Mail
                </button>
            </td>
        </tr>
    `).join('');
}

async function sendBulkOutreach() {
    showToast('Bulk outreach functionality coming soon!', 'info');
}

async function sendIndividualOutreach(candidateId) {
    try {
        const candidate = outreachState.candidates.find(c => c.id === candidateId);
        if (!candidate) {
            showToast('Candidate not found', 'error');
            return;
        }

        const res = await fetch(`${API_BASE}/outreach/send`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                candidate_id: candidateId,
                job_id: candidate.job_id
            })
        });

        const data = await res.json();
        if (res.ok) {
            showToast(`Outreach sent to ${candidate.name}`, 'success');
            await loadOutreachData();
        } else {
            showToast(data.detail || 'Failed to send outreach', 'error');
        }
    } catch (e) {
        showToast('Network error: ' + e.message, 'error');
    }
}

function viewCommunicationTimeline(candidateId) {
    const panel = document.getElementById('communication-timeline-panel');
    const content = document.getElementById('communication-timeline-content');

    if (!panel || !content) return;

    panel.style.display = 'block';
    content.innerHTML = `
        <div class="timeline">
            <div class="timeline-item">
                <div class="timeline-marker bg-blue"></div>
                <div class="timeline-content">
                    <h4>Initial Outreach Sent</h4>
                    <p>Personalized outreach email sent via EmailJS</p>
                    <span class="timeline-time">2 days ago</span>
                </div>
            </div>
            <div class="timeline-item">
                <div class="timeline-marker bg-green"></div>
                <div class="timeline-content">
                    <h4>Email Opened</h4>
                    <p>Candidate opened the outreach email</p>
                    <span class="timeline-time">1 day ago</span>
                </div>
            </div>
            <div class="timeline-item">
                <div class="timeline-marker bg-orange"></div>
                <div class="timeline-content">
                    <h4>Follow-up Scheduled</h4>
                    <p>Automatic follow-up scheduled for Day 3</p>
                    <span class="timeline-time">Tomorrow</span>
                </div>
            </div>
        </div>
    `;
}

function closeCommunicationTimeline() {
    const panel = document.getElementById('communication-timeline-panel');
    if (panel) panel.style.display = 'none';
}

async function exportOutreachData() {
    try {
        const candidates = outreachState.candidates || [];

        if (!candidates.length) {
            showToast('No outreach data to export', 'error');
            return;
        }

        const csv = [
            'Name,Email,Job Title,Score,Outreach Sent,Status,Follow-ups',
            ...candidates.map(c => [
                c.name || '',
                c.email || '',
                c.job_title || '',
                c.score || 0,
                c.sent_at || '',
                c.status || '',
                (c.follow_ups || []).length
            ].map(field => `"${field}"`).join(','))
        ].join('\n');

        const blob = new Blob([csv], { type: 'text/csv' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `outreach-data-${new Date().toISOString().split('T')[0]}.csv`;
        a.click();
        URL.revokeObjectURL(url);

        showToast(`Exported ${candidates.length} outreach records`, 'success');
    } catch (e) {
        showToast('Export failed: ' + e.message, 'error');
    }
}

// ── Enhanced Stage 5: Prescreening Functions ─────────────────────────

// Enhanced prescreening data loading with better stats
async function loadPrescreeningData() {
    await Promise.all([
        loadPrescreeningStats(),
        loadPrescreeningSessions(),
        loadPrescreeningJobs()
    ]);
    updatePrescreeningUI();
}

async function loadPrescreeningJobs() {
    try {
        const res = await fetch(`${API_BASE}/prescreening/jobs`);
        const jobs = await res.json();

        // Update job filter dropdown
        const select = document.getElementById('prescreening-job-filter');
        if (select) {
            select.innerHTML = '<option value="">-- All Jobs --</option>' +
                jobs.map(j =>
                    `<option value="${j.id}">${j.title} (${j.in_prescreening_count} sessions)</option>`
                ).join('');
        }
    } catch (e) {
        console.error('Failed to load prescreening jobs:', e);
    }
}

function updatePrescreeningUI() {
    if (prescreeningState.stats) {
        // Update mini stats
        document.getElementById('prescreening-total').textContent = prescreeningState.stats.total_in_prescreening;
        document.getElementById('prescreening-completed').textContent = prescreeningState.stats.sessions_completed;
        document.getElementById('prescreening-passed').textContent = prescreeningState.stats.passed;
        document.getElementById('bgv-cleared').textContent = prescreeningState.stats.bgv_cleared;

        // Update enhanced stats grid
        document.getElementById('stat-total-sessions').textContent = prescreeningState.stats.sessions_created;
        document.getElementById('stat-sessions-completed').textContent = prescreeningState.stats.sessions_completed;
        document.getElementById('stat-sessions-passed').textContent = prescreeningState.stats.passed;

        // Calculate average score
        const avgScore = prescreeningState.sessions.length > 0 ?
            prescreeningState.sessions.reduce((sum, s) => sum + (s.avg_score || 0), 0) / prescreeningState.sessions.length : 0;
        document.getElementById('stat-avg-prescreening-score').textContent = avgScore.toFixed(1);
    }

    renderPrescreeningSessions();
}

function renderPrescreeningSessions() {
    const tbody = document.getElementById('prescreening-table-body');
    if (!tbody) return;

    if (!prescreeningState.sessions || !prescreeningState.sessions.length) {
        tbody.innerHTML = '<tr><td colspan="9" class="empty-state">No prescreening sessions yet. Candidates who respond to outreach emails will be invited to prescreening.</td></tr>';
        return;
    }

    tbody.innerHTML = prescreeningState.sessions.map(s => `
        <tr>
            <td><strong>${s.candidate_name || 'Unknown'}</strong></td>
            <td>${s.candidate_email || 'N/A'}</td>
            <td>${s.job_title || 'N/A'}</td>
            <td><span class="status-tag ${s.status === 'COMPLETED' ? 'active' : s.status === 'IN_PROGRESS' ? 'draft' : 'pending'}">${s.status || 'PENDING'}</span></td>
            <td>${s.answered_questions || 0} / ${s.total_questions || 6}</td>
            <td>
                ${s.avg_score !== undefined ? `
                    <div class="score-display">
                        <span class="score-value ${getScoreClass(s.avg_score * 25)}">${(s.avg_score * 25).toFixed(0)}</span>
                        <span class="score-label">/ 100</span>
                    </div>
                ` : '<span class="text-muted">-</span>'}
            </td>
            <td>
                ${s.verdict ? `
                    <span class="verdict-badge ${s.verdict.toLowerCase()}">${s.verdict}</span>
                ` : '<span class="text-muted">Pending</span>'}
            </td>
            <td>${s.created_at ? new Date(s.created_at).toLocaleString() : 'N/A'}</td>
            <td>
                <div class="candidate-actions">
                    <button class="btn-icon" onclick="viewSessionDetails('${s.session_id}')" title="View Details">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
                            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                            <circle cx="12" cy="12" r="3"/>
                        </svg>
                    </button>
                    ${s.status === 'COMPLETED' && !s.verdict ? `
                        <button class="btn-icon" onclick="evaluateSession('${s.session_id}')" title="Evaluate">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
                                <path d="M9 12l2 2 4-4"/><circle cx="12" cy="12" r="10"/>
                            </svg>
                        </button>
                    ` : ''}
                </div>
            </td>
        </tr>
    `).join('');
}

async function filterPrescreeningSessions() {
    const jobFilter = document.getElementById('prescreening-job-filter');
    const statusFilter = document.getElementById('prescreening-status-filter');

    const jobId = jobFilter ? jobFilter.value : null;
    const status = statusFilter ? statusFilter.value : null;

    try {
        let url = `${API_BASE}/prescreening/sessions?limit=100`;
        if (jobId) url += `&job_id=${jobId}`;
        if (status) url += `&status=${status}`;

        const res = await fetch(url);
        if (res.ok) {
            prescreeningState.sessions = await res.json();
            renderPrescreeningSessions();
        }
    } catch (e) {
        console.error('Failed to filter prescreening sessions:', e);
    }
}

async function createPrescreeningSession() {
    showToast('Create prescreening session functionality coming soon!', 'info');
}

async function evaluateSession(sessionId) {
    try {
        showToast('Evaluating session with Claude AI...', 'info');

        // This would call the answer evaluator
        const res = await fetch(`${API_BASE}/prescreening/evaluate/${sessionId}`, {
            method: 'POST'
        });

        const data = await res.json();
        if (res.ok) {
            showToast(`Session evaluated: ${data.verdict}`, 'success');
            await loadPrescreeningData();
        } else {
            showToast(data.detail || 'Evaluation failed', 'error');
        }
    } catch (e) {
        showToast('Network error: ' + e.message, 'error');
    }
}

async function runBulkEvaluation() {
    try {
        const completedSessions = prescreeningState.sessions.filter(s =>
            s.status === 'COMPLETED' && !s.verdict
        );

        if (!completedSessions.length) {
            showToast('No completed sessions to evaluate', 'info');
            return;
        }

        showToast(`Evaluating ${completedSessions.length} sessions...`, 'info');

        for (const session of completedSessions) {
            await evaluateSession(session.session_id);
        }

        showToast(`Bulk evaluation completed for ${completedSessions.length} sessions`, 'success');
    } catch (e) {
        showToast('Bulk evaluation failed: ' + e.message, 'error');
    }
}

function viewSessionDetails(sessionId) {
    const session = prescreeningState.sessions.find(s => s.session_id === sessionId);
    if (!session) return;

    const panel = document.getElementById('session-details-panel');
    const content = document.getElementById('session-details-content');

    if (!panel || !content) return;

    panel.style.display = 'block';
    content.innerHTML = `
        <div class="session-overview">
            <h4>${session.candidate_name} - ${session.job_title}</h4>
            <div class="session-meta">
                <span><strong>Status:</strong> ${session.status}</span>
                <span><strong>Created:</strong> ${new Date(session.created_at).toLocaleString()}</span>
                <span><strong>Questions:</strong> ${session.answered_questions}/${session.total_questions}</span>
                ${session.verdict ? `<span><strong>Verdict:</strong> ${session.verdict}</span>` : ''}
            </div>
        </div>
        
        ${session.questions ? `
            <div class="questions-list">
                <h5>Questions & Answers</h5>
                ${session.questions.map((q, i) => `
                    <div class="question-item">
                        <div class="question-text"><strong>Q${i + 1}:</strong> ${q}</div>
                        <div class="answer-placeholder">Answer would be displayed here</div>
                    </div>
                `).join('')}
            </div>
        ` : ''}
    `;
}

function closeSessionDetails() {
    const panel = document.getElementById('session-details-panel');
    if (panel) panel.style.display = 'none';
}

async function exportPrescreeningData() {
    try {
        const sessions = prescreeningState.sessions || [];

        if (!sessions.length) {
            showToast('No prescreening data to export', 'error');
            return;
        }

        const csv = [
            'Candidate Name,Email,Job Title,Status,Questions Answered,Score,Verdict,Created',
            ...sessions.map(s => [
                s.candidate_name || '',
                s.candidate_email || '',
                s.job_title || '',
                s.status || '',
                `${s.answered_questions || 0}/${s.total_questions || 6}`,
                s.avg_score ? (s.avg_score * 25).toFixed(0) : '',
                s.verdict || '',
                s.created_at || ''
            ].map(field => `"${field}"`).join(','))
        ].join('\n');

        const blob = new Blob([csv], { type: 'text/csv' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `prescreening-data-${new Date().toISOString().split('T')[0]}.csv`;
        a.click();
        URL.revokeObjectURL(url);

        showToast(`Exported ${sessions.length} prescreening sessions`, 'success');
    } catch (e) {
        showToast('Export failed: ' + e.message, 'error');
    }
}


// ── Stage 6 & 7: Interview & Evaluation Functions ────────────────────

async function loadInterviewResults() {
    try {
        let sessions = [];

        // Try to load from API, but don't fail if it doesn't work
        try {
            const res = await fetch(`${API_BASE}/interview/sessions`);
            if (res.ok) {
                sessions = await res.json();
            }
        } catch (e) {
            console.log('API not available, showing empty data');
        }

        // Update stats
        const total = sessions.length;
        const completed = sessions.filter(s => s.phase === 'COMPLETE').length;
        const inProgress = sessions.filter(s => s.phase !== 'COMPLETE').length;

        document.getElementById('stat-total-interviews').textContent = total;
        document.getElementById('stat-completed-interviews').textContent = completed;
        document.getElementById('stat-in-progress').textContent = inProgress;

        // Calculate average score
        const completedSessions = sessions.filter(s => s.phase === 'COMPLETE');
        if (completedSessions.length > 0) {
            const avgScore = completedSessions.reduce((sum, s) => sum + (s.overall_score || 0), 0) / completedSessions.length;
            document.getElementById('stat-avg-score').textContent = avgScore.toFixed(1);
        }

        // Always render interview results
        renderInterviewResults(sessions);
    } catch (e) {
        console.error('Failed to load interview results:', e);
        renderInterviewResults([]);
    }
}

function renderInterviewResults(sessions) {
    const container = document.getElementById('interview-results-list');
    if (!container) return;

    if (!sessions.length) {
        container.innerHTML = `
            <div class="empty-state">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="48" height="48" style="opacity: 0.3; margin-bottom: 1rem;">
                    <path d="M23 7l-7 5 7 5V7z"/><rect x="1" y="5" width="15" height="14" rx="2" ry="2"/>
                </svg>
                <p>No completed interviews yet</p>
                <span style="opacity: 0.7; font-size: 0.9em;">Interview results will appear here after candidates complete their sessions</span>
            </div>
        `;
        return;
    }

    // Create table format similar to prescreening
    container.innerHTML = `
        <div class="table-container">
            <table class="results-table">
                <thead>
                    <tr>
                        <th>Candidate</th>
                        <th>Email</th>
                        <th>Job Title</th>
                        <th>Status</th>
                        <th>Score</th>
                        <th>Completed</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    ${sessions.map(s => `
                        <tr>
                            <td><strong>${s.candidate_name || 'Unknown'}</strong></td>
                            <td>${s.candidate_email || 'N/A'}</td>
                            <td>${s.job_title || 'N/A'}</td>
                            <td><span class="status-tag ${s.phase === 'COMPLETE' ? 'active' : s.phase === 'IN_PROGRESS' ? 'draft' : 'pending'}">${s.phase || 'PENDING'}</span></td>
                            <td><strong>10/10</strong></td>
                            <td>${s.created_at ? new Date(s.created_at).toLocaleString() : 'N/A'}</td>
                            <td>
                                <button class="btn-icon" onclick="viewInterviewReport('${s.interview_id}')" title="View Details">
                                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
                                        <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                                        <circle cx="12" cy="12" r="3"/>
                                    </svg>
                                </button>
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        </div>
    `;
}

function getScoreColor(score) {
    if (score >= 0.7) return 'var(--accent-green)';
    if (score >= 0.5) return 'var(--accent-orange)';
    return 'var(--accent-red)';
}

function getRecommendation(score) {
    if (score >= 0.7) return 'Hire';
    if (score >= 0.5) return 'Maybe';
    return 'Reject';
}

function getRecommendationClass(score) {
    if (score >= 0.7) return 'success';
    if (score >= 0.5) return 'warning';
    return 'error';
}

async function viewInterviewReport(interviewId) {
    try {
        const res = await fetch(`${API_BASE}/interview/session/${interviewId}/report`);
        if (!res.ok) {
            showToast('Failed to load interview report', 'error');
            return;
        }

        const report = await res.json();

        // Open report in new window or modal
        const reportWindow = window.open('', '_blank', 'width=1000,height=800');
        reportWindow.document.write(`
            <!DOCTYPE html>
            <html>
            <head>
                <title>Interview Report #${interviewId}</title>
                <style>
                    body { font-family: system-ui, sans-serif; padding: 2rem; max-width: 1200px; margin: 0 auto; }
                    h1 { color: #667eea; }
                    .score-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin: 2rem 0; }
                    .score-card { padding: 1.5rem; background: #f8f9fa; border-radius: 12px; text-align: center; }
                    .score-value { font-size: 2rem; font-weight: bold; color: #667eea; }
                    .score-label { font-size: 0.9rem; color: #666; margin-top: 0.5rem; }
                    .turn-card { padding: 1.5rem; background: white; border: 1px solid #e0e0e0; border-radius: 12px; margin-bottom: 1rem; }
                    .turn-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; }
                    .turn-number { font-weight: bold; color: #667eea; }
                    .turn-score { font-weight: bold; color: ${getScoreColor(report.overall_score)}; }
                    .question { font-weight: 600; margin-bottom: 0.5rem; }
                    .answer { color: #666; margin-bottom: 0.5rem; }
                    .feedback { background: #f0f7ff; padding: 1rem; border-radius: 8px; margin-top: 1rem; }
                </style>
            </head>
            <body>
                <h1>Interview Report #${interviewId}</h1>
                
                <div class="score-grid">
                    <div class="score-card">
                        <div class="score-value">${(report.overall_score * 100).toFixed(0)}%</div>
                        <div class="score-label">Overall Score</div>
                    </div>
                    <div class="score-card">
                        <div class="score-value">${(report.content_score * 100).toFixed(0)}%</div>
                        <div class="score-label">Content Score</div>
                    </div>
                    <div class="score-card">
                        <div class="score-value">${(report.behavior_score * 100).toFixed(0)}%</div>
                        <div class="score-label">Behavior Score</div>
                    </div>
                    <div class="score-card">
                        <div class="score-value">${report.total_turns}</div>
                        <div class="score-label">Total Turns</div>
                    </div>
                </div>
                
                ${report.feedback_summary ? `
                    <div class="feedback">
                        <strong>AI Feedback Summary:</strong><br>
                        ${report.feedback_summary}
                    </div>
                ` : ''}
                
                <h2 style="margin-top: 2rem;">Turn-by-Turn Analysis</h2>
                ${report.turn_reviews.map(turn => `
                    <div class="turn-card">
                        <div class="turn-header">
                            <span class="turn-number">Turn ${turn.turn_number}</span>
                            <span class="turn-score">Score: ${(turn.final_score * 100).toFixed(0)}%</span>
                        </div>
                        <div class="question"><strong>Q:</strong> ${turn.question_text}</div>
                        <div class="answer"><strong>A:</strong> ${turn.candidate_response || 'No response'}</div>
                        <div style="margin-top: 0.5rem; font-size: 0.9em; color: #666;">
                            Content: ${(turn.content_score * 100).toFixed(0)}% | 
                            Behavior: ${(turn.behavior_score * 100).toFixed(0)}% | 
                            Intent: ${turn.intent} | 
                            Response Time: ${turn.response_time_sec}s
                        </div>
                        ${turn.followups && turn.followups.length > 0 ? `
                            <div style="margin-top: 1rem; padding-left: 1rem; border-left: 3px solid #e0e0e0;">
                                <strong>Follow-ups:</strong>
                                ${turn.followups.map(f => `
                                    <div style="margin-top: 0.5rem;">
                                        <div class="question"><strong>Q:</strong> ${f.question_text}</div>
                                        <div class="answer"><strong>A:</strong> ${f.candidate_response}</div>
                                    </div>
                                `).join('')}
                            </div>
                        ` : ''}
                    </div>
                `).join('')}
                
                <button onclick="window.print()" style="margin-top: 2rem; padding: 0.75rem 1.5rem; background: #667eea; color: white; border: none; border-radius: 8px; cursor: pointer;">
                    Print Report
                </button>
            </body>
            </html>
        `);
    } catch (e) {
        console.error('Failed to view report:', e);
        showToast('Failed to load interview report', 'error');
    }
}

async function exportInterviewJSON(interviewId) {
    try {
        const res = await fetch(`${API_BASE}/interview/session/${interviewId}/report`);
        if (!res.ok) {
            showToast('Failed to export interview data', 'error');
            return;
        }

        const data = await res.json();

        // Download as JSON file
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `interview-${interviewId}-report.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);

        showToast('Interview data exported successfully', 'success');
    } catch (e) {
        console.error('Failed to export:', e);
        showToast('Failed to export interview data', 'error');
    }
}

async function exportInterviewData() {
    try {
        const res = await fetch(`${API_BASE}/interview/sessions`);
        if (!res.ok) {
            showToast('Failed to export interview data', 'error');
            return;
        }

        const sessions = await res.json();
        const completedSessions = sessions.filter(s => s.phase === 'COMPLETE');

        // Download as JSON file
        const blob = new Blob([JSON.stringify(completedSessions, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `interview-data-${new Date().toISOString().split('T')[0]}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);

        showToast(`Exported ${completedSessions.length} interview sessions`, 'success');
    } catch (e) {
        console.error('Failed to export:', e);
        showToast('Failed to export interview data', 'error');
    }
}

function viewAPIEndpoints() {
    const endpoints = [
        { method: 'GET', path: '/api/interview/sessions', desc: 'List all interview sessions' },
        { method: 'GET', path: '/api/interview/session/{id}/report', desc: 'Get interview report' },
        { method: 'POST', path: '/api/interview/resume/upload', desc: 'Upload resume for question generation' },
        { method: 'POST', path: '/api/interview/session/start', desc: 'Start new interview' },
        { method: 'GET', path: '/api/interview/session/{id}/next', desc: 'Get next question' },
        { method: 'POST', path: '/api/interview/session/{id}/respond', desc: 'Submit response' },
    ];

    const modal = document.createElement('div');
    modal.style.cssText = 'position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 10000;';
    modal.innerHTML = `
        <div style="background: white; padding: 2rem; border-radius: 16px; max-width: 800px; max-height: 80vh; overflow-y: auto;">
            <h2 style="margin: 0 0 1.5rem 0;">Interview API Endpoints</h2>
            <table style="width: 100%; border-collapse: collapse;">
                <thead>
                    <tr style="border-bottom: 2px solid #e0e0e0;">
                        <th style="text-align: left; padding: 0.75rem;">Method</th>
                        <th style="text-align: left; padding: 0.75rem;">Endpoint</th>
                        <th style="text-align: left; padding: 0.75rem;">Description</th>
                    </tr>
                </thead>
                <tbody>
                    ${endpoints.map(e => `
                        <tr style="border-bottom: 1px solid #f0f0f0;">
                            <td style="padding: 0.75rem;"><code style="background: #f0f7ff; padding: 0.25rem 0.5rem; border-radius: 4px; color: #667eea;">${e.method}</code></td>
                            <td style="padding: 0.75rem; font-family: monospace; font-size: 0.9em;">${e.path}</td>
                            <td style="padding: 0.75rem; color: #666;">${e.desc}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
            <div style="margin-top: 1.5rem; text-align: right;">
                <button onclick="this.closest('div[style*=fixed]').remove()" style="padding: 0.75rem 1.5rem; background: #667eea; color: white; border: none; border-radius: 8px; cursor: pointer;">
                    Close
                </button>
            </div>
        </div>
    `;
    document.body.appendChild(modal);
    modal.addEventListener('click', (e) => {
        if (e.target === modal) modal.remove();
    });
}

// Auto-load interview results when switching to stage 6 tab
const originalSwitchTab = switchTab;
switchTab = function (tabId) {
    originalSwitchTab(tabId);
    if (tabId === 'stage6') {
        loadInterviewResults();
    }
};


// ── Stage 8: Offer Management Functions ────────────────────────

async function loadOffers() {
    try {
        let offers = [];

        // Try to load from API, but don't fail if it doesn't work
        try {
            const res = await fetch(`${API_BASE}/offer/list`);
            if (res.ok) {
                const data = await res.json();
                offers = data.offers || [];
            }
        } catch (e) {
            console.log('API not available, showing empty data');
        }

        // Enrich offers with interview summary for UI (non-blocking)
        try {
            const enriched = await Promise.all(offers.map(async (offer) => {
                // Determine candidate_id from application_id or candidate_id field
                let candidateId = null;
                if (offer.candidate_id) candidateId = offer.candidate_id;
                else if (offer.application_id && typeof offer.application_id === 'string') {
                    const m = offer.application_id.match(/app_(\d+)/);
                    if (m) candidateId = parseInt(m[1], 10);
                }

                if (candidateId) {
                    try {
                        const r = await fetch(`${API_BASE}/offer/candidate-interview-summary/${candidateId}`);
                        if (r.ok) {
                            const jd = await r.json();
                            offer.interview = jd.interview || null;
                        }
                    } catch (e) {
                        // ignore enrichment failures
                    }
                }
                return offer;
            }));
            offers = enriched;
        } catch (e) {
            console.warn('Failed to enrich offers with interview data', e);
        }

        // Update stats
        document.getElementById('stat-total-offers').textContent = offers.length;
        document.getElementById('stat-accepted-offers').textContent = offers.filter(o => o.status === 'accepted').length;
        document.getElementById('stat-pending-offers').textContent = offers.filter(o => o.status === 'pending').length;
        document.getElementById('stat-negotiations').textContent = offers.filter(o => o.status === 'negotiating').length;

        // Render offers list
        renderOffers(offers);
    } catch (e) {
        console.error('Failed to load offers:', e);
        renderOffers([]);
    }
}

function renderOffers(offers) {
    const container = document.getElementById('offers-list');
    if (!container) return;

    if (!offers.length) {
        container.innerHTML = `
            <div class="empty-state">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="48" height="48" style="opacity: 0.3; margin-bottom: 1rem;">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/>
                </svg>
                <p>No offers generated yet</p>
                <span style="opacity: 0.7; font-size: 0.9em;">Offers will appear here after interview completion</span>
            </div>
        `;
        return;
    }

    container.innerHTML = offers.map(offer => `
        <div class="item-card">
            <div class="item-card-info">
                <h4>Offer ${offer.id}</h4>
                <p>Application: ${offer.application_id} • Salary: $${offer.offered_salary?.toLocaleString() || '0'} ${offer.currency || 'USD'}</p>
                <p style="font-size: 0.9em; opacity: 0.7;">Start Date: ${offer.start_date || 'TBD'} • Offered: ${offer.offered_at ? new Date(offer.offered_at).toLocaleDateString() : 'N/A'}</p>
                ${offer.interview ? `<p style="margin-top:6px;font-size:0.9em;">Interview Score: <strong>${(offer.interview.final_score || offer.interview.final_score === 0) ? offer.interview.final_score : (offer.interview.final_score)}</strong> • Content ${offer.interview.content_score} • Behavior ${offer.interview.behavior_score}</p>` : ''}
            </div>
            <div class="item-card-actions">
                <span class="status-tag ${getOfferStatusClass(offer.status)}">${offer.status.toUpperCase()}</span>
                ${offer.status === 'pending' ? `
                    <button class="btn btn-primary btn-sm" onclick="acceptOffer('${offer.id}')">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
                            <polyline points="20 6 9 17 4 12"/>
                        </svg>
                        Accept Offer
                    </button>
                ` : ''}
            </div>
        </div>
    `).join('');
}

function getOfferStatusClass(status) {
    const statusMap = {
        'generated': 'info',
        'sent': 'warning',
        'accepted': 'success',
        'rejected': 'error',
        'negotiating': 'warning'
    };
    return statusMap[status] || 'info';
}

async function dispatchOffer(offerId) {
    try {
        const res = await fetch(`${API_BASE}/offer/dispatch/${offerId}`, { method: 'POST' });
        if (!res.ok) {
            showToast('Failed to dispatch offer', 'error');
            return;
        }

        showToast('Offer dispatched successfully', 'success');
        loadOffers();
    } catch (e) {
        console.error('Failed to dispatch offer:', e);
        showToast('Failed to dispatch offer', 'error');
    }
}

async function acceptOffer(offerId) {
    if (!confirm('Accept this offer and start onboarding?')) return;

    try {
        const res = await fetch(`${API_BASE}/offer/accept/${offerId}`, { method: 'POST' });
        if (!res.ok) {
            showToast('Failed to accept offer', 'error');
            return;
        }

        const data = await res.json();
        showToast(`Offer accepted! Onboarding started for ${data.candidate_id}`, 'success');
        loadOffers();

        // Refresh onboarding tab if visible
        if (document.getElementById('tab-stage9').classList.contains('active')) {
            loadOnboarding();
        }
    } catch (e) {
        console.error('Failed to accept offer:', e);
        showToast('Failed to accept offer', 'error');
    }
}

// ── Stage 9: Onboarding Functions ────────────────────────

async function loadOnboarding() {
    try {
        let records = [];

        // Try to load from API, but don't fail if it doesn't work
        try {
            const res = await fetch(`${API_BASE}/onboarding/list`);
            if (res.ok) {
                const data = await res.json();
                records = data.onboarding || [];
            }
        } catch (e) {
            console.log('API not available, showing empty data');
        }

        // Update stats
        document.getElementById('stat-total-onboarding').textContent = records.length;
        document.getElementById('stat-completed-onboarding').textContent = records.filter(r => r.status === 'completed').length;
        // Note: pending docs and tasks would need additional API calls

        // Render onboarding list
        renderOnboarding(records);
    } catch (e) {
        console.error('Failed to load onboarding:', e);
        renderOnboarding([]);
    }
}

function renderOnboarding(records) {
    const container = document.getElementById('onboarding-list');
    if (!container) return;

    if (!records.length) {
        container.innerHTML = `
            <div class="empty-state">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="48" height="48" style="opacity: 0.3; margin-bottom: 1rem;">
                    <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/>
                </svg>
                <p>No onboarding records yet</p>
                <span style="opacity: 0.7; font-size: 0.9em;">Onboarding starts after offer acceptance</span>
            </div>
        `;
        return;
    }

    container.innerHTML = records.map(record => `
        <div class="item-card">
            <div class="item-card-info">
                <h4>${record.candidate_name || 'Unknown Candidate'}</h4>
                <p><strong>Position:</strong> ${record.job_title || 'Unknown Position'} • <strong>Email:</strong> ${record.candidate_email || 'N/A'}</p>
                <p><strong>Manager:</strong> ${record.manager_assigned || 'TBD'} • <strong>Department:</strong> ${record.department || 'N/A'}</p>
                <p><strong>Start Date:</strong> ${record.start_date || 'TBD'} • <strong>Tasks:</strong> ${record.tasks_completed || 0}/${record.total_tasks || 0}</p>
                <p style="font-size: 0.9em; opacity: 0.7;"><strong>Documents:</strong> ${record.documents_status || 'pending'} • <strong>BGV:</strong> ${record.bgv_status || 'pending'} • <strong>IT:</strong> ${record.it_provisioning_status || 'pending'}</p>
                <p style="font-size: 0.9em; opacity: 0.7;"><strong>Started:</strong> ${new Date(record.created_at).toLocaleDateString()}</p>
            </div>
            <div class="item-card-actions">
                <span class="status-tag ${getOnboardingStatusClass(record.status)}">${record.status.toUpperCase()}</span>
                <button class="btn btn-ghost btn-sm" onclick="viewOnboardingTasks('${record.id}')">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
                        <polyline points="9 11 12 14 22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/>
                    </svg>
                    View Tasks
                </button>
            </div>
        </div>
    `).join('');
}

function getOnboardingStatusClass(status) {
    const statusMap = {
        'pending': 'warning',
        'documents_pending': 'warning',
        'bgv_pending': 'warning',
        'it_provisioned': 'info',
        'completed': 'success'
    };
    return statusMap[status] || 'info';
}

async function viewOnboardingTasks(onboardingId) {
    try {
        const res = await fetch(`${API_BASE}/onboarding/${onboardingId}/tasks`);
        if (!res.ok) {
            showToast('Failed to load tasks', 'error');
            return;
        }

        const data = await res.json();
        const tasks = data.tasks || [];

        // Show tasks in a modal or new window
        alert(`Onboarding Tasks:\n\n${tasks.map(t => `- ${t.task} (${t.phase})`).join('\n')}`);
    } catch (e) {
        console.error('Failed to load tasks:', e);
        showToast('Failed to load tasks', 'error');
    }
}

// ── Stage 10: Analytics Functions ────────────────────────

async function loadAnalyticsDashboard() {
    try {
        let data = { funnel: [] };

        // Try to load from API, but don't fail if it doesn't work
        try {
            const res = await fetch(`${API_BASE}/analytics/dashboard`);
            if (res.ok) {
                data = await res.json();
            }
        } catch (e) {
            console.log('API not available, showing empty data');
        }

        renderFunnelMetrics(data.funnel || []);
    } catch (e) {
        console.error('Failed to load analytics:', e);
        renderFunnelMetrics([]);
    }
}

function renderFunnelMetrics(funnel) {
    const container = document.getElementById('funnel-metrics');
    if (!container) return;

    if (!funnel.length) {
        container.innerHTML = '<div class="empty-state">No funnel data available</div>';
        return;
    }

    container.innerHTML = `
        <div style="overflow-x: auto;">
            <table style="width: 100%; border-collapse: collapse;">
                <thead>
                    <tr style="background: rgba(102, 126, 234, 0.1); text-align: left;">
                        <th style="padding: 1rem; border-bottom: 2px solid #e0e0e0;">Stage</th>
                        <th style="padding: 1rem; border-bottom: 2px solid #e0e0e0;">Count</th>
                        <th style="padding: 1rem; border-bottom: 2px solid #e0e0e0;">Drop-off %</th>
                    </tr>
                </thead>
                <tbody>
                    ${funnel.map(stage => `
                        <tr style="border-bottom: 1px solid #e0e0e0;">
                            <td style="padding: 1rem;">${stage.stage}</td>
                            <td style="padding: 1rem; font-weight: 600;">${stage.count}</td>
                            <td style="padding: 1rem; color: ${stage.dropoff_pct > 50 ? 'var(--accent-red)' : 'var(--accent-green)'};">
                                ${stage.dropoff_pct}%
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        </div>
    `;
}

async function exportAnalyticsCSV() {
    try {
        const res = await fetch(`${API_BASE}/analytics/export/csv`);
        if (!res.ok) {
            showToast('Failed to export CSV', 'error');
            return;
        }

        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'recruitment_dashboard.csv';
        a.click();

        showToast('CSV exported successfully', 'success');
    } catch (e) {
        console.error('Failed to export CSV:', e);
        showToast('Failed to export CSV', 'error');
    }
}

async function exportAnalyticsPDF() {
    try {
        const res = await fetch(`${API_BASE}/analytics/export/pdf`);
        if (!res.ok) {
            showToast('Failed to export PDF', 'error');
            return;
        }

        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'recruitment_dashboard.pdf';
        a.click();

        showToast('PDF exported successfully', 'success');
    } catch (e) {
        console.error('Failed to export PDF:', e);
        showToast('Failed to export PDF', 'error');
    }
}

function viewOfferDetails(offerId) {
    showToast('Offer details view coming soon!', 'info');
}
function viewOnboardingTasks(onboardingId) {
    showToast('Onboarding tasks view coming soon!', 'info');
}

// ── Additional Stage 4 & 5 Functions ─────────────────────

// Filter functions
function filterOutreachCandidates() {
    const jobFilter = document.getElementById('outreach-job-filter');
    const selectedJobId = jobFilter ? jobFilter.value : '';

    let filteredCandidates = outreachState.candidates || [];
    if (selectedJobId) {
        filteredCandidates = filteredCandidates.filter(c => c.job_id === selectedJobId);
    }

    const tbody = document.getElementById('outreach-table-body');
    if (!tbody) return;

    if (!filteredCandidates.length) {
        tbody.innerHTML = '<tr><td colspan="4" class="empty-state">No candidates found for the selected job.</td></tr>';
        return;
    }

    tbody.innerHTML = filteredCandidates.map(c => `
        <tr>
            <td><strong>${c.name || 'Unknown'}</strong></td>
            <td>${c.email || 'N/A'}</td>
            <td>${c.job_title || 'N/A'}</td>
            <td>
                <button class="btn btn-primary btn-sm" onclick="sendIndividualOutreach('${c.id}')">
                    Send Mail
                </button>
            </td>
        </tr>
    `).join('');
}

function filterPrescreeningSessions() {
    const jobFilter = document.getElementById('prescreening-job-filter');
    const statusFilter = document.getElementById('prescreening-status-filter');
    const selectedJobId = jobFilter ? jobFilter.value : '';
    const selectedStatus = statusFilter ? statusFilter.value : '';

    // Filter sessions based on job and status selection
    let filteredSessions = prescreeningState.sessions;
    if (selectedJobId) {
        filteredSessions = filteredSessions.filter(s => s.job_id === selectedJobId);
    }
    if (selectedStatus) {
        filteredSessions = filteredSessions.filter(s => s.status === selectedStatus);
    }

    // Update the display with filtered sessions
    const tbody = document.getElementById('prescreening-table-body');
    if (!tbody) return;

    if (!filteredSessions.length) {
        tbody.innerHTML = '<tr><td colspan="9" class="empty-state">No sessions found for the selected filters.</td></tr>';
        return;
    }

    tbody.innerHTML = filteredSessions.map(s => `
        <tr>
            <td><strong>${s.candidate_name || 'Unknown'}</strong></td>
            <td>${s.candidate_email || 'N/A'}</td>
            <td>${s.job_title || 'N/A'}</td>
            <td><span class="status-tag ${s.status === 'COMPLETED' ? 'active' : s.status === 'IN_PROGRESS' ? 'draft' : 'pending'}">${s.status || 'PENDING'}</span></td>
            <td>${s.answered_questions || 0} / ${s.total_questions || 6}</td>
            <td>${s.avg_score ? `<span class="score-badge">${s.avg_score.toFixed(1)}</span>` : 'N/A'}</td>
            <td>${s.verdict ? `<span class="status-tag ${s.verdict === 'PASS' ? 'active' : s.verdict === 'FAIL' ? 'closed' : 'draft'}">${s.verdict}</span>` : 'N/A'}</td>
            <td>${s.created_at ? new Date(s.created_at).toLocaleString() : 'N/A'}</td>
            <td>
                <button class="btn-icon" onclick="viewSessionDetails('${s.session_id}')" title="View Details">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
                        <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                        <circle cx="12" cy="12" r="3"/>
                    </svg>
                </button>
            </td>
        </tr>
    `).join('');
}

// Export functions
function exportOutreachData() {
    const data = outreachState.candidates.map(c => ({
        name: c.name || 'Unknown',
        email: c.email || 'N/A',
        job_title: c.job_title || 'N/A',
        score: c.score || 0,
        sent_at: c.sent_at || 'N/A',
        status: c.status || 'PENDING',
        follow_ups: c.follow_ups || 0
    }));

    const csv = convertToCSV(data);
    downloadCSV(csv, 'outreach_data.csv');
    showToast('Outreach data exported successfully!', 'success');
}

function exportPrescreeningData() {
    const data = prescreeningState.sessions.map(s => ({
        candidate_name: s.candidate_name || 'Unknown',
        candidate_email: s.candidate_email || 'N/A',
        job_title: s.job_title || 'N/A',
        status: s.status || 'PENDING',
        answered_questions: s.answered_questions || 0,
        total_questions: s.total_questions || 6,
        avg_score: s.avg_score || 'N/A',
        verdict: s.verdict || 'N/A',
        created_at: s.created_at || 'N/A'
    }));

    const csv = convertToCSV(data);
    downloadCSV(csv, 'prescreening_data.csv');
    showToast('Prescreening data exported successfully!', 'success');
}

// Bulk operations
async function sendBulkOutreach() {
    try {
        const res = await fetch(`${API_BASE}/outreach/bulk-send`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({})
        });

        const data = await res.json();
        if (res.ok) {
            showToast(`Bulk outreach sent to ${data.sent_count} candidates`, 'success');
            await loadOutreachData();
        } else {
            showToast(data.detail || 'Bulk outreach failed', 'error');
        }
    } catch (e) {
        showToast('Network error: ' + e.message, 'error');
    }
}

async function runBulkEvaluation() {
    try {
        const res = await fetch(`${API_BASE}/prescreening/bulk-evaluate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({})
        });

        const data = await res.json();
        if (res.ok) {
            showToast(`Bulk evaluation completed for ${data.evaluated_count} sessions`, 'success');
            await loadPrescreeningData();
        } else {
            showToast(data.detail || 'Bulk evaluation failed', 'error');
        }
    } catch (e) {
        showToast('Network error: ' + e.message, 'error');
    }
}

async function createPrescreeningSession() {
    showToast('Create prescreening session functionality coming soon!', 'info');
}

// Communication timeline functions
function viewCommunicationTimeline(candidateId) {
    const panel = document.getElementById('communication-timeline-panel');
    const content = document.getElementById('communication-timeline-content');

    if (panel && content) {
        panel.style.display = 'block';
        content.innerHTML = `
            <div class="timeline-item">
                <div class="timeline-date">Today</div>
                <div class="timeline-content">
                    <h4>Initial Outreach Sent</h4>
                    <p>Personalized email sent to candidate</p>
                </div>
            </div>
            <div class="timeline-item">
                <div class="timeline-date">3 days ago</div>
                <div class="timeline-content">
                    <h4>Candidate Shortlisted</h4>
                    <p>Candidate passed screening with score 85/100</p>
                </div>
            </div>
        `;
    }
}

function closeCommunicationTimeline() {
    const panel = document.getElementById('communication-timeline-panel');
    if (panel) {
        panel.style.display = 'none';
    }
}

function closeSessionDetails() {
    const panel = document.getElementById('session-details-panel');
    if (panel) {
        panel.style.display = 'none';
    }
}

// Utility functions
function convertToCSV(data) {
    if (!data.length) return '';

    const headers = Object.keys(data[0]);
    const csvContent = [
        headers.join(','),
        ...data.map(row => headers.map(header => {
            const value = row[header];
            return typeof value === 'string' && value.includes(',') ? `"${value}"` : value;
        }).join(','))
    ].join('\n');

    return csvContent;
}

function downloadCSV(csv, filename) {
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');

    if (link.download !== undefined) {
        const url = URL.createObjectURL(blob);
        link.setAttribute('href', url);
        link.setAttribute('download', filename);
        link.style.visibility = 'hidden';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }
}

// Update stats display functions
function updateOutreachStatsDisplay() {
    if (outreachState.stats) {
        // Update mini stats
        document.getElementById('outreach-sent').textContent = outreachState.stats.total_sent || 0;
        document.getElementById('outreach-opened').textContent = outreachState.stats.opened || 0;
        document.getElementById('outreach-replied').textContent = outreachState.stats.replied || 0;
        document.getElementById('outreach-unresponsive').textContent = outreachState.stats.unresponsive || 0;

        // Update main stats grid
        document.getElementById('stat-total-shortlisted').textContent = outreachState.stats.total_shortlisted || 0;
        document.getElementById('stat-outreach-sent').textContent = outreachState.stats.total_sent || 0;
        document.getElementById('stat-emails-opened').textContent = outreachState.stats.opened || 0;
        document.getElementById('stat-candidates-replied').textContent = outreachState.stats.replied || 0;
    }
}

function updatePrescreeningStatsDisplay() {
    if (prescreeningState.stats) {
        // Update mini stats
        document.getElementById('prescreening-total').textContent = prescreeningState.stats.total_sessions || 0;
        document.getElementById('prescreening-completed').textContent = prescreeningState.stats.completed || 0;
        document.getElementById('prescreening-passed').textContent = prescreeningState.stats.passed || 0;
        document.getElementById('bgv-cleared').textContent = prescreeningState.stats.bgv_cleared || 0;

        // Update main stats grid
        document.getElementById('stat-total-sessions').textContent = prescreeningState.stats.total_sessions || 0;
        document.getElementById('stat-sessions-completed').textContent = prescreeningState.stats.completed || 0;
        document.getElementById('stat-sessions-passed').textContent = prescreeningState.stats.passed || 0;
        document.getElementById('stat-avg-prescreening-score').textContent = prescreeningState.stats.avg_score ? prescreeningState.stats.avg_score.toFixed(1) : '0.0';
    }
}

// Update the main update functions to use the new display functions
function updateOutreachUI() {
    updateOutreachStatsDisplay();
    renderOutreachCandidates();
}

function updatePrescreeningUI() {
    updatePrescreeningStatsDisplay();
    renderPrescreeningSessions();
}
