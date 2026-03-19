/* ═══════════════════════════════════════
   Auth State
   ═══════════════════════════════════════ */
const auth = {
    token: localStorage.getItem('latex_token'),
    user: JSON.parse(localStorage.getItem('latex_user') || 'null'),
    isLoggedIn() { return !!this.token; },
    login(token, user) {
        this.token = token;
        this.user = user;
        localStorage.setItem('latex_token', token);
        localStorage.setItem('latex_user', JSON.stringify(user));
        updateAuthUI();
    },
    logout() {
        this.token = null;
        this.user = null;
        localStorage.removeItem('latex_token');
        localStorage.removeItem('latex_user');
        updateAuthUI();
        showHome();
    },
    headers() {
        const h = { 'Content-Type': 'application/json' };
        if (this.token) h['Authorization'] = `Bearer ${this.token}`;
        return h;
    },
};

async function authFetch(url, options = {}) {
    const headers = options.headers || {};
    // Add auth token
    if (auth.token) headers['Authorization'] = `Bearer ${auth.token}`;
    // Only set Content-Type for non-FormData bodies
    if (!(options.body instanceof FormData)) {
        headers['Content-Type'] = headers['Content-Type'] || 'application/json';
    }
    options.headers = headers;
    const res = await fetch(url, options);
    if (res.status === 401) {
        auth.logout();
        showAuthModal('login');
        throw new Error('Session expired');
    }
    return res;
}

function updateAuthUI() {
    const loggedIn = auth.isLoggedIn();
    document.getElementById('navLogin').style.display = loggedIn ? 'none' : '';
    document.getElementById('navRegister').style.display = loggedIn ? 'none' : '';
    document.getElementById('navProjects').style.display = loggedIn ? '' : 'none';
    document.getElementById('navLogout').style.display = loggedIn ? '' : 'none';
    const userEl = document.getElementById('navUser');
    if (loggedIn) {
        userEl.textContent = auth.user.email;
        userEl.style.display = '';
    } else {
        userEl.style.display = 'none';
    }
}

/* ═══════════════════════════════════════
   Auth Modal
   ═══════════════════════════════════════ */
let authMode = 'login';

function showAuthModal(mode) {
    authMode = mode;
    document.getElementById('authModalTitle').textContent = mode === 'login' ? 'Login' : 'Sign Up';
    document.getElementById('authSubmitBtn').textContent = mode === 'login' ? 'Login' : 'Sign Up';
    document.getElementById('authToggleLink').textContent = mode === 'login'
        ? "Don't have an account? Sign up"
        : 'Already have an account? Login';
    document.getElementById('authToggleLink').onclick = () => showAuthModal(mode === 'login' ? 'register' : 'login');
    document.getElementById('authError').style.display = 'none';
    document.getElementById('authEmail').value = '';
    document.getElementById('authPassword').value = '';
    document.getElementById('authModal').classList.add('active');
}

function closeAuthModal() {
    document.getElementById('authModal').classList.remove('active');
}

async function submitAuth() {
    const email = document.getElementById('authEmail').value.trim();
    const password = document.getElementById('authPassword').value;
    const errEl = document.getElementById('authError');
    errEl.style.display = 'none';

    if (!email || !password) {
        errEl.textContent = 'Please fill in both fields';
        errEl.style.display = 'block';
        return;
    }

    const url = authMode === 'login' ? '/api/auth/login' : '/api/auth/register';
    try {
        const res = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password }),
        });
        const data = await res.json();
        if (!res.ok) {
            errEl.textContent = data.detail || 'Something went wrong';
            errEl.style.display = 'block';
            return;
        }
        auth.login(data.token, data.user);
        closeAuthModal();
    } catch (e) {
        errEl.textContent = 'Network error';
        errEl.style.display = 'block';
    }
}

// Allow pressing Enter in auth modal
document.getElementById('authPassword').addEventListener('keydown', (e) => {
    if (e.key === 'Enter') submitAuth();
});

/* ═══════════════════════════════════════
   Routing / Views
   ═══════════════════════════════════════ */
function navigateTo(path) {
    history.pushState(null, '', path);
    router();
}

function showHome() {
    navigateTo('/');
}

function showDashboard() {
    if (!auth.isLoggedIn()) { showAuthModal('login'); return; }
    navigateTo('/projects');
}

// Close the live mode overlay without changing the URL (used by the router)
function closeLiveModeQuiet() {
    if (!document.getElementById('liveModeContainer').classList.contains('active')) return;
    if (activeFileId && isMultiFileMode()) {
        fileContentsCache[activeFileId] = liveEditor.value;
    }
    if (currentProject && liveEditor.value !== lastSavedSource) {
        if (confirm('You have unsaved changes. Save before exiting?')) {
            saveProject();
        }
    }
    document.getElementById('liveModeContainer').classList.remove('active');
    document.body.style.overflow = '';
    clearInterval(autoSaveTimer);
    currentProject = null;
    currentShareLink = null;
    projectFiles = [];
    activeFileId = null;
    fileContentsCache = {};
    expandedFolders = new Set();
    showFileTree(false);
}

async function router() {
    const path = window.location.pathname;

    if (path.startsWith('/shared/')) {
        closeLiveModeQuiet();
        const linkId = path.slice(8);
        document.getElementById('mainContainer').style.display = 'none';
        document.getElementById('projectDashboard').classList.remove('active');
        await openSharedProject(linkId);

    } else if (path.startsWith('/projects/')) {
        const projectId = path.slice(10);
        if (auth.isLoggedIn() && projectId) {
            if (!currentProject || currentProject.id !== projectId) {
                closeLiveModeQuiet();
                document.getElementById('mainContainer').style.display = 'none';
                document.getElementById('projectDashboard').classList.remove('active');
                await openProject(projectId);
            }
        } else {
            closeLiveModeQuiet();
            document.getElementById('mainContainer').style.display = '';
            document.getElementById('projectDashboard').classList.remove('active');
        }

    } else if (path === '/projects') {
        closeLiveModeQuiet();
        if (auth.isLoggedIn()) {
            document.getElementById('mainContainer').style.display = 'none';
            document.getElementById('projectDashboard').classList.add('active');
            loadProjects();
        } else {
            document.getElementById('mainContainer').style.display = '';
            document.getElementById('projectDashboard').classList.remove('active');
        }

    } else {
        // / — home
        closeLiveModeQuiet();
        document.getElementById('mainContainer').style.display = '';
        document.getElementById('projectDashboard').classList.remove('active');
    }
}

window.addEventListener('popstate', router);

/* ═══════════════════════════════════════
   Project Dashboard
   ═══════════════════════════════════════ */
async function loadProjects() {
    const listEl = document.getElementById('projectList');
    listEl.innerHTML = '<li class="project-empty">Loading...</li>';
    try {
        const res = await authFetch('/api/projects');
        const projects = await res.json();
        if (projects.length === 0) {
            listEl.innerHTML = '<li class="project-empty">No projects yet. Create one to get started!</li>';
            return;
        }
        listEl.innerHTML = projects.map(p => `
            <li class="project-card">
                <div class="project-card-info">
                    <div class="project-card-title">${escHtml(p.title)}</div>
                    <div class="project-card-date">Updated ${new Date(p.updated_at).toLocaleString()}</div>
                </div>
                <div class="project-card-actions">
                    <button class="btn btn-sm" onclick="navigateTo('/projects/${p.id}')">Open</button>
                    <button class="btn btn-sm" style="background:#38a169;" onclick="downloadProjectZipById('${p.id}', '${escHtml(p.title)}')">Download</button>
                    <button class="btn btn-sm" style="background:#0ea5e9;" onclick="openShareModal('${p.id}', '${escHtml(p.title)}')">Share</button>
                    <button class="btn btn-sm" style="background:#e53e3e;" onclick="confirmDeleteProject('${p.id}')">Delete</button>
                </div>
            </li>
        `).join('');
    } catch (e) {
        listEl.innerHTML = '<li class="project-empty">Failed to load projects.</li>';
    }
}

async function createNewProject() {
    try {
        const res = await authFetch('/api/projects', {
            method: 'POST',
            body: JSON.stringify({ title: 'Untitled Project', source: DEFAULT_TEX }),
        });
        const project = await res.json();
        navigateTo('/projects/' + project.id);
    } catch (e) { /* ignore */ }
}

async function openProject(projectId) {
    try {
        const res = await authFetch(`/api/projects/${projectId}`);
        if (!res.ok) return;
        const project = await res.json();
        currentProject = project;
        currentShareLink = null;
        fileContentsCache = {};
        expandedFolders = new Set();
        liveEditor.readOnly = false;
        const titleEl = document.getElementById('liveHeaderTitle');
        titleEl.textContent = project.title;
        titleEl.classList.add('editable');
        document.getElementById('liveSaveBtn').style.display = '';
        document.getElementById('liveModeContainer').classList.add('active');
        document.body.style.overflow = 'hidden';

        // Load file tree
        projectFiles = project.files || [];
        if (projectFiles.length > 0) {
            showFileTree(true);
            document.querySelector('.file-tree-actions').style.display = '';
            renderFileTree();
            // Open main file
            const mainFile = project.main_file || 'main.tex';
            const mainF = projectFiles.find(f => f.filename === mainFile);
            if (mainF) {
                await openFile(mainF.id);
            } else {
                await openFile(projectFiles[0].id);
            }
        } else {
            // Fallback to legacy single-file mode
            showFileTree(false);
            liveEditor.value = project.source || DEFAULT_TEX;
            document.getElementById('editorPanelLabel').textContent = 'LaTeX Source';
        }

        resetLivePreview();

        // Load cached render if available (non-blocking)
        loadCachedRender(projectId);
    } catch (e) { /* ignore */ }
}

async function loadCachedRender(projectId) {
    const overlay = document.getElementById('pdfLoadingOverlay');
    try {
        // Show loading spinner
        livePdfPlaceholder.style.display = 'none';
        overlay.style.display = 'flex';

        const res = await authFetch(`/api/projects/${projectId}/cached-render`);
        if (res.status === 204 || !res.ok) {
            overlay.style.display = 'none';
            livePdfPlaceholder.style.display = '';
            return;
        }
        const data = await res.json();
        if (data && data.pdf_base64) {
            const pdfBytes = Uint8Array.from(atob(data.pdf_base64), c => c.charCodeAt(0));
            synctexData = data.synctex || null;
            liveErrorPanel.style.display = 'none';
            pdfViewerContainer.style.display = 'block';
            await renderPdfPages(pdfBytes);
            overlay.style.display = 'none';
            setLiveStatus('ready', 'Loaded from cache');
        } else {
            overlay.style.display = 'none';
            livePdfPlaceholder.style.display = '';
        }
    } catch (e) {
        overlay.style.display = 'none';
        livePdfPlaceholder.style.display = '';
    }
}

async function confirmDeleteProject(projectId) {
    if (!confirm('Delete this project? This cannot be undone.')) return;
    try {
        await authFetch(`/api/projects/${projectId}`, { method: 'DELETE' });
        loadProjects();
    } catch (e) { /* ignore */ }
}

/* ═══════════════════════════════════════
   Share Modal
   ═══════════════════════════════════════ */
let shareProjectId = null;

function openShareModal(projectId, title) {
    shareProjectId = projectId;
    document.getElementById('shareModalTitle').textContent = `Share "${title}"`;
    document.getElementById('shareError').style.display = 'none';
    document.getElementById('shareModal').classList.add('active');
    loadShareLinks();
}

function closeShareModal() {
    document.getElementById('shareModal').classList.remove('active');
    shareProjectId = null;
}

async function generateShareLink() {
    const level = document.getElementById('shareAccessLevel').value;
    const errEl = document.getElementById('shareError');
    errEl.style.display = 'none';
    try {
        const res = await authFetch(`/api/projects/${shareProjectId}/share`, {
            method: 'POST',
            body: JSON.stringify({ access_level: level }),
        });
        if (!res.ok) {
            const d = await res.json();
            errEl.textContent = d.detail || 'Failed';
            errEl.style.display = 'block';
            return;
        }
        loadShareLinks();
    } catch (e) {
        errEl.textContent = 'Network error';
        errEl.style.display = 'block';
    }
}

async function loadShareLinks() {
    const container = document.getElementById('shareLinksContainer');
    container.innerHTML = 'Loading...';
    try {
        const res = await authFetch(`/api/projects/${shareProjectId}`);
        const project = await res.json();
        const links = project.share_links || [];
        if (links.length === 0) {
            container.innerHTML = '<div style="color:#999;font-size:0.85rem;text-align:center;">No share links yet.</div>';
            return;
        }
        container.innerHTML = links.map(l => {
            const url = `${location.origin}/shared/${l.id}`;
            return `
                <div class="share-link-row">
                    <span class="share-link-badge ${l.access_level}">${l.access_level}</span>
                    <span class="share-link-url">${url}</span>
                    <button class="btn btn-sm" style="padding:4px 10px;font-size:0.75rem;" onclick="copyText('${url}')">Copy</button>
                    <button class="btn btn-sm" style="padding:4px 10px;font-size:0.75rem;background:#e53e3e;" onclick="revokeShareLink('${l.id}')">Revoke</button>
                </div>`;
        }).join('');
    } catch (e) {
        container.innerHTML = '<div style="color:#e53e3e;font-size:0.85rem;">Failed to load.</div>';
    }
}

async function revokeShareLink(linkId) {
    try {
        await authFetch(`/api/share/${linkId}`, { method: 'DELETE' });
        loadShareLinks();
    } catch (e) { /* ignore */ }
}

function copyText(text) {
    navigator.clipboard.writeText(text).catch(() => {});
}

/* ═══════════════════════════════════════
   Shared Project View
   ═══════════════════════════════════════ */
async function openSharedProject(linkId) {
    try {
        const res = await fetch(`/api/shared/${linkId}`);
        if (!res.ok) {
            alert('Share link not found or expired.');
            showHome();
            return;
        }
        const data = await res.json();
        currentProject = null;
        currentShareLink = { id: linkId, access_level: data.access_level, project_id: data.project.id };
        fileContentsCache = {};
        expandedFolders = new Set();
        liveEditor.readOnly = data.access_level === 'readonly';
        const titleSuffix = data.access_level === 'readonly' ? ' (readonly)' : ' (contributor)';
        const titleEl = document.getElementById('liveHeaderTitle');
        titleEl.textContent = data.project.title + titleSuffix;
        titleEl.classList.remove('editable');
        document.getElementById('liveSaveBtn').style.display = data.access_level === 'contributor' ? '' : 'none';
        document.getElementById('liveModeContainer').classList.add('active');
        document.body.style.overflow = 'hidden';

        // Load file tree for shared projects
        projectFiles = data.files || [];
        if (projectFiles.length > 0) {
            showFileTree(true);
            // Hide file management actions for shared projects
            document.querySelector('.file-tree-actions').style.display = 'none';
            renderFileTree();
            const mainFile = data.project.main_file || 'main.tex';
            const mainF = projectFiles.find(f => f.filename === mainFile);
            if (mainF) {
                await openFile(mainF.id);
            } else {
                await openFile(projectFiles[0].id);
            }
        } else {
            showFileTree(false);
            liveEditor.value = data.project.source || '';
            document.getElementById('editorPanelLabel').textContent = 'LaTeX Source';
        }

        resetLivePreview();
    } catch (e) {
        alert('Failed to load shared project.');
        showHome();
    }
}

/* ═══════════════════════════════════════
   Upload Mode
   ═══════════════════════════════════════ */
const uploadArea = document.getElementById('uploadArea');
const fileInput = document.getElementById('fileInput');
const loading = document.getElementById('loading');
const result = document.getElementById('result');
const fileSelected = document.getElementById('fileSelected');
const selectedFileName = document.getElementById('selectedFileName');
const uploadText = document.getElementById('uploadText');
const uploadHint = document.getElementById('uploadHint');

uploadArea.addEventListener('dragover', (e) => {
    e.preventDefault();
    uploadArea.classList.add('dragover');
});

uploadArea.addEventListener('dragleave', () => {
    uploadArea.classList.remove('dragover');
});

uploadArea.addEventListener('drop', (e) => {
    e.preventDefault();
    uploadArea.classList.remove('dragover');
    const files = e.dataTransfer.files;
    if (files.length > 0) handleFile(files[0]);
});

uploadArea.addEventListener('click', (e) => {
    if (e.target !== fileInput) fileInput.click();
});

fileInput.addEventListener('change', (e) => {
    if (e.target.files.length > 0) handleFile(e.target.files[0]);
});

function handleFile(file) {
    if (!file.name.endsWith('.zip')) {
        showError('Please select a ZIP file containing your LaTeX project.');
        return;
    }
    selectedFileName.textContent = file.name;
    fileSelected.style.display = 'block';
    uploadText.textContent = 'File uploaded, starting compilation...';
    uploadHint.textContent = 'Please wait while we compile your LaTeX project';
    uploadFile(file);
}

/* ── Progress bar controller ── */
const PROGRESS_STAGES = [
    { icon: '\u{1F4E6}', doneIcon: '\u2705', pct: 10,  label: 'Extracting ZIP file' },
    { icon: '\u{1F50D}', doneIcon: '\u2705', pct: 20,  label: 'Detecting LaTeX entry point' },
    { icon: '\u2699\uFE0F', doneIcon: '\u2705', pct: 85,  label: 'Compiling with latexmk' },
    { icon: '\u{1F4C4}', doneIcon: '\u2705', pct: 100, label: 'Generating PDF' },
];
let progressTimer = null;
let progressStart = 0;
const ESTIMATED_SECONDS = 15;

function startProgress() {
    progressStart = Date.now();
    setProgressUI(0, -1);
    progressTimer = setInterval(tickProgress, 300);
}

function tickProgress() {
    const elapsed = (Date.now() - progressStart) / 1000;
    // Ease-out curve: fast at start, slows approaching 95%
    const ratio = Math.min(elapsed / ESTIMATED_SECONDS, 1);
    const pct = Math.min(95, Math.round(ratio * 100 * (1 - 0.3 * ratio)));

    // Determine current stage based on which threshold we've passed
    let stageIdx = 0;
    for (let i = PROGRESS_STAGES.length - 1; i >= 0; i--) {
        if (pct >= (i === 0 ? 0 : PROGRESS_STAGES[i - 1].pct)) { stageIdx = i; break; }
    }

    setProgressUI(pct, stageIdx);

    const remaining = Math.max(0, Math.round(ESTIMATED_SECONDS - elapsed));
    const timeEl = document.getElementById('progressTime');
    if (remaining > 0) {
        timeEl.textContent = `Estimated time remaining: ~${remaining}s`;
    } else {
        timeEl.textContent = 'Almost done, finalizing...';
    }
}

function setProgressUI(pct, activeStageIdx) {
    document.getElementById('progressBarFill').style.width = pct + '%';
    document.getElementById('progressBarLabel').textContent = pct + '%';

    const stageEl = document.getElementById('progressStage');
    if (activeStageIdx >= 0 && activeStageIdx < PROGRESS_STAGES.length) {
        stageEl.textContent = PROGRESS_STAGES[activeStageIdx].label + '...';
    } else {
        stageEl.textContent = 'Preparing...';
    }

    for (let i = 0; i < PROGRESS_STAGES.length; i++) {
        const step = document.getElementById('pStep' + i);
        const icon = document.getElementById('pIcon' + i);
        step.classList.remove('active', 'done');
        if (i < activeStageIdx) {
            step.classList.add('done');
            icon.textContent = PROGRESS_STAGES[i].doneIcon;
        } else if (i === activeStageIdx) {
            step.classList.add('active');
            icon.textContent = PROGRESS_STAGES[i].icon;
        } else {
            icon.textContent = PROGRESS_STAGES[i].icon;
        }
    }
}

function finishProgress() {
    clearInterval(progressTimer);
    progressTimer = null;
    setProgressUI(100, PROGRESS_STAGES.length);
    // Mark all as done
    for (let i = 0; i < PROGRESS_STAGES.length; i++) {
        const step = document.getElementById('pStep' + i);
        const icon = document.getElementById('pIcon' + i);
        step.classList.remove('active');
        step.classList.add('done');
        icon.textContent = PROGRESS_STAGES[i].doneIcon;
    }
    document.getElementById('progressStage').textContent = 'Done!';
    document.getElementById('progressTime').textContent = '';
}

function resetProgress() {
    clearInterval(progressTimer);
    progressTimer = null;
    setProgressUI(0, -1);
    document.getElementById('progressTime').textContent = '';
    // Reset icons
    for (let i = 0; i < PROGRESS_STAGES.length; i++) {
        const step = document.getElementById('pStep' + i);
        const icon = document.getElementById('pIcon' + i);
        step.classList.remove('active', 'done');
        icon.textContent = PROGRESS_STAGES[i].icon;
    }
}

async function uploadFile(file) {
    const formData = new FormData();
    formData.append('project', file);
    formData.append('engine', 'latexmk');
    formData.append('runs', '3');

    loading.style.display = 'block';
    result.style.display = 'none';
    uploadText.textContent = 'Compilation in progress...';
    uploadHint.textContent = 'Please wait while we process your LaTeX project';
    fileInput.value = '';
    fileSelected.style.display = 'none';
    startProgress();

    try {
        const response = await fetch('/render', { method: 'POST', body: formData });
        finishProgress();
        if (response.ok) {
            const data = await response.json();
            if (data.success) {
                showSuccess(data);
            } else {
                showError(data.error || 'Compilation failed. Please check your LaTeX code.');
            }
        } else {
            let errorMessage = 'Compilation failed';
            try {
                const errorData = await response.json();
                errorMessage = errorData.error || errorData.detail || `HTTP ${response.status}: ${response.statusText}`;
            } catch (_) {
                errorMessage = `HTTP ${response.status}: ${response.statusText}`;
                if (response.status === 422) errorMessage += '. LaTeX compilation failed. Check your source code for errors.';
            }
            showError(errorMessage);
        }
    } catch (error) {
        showError('Network error occurred while processing your file. Please check your connection and try again.');
    } finally {
        resetProgress();
        loading.style.display = 'none';
    }
}

function showSuccess(data) {
    loading.style.display = 'none';
    uploadText.textContent = 'Drag & drop your ZIP file here';
    uploadHint.textContent = 'or click to browse';
    result.className = 'result';
    result.innerHTML = `
        <div class="success-icon">\u2705</div>
        <h3>Compilation Successful!</h3>
        <div class="file-info">
            <p><strong>File ID:</strong> ${data.file_id}</p>
            <p><strong>Filename:</strong> ${data.filename}</p>
            <p><strong>Size:</strong> ${(data.size_bytes / 1024).toFixed(1)} KB</p>
            <p><strong>Expires:</strong> ${new Date(data.expires_at).toLocaleString()}</p>
        </div>
        <div style="text-align:center;padding:40px 20px;background:#f8f9fa;border-radius:12px;border:2px dashed #dee2e6;margin:15px 0;">
            <div style="font-size:4rem;margin-bottom:20px;">\u{1F4C4}</div>
            <p style="margin:0 0 25px;color:#666;font-size:1.1rem;">Your LaTeX project has been compiled successfully.</p>
            <button class="btn" onclick="window.open('${data.download_url}', '_blank')" style="background:#28a745;">
                Open PDF in Browser
            </button>
        </div>
        <div class="action-buttons" style="margin-top:20px;">
            <button class="btn" onclick="window.open('${data.download_url}', '_blank')">Open in New Tab</button>
            <button class="btn" onclick="resetInterface()">Upload Another File</button>
        </div>
    `;
    result.style.display = 'block';
}

function showError(message) {
    loading.style.display = 'none';
    uploadText.textContent = 'Drag & drop your ZIP file here';
    uploadHint.textContent = 'or click to browse';
    result.className = 'result error';
    result.innerHTML = `
        <div class="error-icon">\u274C</div>
        <h3>Error</h3>
        <p>${message}</p>
        <div style="background:#fff3cd;border:1px solid #ffeaa7;border-radius:6px;padding:15px;margin:20px 0;text-align:left;">
            <h4 style="margin:0 0 10px;color:#856404;">Troubleshooting Tips:</h4>
            <ul style="margin:0;padding-left:20px;color:#856404;">
                <li>Ensure your ZIP file contains a valid LaTeX project with a main .tex file</li>
                <li>Check that your LaTeX code compiles without errors</li>
                <li>Verify the ZIP file is not corrupted</li>
            </ul>
        </div>
        <div style="text-align:center;margin-top:20px;">
            <button class="btn" onclick="resetInterface()">Try Another File</button>
        </div>
    `;
    result.style.display = 'block';
}

function resetInterface() {
    result.style.display = 'none';
    loading.style.display = 'none';
    fileSelected.style.display = 'none';
    uploadText.textContent = 'Drag & drop your ZIP file here';
    uploadHint.textContent = 'or click to browse';
    fileInput.value = '';
    resetProgress();
}

/* ═══════════════════════════════════════
   Live Mode
   ═══════════════════════════════════════ */
const DEFAULT_TEX = `\\documentclass{article}
\\usepackage{amsmath}

\\title{My Document}
\\author{Author}
\\date{\\today}

\\begin{document}
\\maketitle

\\section{Introduction}
Hello, \\LaTeX! This is a live preview.

\\section{Math Example}
The quadratic formula is:
\\[
  x = \\frac{-b \\pm \\sqrt{b^2 - 4ac}}{2a}
\\]

\\section{Lists}
\\begin{itemize}
  \\item First item
  \\item Second item
  \\item Third item
\\end{itemize}

\\end{document}`;

const liveEditor     = document.getElementById('liveEditor');
const liveStatus     = document.getElementById('liveStatus');
const pdfViewerContainer = document.getElementById('pdfViewerContainer');
const livePdfPlaceholder = document.getElementById('livePdfPlaceholder');
const liveErrorPanel = document.getElementById('liveErrorPanel');

let liveDebounceTimer = null;
let liveRendering     = false;

// pdf.js + SyncTeX state
let pdfDoc = null;
let synctexData = null;
let pdfPageCanvases = [];  // [{canvas, pageNum, viewport, wrapper}]
let pdfScale = 1.5;
let currentProject    = null;    // set when editing an owned project
let currentShareLink  = null;    // set when editing via share link
let autoSaveTimer     = null;
let lastSavedSource   = '';

// Multi-file state
let projectFiles = [];        // [{id, filename, updated_at}]
let activeFileId = null;
let fileContentsCache = {};   // {file_id: content}
let contextMenuFileId = null;

function isMultiFileMode() {
    return currentProject || currentShareLink;
}

function showFileTree(show) {
    document.getElementById('liveFileTree').style.display = show ? '' : 'none';
    document.getElementById('liveTreeDivider').style.display = show ? '' : 'none';
}

function enterLiveMode() {
    currentProject = null;
    currentShareLink = null;
    liveEditor.readOnly = false;
    document.getElementById('liveHeaderTitle').textContent = 'LaTeX Live Mode';
    document.getElementById('liveHeaderTitle').classList.remove('editable');
    document.getElementById('liveSaveBtn').style.display = 'none';
    showFileTree(false);
    projectFiles = [];
    activeFileId = null;
    fileContentsCache = {};
    expandedFolders = new Set();
    document.getElementById('editorPanelLabel').textContent = 'LaTeX Source';
    if (!liveEditor.value) {
        liveEditor.value = DEFAULT_TEX;
    }
    document.getElementById('liveModeContainer').classList.add('active');
    document.body.style.overflow = 'hidden';
    liveEditor.focus();
}

function exitLiveMode() {
    const path = window.location.pathname;
    if (path.startsWith('/shared/') || path.startsWith('/projects/')) {
        navigateTo('/projects');
    } else {
        closeLiveModeQuiet();
    }
}

function resetLivePreview() {
    livePdfPlaceholder.style.display = '';
    pdfViewerContainer.style.display = 'none';
    liveErrorPanel.style.display = 'none';
    document.getElementById('pdfLoadingOverlay').style.display = 'none';
    document.getElementById('pdfRenderProgress').style.display = 'none';
    pdfDoc = null;
    synctexData = null;
    pdfPageCanvases = [];
    pdfViewerContainer.innerHTML = '';
    lastPdfBytes = null;
    pdfUserZoom = 1.0;
    pdfBaseScale = null;
    clearTimeout(zoomRenderTimer);
    navScrolling = false;
    setLiveStatus('ready', 'Ready');
    lastSavedSource = liveEditor.value;
    startAutoSave();
    document.getElementById('pdfPageInfo').textContent = '0 / 0';
    document.getElementById('pdfZoomInfo').textContent = '100%';
}

function startAutoSave() {
    clearInterval(autoSaveTimer);
    if (currentProject || (currentShareLink && currentShareLink.access_level === 'contributor')) {
        autoSaveTimer = setInterval(() => {
            if (liveEditor.value !== lastSavedSource) saveProject();
        }, 30000);
    }
}

function setLiveStatus(state, text) {
    liveStatus.className = `live-status ${state}`;
    liveStatus.textContent = text;
}

async function saveProject() {
    // Don't save binary files
    const activeMeta = activeFileId ? projectFiles.find(f => f.id === activeFileId) : null;
    if (activeMeta && activeMeta.is_binary) return;
    if (activeFileId && isMultiFileMode()) {
        // Save active file
        const content = liveEditor.value;
        fileContentsCache[activeFileId] = content;
        try {
            if (currentProject) {
                await authFetch(`/api/projects/${currentProject.id}/files/${activeFileId}`, {
                    method: 'PUT',
                    body: JSON.stringify({ content }),
                });
            } else if (currentShareLink && currentShareLink.access_level === 'contributor') {
                await fetch(`/api/shared/${currentShareLink.id}/files/${activeFileId}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ content }),
                });
            }
            lastSavedSource = content;
            setLiveStatus('saved', 'Saved');
            setTimeout(() => {
                if (liveStatus.textContent === 'Saved') setLiveStatus('ready', 'Ready');
            }, 2000);
        } catch (e) {
            setLiveStatus('error', 'Save failed');
        }
    } else {
        // Legacy single-file save
        const source = liveEditor.value;
        try {
            if (currentProject) {
                await authFetch(`/api/projects/${currentProject.id}`, {
                    method: 'PUT',
                    body: JSON.stringify({ source }),
                });
            } else if (currentShareLink && currentShareLink.access_level === 'contributor') {
                await fetch(`/api/shared/${currentShareLink.id}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ source }),
                });
            }
            lastSavedSource = source;
            setLiveStatus('saved', 'Saved');
            setTimeout(() => {
                if (liveStatus.textContent === 'Saved') setLiveStatus('ready', 'Ready');
            }, 2000);
        } catch (e) {
            setLiveStatus('error', 'Save failed');
        }
    }
}

/* ── Render progress bar (right panel) ── */
let renderProgressTimer = null;
let renderProgressStart = 0;
let renderEstimateSec = 12; // default, updated from past timing data

// Stages with fractional positions based on typical compile vs postprocess ratio
// These get adjusted dynamically when we have real timing data
let renderStageBreakpoints = {
    compilePct: 65,  // % of time spent in compilation (default guess)
};

const RENDER_STAGES = [
    {pct: 0,  label: 'Saving files...'},
    {pct: 8,  label: 'Compiling LaTeX...'},
    {pct: 70, label: 'Processing SyncTeX & encoding...'},
    {pct: 95, label: 'Transferring...'},
];

function getRenderTimingKey() {
    if (currentProject) return 'render_timing_' + currentProject.id;
    if (currentShareLink) return 'render_timing_shared_' + currentShareLink.id;
    return 'render_timing_live';
}

function loadRenderEstimate() {
    try {
        const saved = localStorage.getItem(getRenderTimingKey());
        if (saved) {
            const timing = JSON.parse(saved);
            // Use the last total time, with a small buffer
            renderEstimateSec = Math.max(5, timing.total * 1.1);
            // Adjust stage breakpoints based on compile vs postprocess ratio
            if (timing.compile && timing.total) {
                const compileFrac = timing.compile / timing.total;
                RENDER_STAGES[2].pct = Math.round(8 + compileFrac * 87); // compile ends here
            }
        } else {
            renderEstimateSec = 12; // default for first compile
            RENDER_STAGES[2].pct = 70;
        }
    } catch (e) {
        renderEstimateSec = 12;
    }
}

function saveRenderTiming(timing) {
    if (!timing) return;
    try {
        localStorage.setItem(getRenderTimingKey(), JSON.stringify(timing));
    } catch (e) { /* ignore */ }
}

function showRenderProgress() {
    loadRenderEstimate();
    renderProgressStart = Date.now();
    const el = document.getElementById('pdfRenderProgress');
    el.style.display = '';
    document.getElementById('pdfRenderProgressFill').style.width = '0%';
    document.getElementById('pdfRenderStage').textContent = RENDER_STAGES[0].label;
    document.getElementById('pdfRenderTime').textContent = `~${Math.round(renderEstimateSec)}s`;
    renderProgressTimer = setInterval(tickRenderProgress, 300);
}

function tickRenderProgress() {
    const elapsed = (Date.now() - renderProgressStart) / 1000;
    const ratio = Math.min(elapsed / renderEstimateSec, 1);
    // Ease-out curve that slows down as it approaches 95%
    const pct = Math.min(95, Math.round(ratio * 100 * (1 - 0.3 * ratio)));

    document.getElementById('pdfRenderProgressFill').style.width = pct + '%';

    // Pick stage label
    let stage = RENDER_STAGES[0].label;
    for (let i = RENDER_STAGES.length - 1; i >= 0; i--) {
        if (pct >= RENDER_STAGES[i].pct) { stage = RENDER_STAGES[i].label; break; }
    }
    document.getElementById('pdfRenderStage').textContent = stage;

    const remaining = Math.max(0, Math.round(renderEstimateSec - elapsed));
    document.getElementById('pdfRenderTime').textContent = remaining > 0 ? `~${remaining}s` : 'almost done...';
}

function hideRenderProgress() {
    clearInterval(renderProgressTimer);
    renderProgressTimer = null;
    const el = document.getElementById('pdfRenderProgress');
    document.getElementById('pdfRenderProgressFill').style.width = '100%';
    document.getElementById('pdfRenderStage').textContent = 'Done';
    document.getElementById('pdfRenderTime').textContent = '';
    setTimeout(() => { el.style.display = 'none'; }, 400);
}

async function liveRender() {
    if (liveRendering) return;
    liveRendering = true;
    setLiveStatus('compiling', 'Compiling\u2026');
    showRenderProgress();

    try {
        let response;
        if (isMultiFileMode() && projectFiles.length > 0) {
            // Save current file first
            if (activeFileId) {
                fileContentsCache[activeFileId] = liveEditor.value;
                if (currentProject) {
                    await authFetch(`/api/projects/${currentProject.id}/files/${activeFileId}`, {
                        method: 'PUT',
                        body: JSON.stringify({ content: liveEditor.value }),
                    });
                } else if (currentShareLink && currentShareLink.access_level === 'contributor') {
                    await fetch(`/api/shared/${currentShareLink.id}/files/${activeFileId}`, {
                        method: 'PUT',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ content: liveEditor.value }),
                    });
                }
                lastSavedSource = liveEditor.value;
            }
            // Render via multi-file endpoint
            if (currentProject) {
                response = await authFetch(`/api/projects/${currentProject.id}/render`, { method: 'POST' });
            } else if (currentShareLink) {
                response = await fetch(`/api/shared/${currentShareLink.id}/render`, { method: 'POST' });
            }
        } else {
            // Single-file render
            const source = liveEditor.value.trim();
            if (!source) { liveRendering = false; hideRenderProgress(); return; }
            const formData = new FormData();
            formData.append('source', source);
            formData.append('runs', '3');
            response = await fetch('/render-source', { method: 'POST', body: formData });
        }

        if (response.ok) {
            const data = await response.json();
            if (data.pdf_base64) {
                // Save server timing for future estimates
                if (data.timing) saveRenderTiming(data.timing);

                const pdfBytes = Uint8Array.from(atob(data.pdf_base64), c => c.charCodeAt(0));
                synctexData = data.synctex || null;

                livePdfPlaceholder.style.display = 'none';
                liveErrorPanel.style.display = 'none';
                pdfViewerContainer.style.display = 'block';

                await renderPdfPages(pdfBytes);
                setLiveStatus('ready', 'Ready');
            } else if (data.error) {
                let errText = data.error;
                if (data.log) errText += '\n\n' + data.log;
                showLiveError(errText);
            }
        } else {
            let errText = `HTTP ${response.status}`;
            try {
                const errData = await response.json();
                errText = errData.error || errText;
                if (errData.log) errText += '\n\n' + errData.log;
            } catch (_) {}
            showLiveError(errText);
        }
    } catch (err) {
        showLiveError('Network error: ' + err.message);
    } finally {
        hideRenderProgress();
        liveRendering = false;
    }
}

function showLiveError(message) {
    livePdfPlaceholder.style.display = 'none';
    pdfViewerContainer.style.display = 'none';
    liveErrorPanel.style.display = 'block';
    liveErrorPanel.textContent = message;
    setLiveStatus('error', 'Error');
}

/* ═══════════════════════════════════════
   pdf.js Rendering + SyncTeX
   ═══════════════════════════════════════ */
async function renderPdfPages(pdfBytes) {
    // Store for download
    lastPdfBytes = pdfBytes;

    // Preserve scroll position
    const prevScroll = pdfViewerContainer.scrollTop;
    const hadContent = pdfPageCanvases.length > 0;

    // Load PDF
    const loadingTask = pdfjsLib.getDocument({data: pdfBytes});
    pdfDoc = await loadingTask.promise;

    // Compute base scale to fit container width (= 100% zoom)
    const containerWidth = pdfViewerContainer.clientWidth - 24; // padding
    const firstPage = await pdfDoc.getPage(1);
    const unscaledViewport = firstPage.getViewport({scale: 1});
    pdfBaseScale = containerWidth / unscaledViewport.width;
    if (pdfBaseScale < 0.3) pdfBaseScale = 0.3;
    if (pdfBaseScale > 5) pdfBaseScale = 5;

    // Apply user zoom on top of base scale
    pdfScale = pdfBaseScale * pdfUserZoom;

    pdfViewerContainer.innerHTML = '';
    pdfPageCanvases = [];

    for (let i = 1; i <= pdfDoc.numPages; i++) {
        const page = await pdfDoc.getPage(i);
        const viewport = page.getViewport({scale: pdfScale});

        const wrapper = document.createElement('div');
        wrapper.className = 'pdf-page-wrapper';
        wrapper.style.width = viewport.width + 'px';
        wrapper.style.height = viewport.height + 'px';
        wrapper.dataset.pageNum = i;

        const canvas = document.createElement('canvas');
        canvas.width = viewport.width * (window.devicePixelRatio || 1);
        canvas.height = viewport.height * (window.devicePixelRatio || 1);
        canvas.style.width = viewport.width + 'px';
        canvas.style.height = viewport.height + 'px';
        if (synctexData) canvas.style.cursor = 'crosshair';

        const ctx = canvas.getContext('2d');
        ctx.scale(window.devicePixelRatio || 1, window.devicePixelRatio || 1);
        await page.render({canvasContext: ctx, viewport}).promise;

        wrapper.appendChild(canvas);
        pdfViewerContainer.appendChild(wrapper);

        pdfPageCanvases.push({canvas, pageNum: i, viewport, wrapper});

        // Inverse search: click on PDF → jump to editor
        const pageNum = i;
        canvas.addEventListener('dblclick', (e) => inverseSyncTexClick(e, pageNum, viewport, wrapper));
    }

    // Restore scroll position
    if (hadContent) {
        pdfViewerContainer.scrollTop = prevScroll;
    }

    // Update toolbar info
    updateZoomInfo();
    updatePageInfo();
}

/* ── Inverse Search: PDF click → Editor ── */
function inverseSyncTexClick(e, pageNum, viewport, wrapper) {
    if (!synctexData || !synctexData.inverse) return;

    const rect = wrapper.getBoundingClientRect();
    // Convert click Y to PDF points
    const clickY_css = e.clientY - rect.top;
    const y_pt = clickY_css / pdfScale;

    const records = synctexData.inverse[String(pageNum)];
    if (!records || records.length === 0) return;

    // Find closest record by y position
    let best = records[0];
    let bestDist = Math.abs(best.y - y_pt);
    for (const r of records) {
        const dist = Math.abs(r.y - y_pt);
        if (dist < bestDist) {
            bestDist = dist;
            best = r;
        }
    }

    scrollEditorToLine(best.file, best.line);
}

async function scrollEditorToLine(filename, lineNum) {
    // If multi-file and different file, switch to it first
    if (isMultiFileMode() && projectFiles.length > 0) {
        const targetFile = projectFiles.find(f => f.filename === filename);
        if (targetFile && targetFile.id !== activeFileId) {
            await openFile(targetFile.id);
        }
    }

    // Scroll textarea to line
    const text = liveEditor.value;
    const lines = text.split('\n');
    const targetLine = Math.max(1, Math.min(lineNum, lines.length));
    let charOffset = 0;
    for (let i = 0; i < targetLine - 1; i++) {
        charOffset += lines[i].length + 1;
    }
    const lineEnd = charOffset + (lines[targetLine - 1] || '').length;

    liveEditor.focus();
    liveEditor.setSelectionRange(charOffset, lineEnd);

    // Scroll the textarea to make the line visible
    const lineHeight = parseFloat(getComputedStyle(liveEditor).lineHeight) || 18;
    const scrollTarget = (targetLine - 1) * lineHeight - liveEditor.clientHeight / 3;
    liveEditor.scrollTop = Math.max(0, scrollTarget);
}

/* ── Forward Search: Editor → PDF (Ctrl+Enter) ── */
function forwardSearch() {
    if (!synctexData || !synctexData.forward) return;

    const cursorPos = liveEditor.selectionStart;
    const textBefore = liveEditor.value.substring(0, cursorPos);
    const lineNum = textBefore.split('\n').length;

    let filename;
    if (isMultiFileMode() && activeFileId) {
        const f = projectFiles.find(f => f.id === activeFileId);
        filename = f ? f.filename : 'main.tex';
    } else {
        filename = 'main.tex';
    }

    const fileForward = synctexData.forward[filename];
    if (!fileForward) return;

    // Search for exact line, then nearby lines
    let records = fileForward[String(lineNum)];
    if (!records) {
        // Try nearby lines (up to 5 away)
        for (let delta = 1; delta <= 5; delta++) {
            records = fileForward[String(lineNum + delta)] || fileForward[String(lineNum - delta)];
            if (records) break;
        }
    }
    if (!records || records.length === 0) return;

    const target = records[0];
    scrollPdfToPosition(target.page, target.y);
}

function scrollPdfToPosition(pageNum, y_pt) {
    const pageEntry = pdfPageCanvases.find(p => p.pageNum === pageNum);
    if (!pageEntry) return;

    const wrapper = pageEntry.wrapper;
    const y_css = y_pt * pdfScale;

    // Scroll the container so the target y is visible
    const wrapperTop = wrapper.offsetTop;
    const targetScroll = wrapperTop + y_css - pdfViewerContainer.clientHeight / 3;
    pdfViewerContainer.scrollTo({top: Math.max(0, targetScroll), behavior: 'smooth'});

    // Flash highlight
    const highlight = document.createElement('div');
    highlight.className = 'synctex-highlight';
    highlight.style.top = y_css + 'px';
    wrapper.appendChild(highlight);
    setTimeout(() => { highlight.style.opacity = '0'; }, 100);
    setTimeout(() => { highlight.remove(); }, 1200);
}

/* ═══════════════════════════════════════
   PDF Toolbar: Zoom, Dark Mode, Page Nav, Download
   ═══════════════════════════════════════ */
let pdfDarkMode = false;
let pdfBaseScale = null;   // the "fit-to-width" scale, computed on render
let pdfUserZoom = 1.0;     // user zoom multiplier (1.0 = 100% = fit-to-width)
let lastPdfBytes = null;   // store last rendered PDF bytes for download
let zoomRenderTimer = null; // debounced quality re-render after zoom
let navScrolling = false;   // suppress page counter updates during smooth scroll

function updateZoomInfo() {
    const pct = Math.round(pdfUserZoom * 100);
    document.getElementById('pdfZoomInfo').textContent = pct + '%';
}

function updatePageInfo() {
    if (navScrolling) return;
    if (!pdfDoc) {
        document.getElementById('pdfPageInfo').textContent = '0 / 0';
        return;
    }
    const currentPage = getCurrentVisiblePage();
    document.getElementById('pdfPageInfo').textContent = currentPage + ' / ' + pdfDoc.numPages;
}

function getCurrentVisiblePage() {
    if (!pdfPageCanvases.length) return 0;
    const scrollTop = pdfViewerContainer.scrollTop;
    const containerMid = scrollTop + pdfViewerContainer.clientHeight / 3;
    let best = 1;
    for (const entry of pdfPageCanvases) {
        if (entry.wrapper.offsetTop <= containerMid) {
            best = entry.pageNum;
        }
    }
    return best;
}

// Update page info on scroll
pdfViewerContainer.addEventListener('scroll', updatePageInfo);

function pdfPageNav(direction) {
    if (!pdfDoc || !pdfPageCanvases.length) return;
    const current = getCurrentVisiblePage();
    const target = Math.max(1, Math.min(pdfDoc.numPages, current + direction));
    if (target === current) return;
    const entry = pdfPageCanvases.find(p => p.pageNum === target);
    if (entry) {
        // Show target page immediately, suppress scroll-based updates during animation
        navScrolling = true;
        document.getElementById('pdfPageInfo').textContent = target + ' / ' + pdfDoc.numPages;
        pdfViewerContainer.scrollTo({top: entry.wrapper.offsetTop - 4, behavior: 'smooth'});
        setTimeout(() => { navScrolling = false; }, 600);
    }
}

// mouseX/mouseY are optional — relative to the pdfViewerContainer.
// When provided, zoom anchors to that point (the document under the cursor stays put).
function pdfZoom(direction, mouseX, mouseY) {
    if (!pdfDoc || !pdfPageCanvases.length) return;
    const step = 0.1;
    const oldZoom = pdfUserZoom;
    pdfUserZoom = Math.max(0.25, Math.min(5.0, pdfUserZoom + direction * step));
    if (oldZoom === pdfUserZoom) return;

    const ratio = pdfUserZoom / oldZoom;

    // Record the document point under the mouse (or center of viewport as fallback)
    const anchorX = mouseX != null ? mouseX : pdfViewerContainer.clientWidth / 2;
    const anchorY = mouseY != null ? mouseY : pdfViewerContainer.clientHeight / 2;
    const docX = pdfViewerContainer.scrollLeft + anchorX;
    const docY = pdfViewerContainer.scrollTop + anchorY;

    // Instantly resize all canvases via CSS (no re-render, no DOM rebuild)
    for (const pe of pdfPageCanvases) {
        const w = parseFloat(pe.canvas.style.width) * ratio;
        const h = parseFloat(pe.canvas.style.height) * ratio;
        pe.wrapper.style.width = w + 'px';
        pe.wrapper.style.height = h + 'px';
        pe.canvas.style.width = w + 'px';
        pe.canvas.style.height = h + 'px';
    }

    pdfScale = pdfBaseScale * pdfUserZoom;

    // After resize, the same document point is now at docX*ratio, docY*ratio.
    // Scroll so it stays under the mouse cursor.
    pdfViewerContainer.scrollLeft = docX * ratio - anchorX;
    pdfViewerContainer.scrollTop = docY * ratio - anchorY;

    updateZoomInfo();
    updatePageInfo();

    // Debounced quality re-render at new resolution
    clearTimeout(zoomRenderTimer);
    zoomRenderTimer = setTimeout(() => qualityReRender(), 350);
}

// Re-render canvases at current pdfScale for sharp text after zoom.
// Renders to offscreen canvases first, then swaps them in to avoid black flash.
async function qualityReRender() {
    if (!pdfDoc) return;
    const targetScale = pdfScale; // snapshot — may change if user keeps zooming

    for (const pe of pdfPageCanvases) {
        // Bail if zoom changed while we were rendering (user zoomed again)
        if (pdfScale !== targetScale) return;

        const page = await pdfDoc.getPage(pe.pageNum);
        const viewport = page.getViewport({scale: targetScale});
        const dpr = window.devicePixelRatio || 1;

        // Render to an offscreen canvas
        const offscreen = document.createElement('canvas');
        offscreen.width = viewport.width * dpr;
        offscreen.height = viewport.height * dpr;
        offscreen.style.width = viewport.width + 'px';
        offscreen.style.height = viewport.height + 'px';
        const ctx = offscreen.getContext('2d');
        ctx.scale(dpr, dpr);
        await page.render({canvasContext: ctx, viewport}).promise;

        // Bail if zoom changed during render
        if (pdfScale !== targetScale) return;

        // Swap: copy event listeners by replacing in-place
        offscreen.style.cursor = pe.canvas.style.cursor;
        const pageNum = pe.pageNum;
        offscreen.addEventListener('dblclick', (e) => inverseSyncTexClick(e, pageNum, viewport, pe.wrapper));
        pe.wrapper.replaceChild(offscreen, pe.canvas);
        pe.canvas = offscreen;
        pe.viewport = viewport;

        pe.wrapper.style.width = viewport.width + 'px';
        pe.wrapper.style.height = viewport.height + 'px';
    }
}

// Ctrl+scroll wheel zoom — anchored to mouse position
pdfViewerContainer.addEventListener('wheel', (e) => {
    if (e.ctrlKey || e.metaKey) {
        e.preventDefault();
        const direction = e.deltaY < 0 ? 1 : -1;
        const rect = pdfViewerContainer.getBoundingClientRect();
        const mouseX = e.clientX - rect.left;
        const mouseY = e.clientY - rect.top;
        pdfZoom(direction, mouseX, mouseY);
    }
}, {passive: false});

function togglePdfDarkMode() {
    pdfDarkMode = !pdfDarkMode;
    const panel = document.getElementById('livePdfPanel');
    panel.classList.toggle('pdf-dark-mode', pdfDarkMode);
}

function downloadCurrentPdf() {
    if (!lastPdfBytes) return;
    const blob = new Blob([lastPdfBytes], {type: 'application/pdf'});
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    const title = currentProject ? currentProject.title : 'document';
    a.download = title + '.pdf';
    a.click();
    URL.revokeObjectURL(url);
}

liveEditor.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        e.preventDefault();
        forwardSearch();
    }
});

// Debounced auto-render on input (1.5 s delay)
liveEditor.addEventListener('input', () => {
    clearTimeout(liveDebounceTimer);
    setLiveStatus('compiling', 'Waiting\u2026');
    liveDebounceTimer = setTimeout(liveRender, 1500);
});

/* ═══════════════════════════════════════
   File Tree
   ═══════════════════════════════════════ */
async function loadFileTree(projectId) {
    try {
        let files;
        if (currentProject) {
            const res = await authFetch(`/api/projects/${projectId}/files`);
            files = await res.json();
        } else if (currentShareLink) {
            const res = await fetch(`/api/shared/${currentShareLink.id}`);
            const data = await res.json();
            files = data.files || [];
        }
        projectFiles = files || [];
        renderFileTree();
    } catch (e) {
        console.error('Failed to load file tree:', e);
    }
}

// Track which folders are expanded (all start collapsed)
let expandedFolders = new Set();

function toggleFolder(folderPath) {
    if (expandedFolders.has(folderPath)) {
        expandedFolders.delete(folderPath);
    } else {
        expandedFolders.add(folderPath);
    }
    renderFileTree();
}

function buildFolderTree(files) {
    // Build a nested structure: { __files__: [...], subfolder: { __files__: [...], ... } }
    const root = { __files__: [] };
    for (const f of files) {
        const parts = f.filename.split('/');
        if (parts.length === 1) {
            root.__files__.push(f);
        } else {
            let node = root;
            for (let i = 0; i < parts.length - 1; i++) {
                const dir = parts[i];
                if (!node[dir]) node[dir] = { __files__: [] };
                node = node[dir];
            }
            node.__files__.push(f);
        }
    }
    return root;
}

function renderFolderNode(node, path, depth, mainFile) {
    let html = '';
    // Sort: folders first (alphabetical), then files (alphabetical)
    const folderNames = Object.keys(node).filter(k => k !== '__files__').sort();
    const files = (node.__files__ || []).slice().sort((a, b) => {
        const nameA = a.filename.split('/').pop();
        const nameB = b.filename.split('/').pop();
        return nameA.localeCompare(nameB);
    });

    // Render subfolders
    for (const dir of folderNames) {
        const folderPath = path ? path + '/' + dir : dir;
        const isCollapsed = !expandedFolders.has(folderPath);
        html += `<li class="file-tree-folder${isCollapsed ? ' collapsed' : ''}">
            <div class="file-tree-folder-header" style="padding-left:${12 + depth * 16}px" onclick="toggleFolder('${escHtml(folderPath)}')">
                <span class="file-tree-folder-arrow">&#x25BC;</span>
                <span class="file-tree-icon">&#x1F4C1;</span>
                <span class="file-tree-folder-name">${escHtml(dir)}</span>
            </div>
            <ul class="file-tree-folder-children" style="list-style:none;padding:0;margin:0;">
                ${renderFolderNode(node[dir], folderPath, depth + 1, mainFile)}
            </ul>
        </li>`;
    }

    // Render files
    for (const f of files) {
        const isActive = f.id === activeFileId;
        const isMain = f.filename === mainFile;
        const displayName = f.filename.split('/').pop();
        const ext = displayName.split('.').pop().toLowerCase();
        const isBin = f.is_binary;
        const icon = isBin ? '&#x1F5BC;' : ext === 'tex' ? '&#x1F4C4;' : ext === 'bib' ? '&#x1F4DA;' : ext === 'cls' || ext === 'sty' ? '&#x2699;' : '&#x1F4C3;';
        const padLeft = 12 + depth * 16 + (isActive ? -2 : 0);
        html += `<li class="file-tree-item${isActive ? ' active' : ''}${isMain ? ' main-file' : ''}"
            style="padding-left:${padLeft}px"
            data-file-id="${f.id}" data-filename="${escHtml(f.filename)}"
            onclick="openFile('${f.id}')"
            oncontextmenu="showFileContextMenu(event, '${f.id}')">
            <span class="file-tree-icon">${icon}</span>
            <span class="file-tree-name">${escHtml(displayName)}</span>
        </li>`;
    }

    return html;
}

function renderFileTree() {
    const list = document.getElementById('fileTreeList');
    const mainFile = currentProject?.main_file || 'main.tex';

    if (projectFiles.length === 0) {
        list.innerHTML = '<li style="padding:12px;color:#555;font-size:0.8rem;text-align:center;">No files</li>';
        return;
    }

    const tree = buildFolderTree(projectFiles);
    list.innerHTML = renderFolderNode(tree, '', 0, mainFile);
}

async function openFile(fileId) {
    // Save current file to cache (skip binary files)
    const prevFile = activeFileId ? projectFiles.find(f => f.id === activeFileId) : null;
    if (activeFileId && activeFileId !== fileId && !(prevFile && prevFile.is_binary)) {
        fileContentsCache[activeFileId] = liveEditor.value;
        // Auto-save previous file
        if (liveEditor.value !== lastSavedSource) {
            try {
                if (currentProject) {
                    await authFetch(`/api/projects/${currentProject.id}/files/${activeFileId}`, {
                        method: 'PUT',
                        body: JSON.stringify({ content: liveEditor.value }),
                    });
                } else if (currentShareLink && currentShareLink.access_level === 'contributor') {
                    await fetch(`/api/shared/${currentShareLink.id}/files/${activeFileId}`, {
                        method: 'PUT',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ content: liveEditor.value }),
                    });
                }
            } catch(e) { /* ignore */ }
        }
    }

    activeFileId = fileId;
    renderFileTree();

    // Get content from cache or fetch
    if (fileContentsCache[fileId] !== undefined) {
        liveEditor.value = fileContentsCache[fileId];
        lastSavedSource = fileContentsCache[fileId];
    } else {
        try {
            let f;
            if (currentProject) {
                const res = await authFetch(`/api/projects/${currentProject.id}/files/${fileId}`);
                f = await res.json();
            } else if (currentShareLink) {
                const res = await fetch(`/api/shared/${currentShareLink.id}/files/${fileId}`);
                f = await res.json();
            }
            fileContentsCache[fileId] = f.content;
            liveEditor.value = f.content;
            lastSavedSource = f.content;
        } catch (e) {
            liveEditor.value = '% Error loading file';
        }
    }

    // Update label and handle binary files
    const fmeta = projectFiles.find(f => f.id === fileId);
    const fname = fmeta?.filename || 'Unknown';
    const displayName = fname.includes('/') ? fname.split('/').pop() : fname;
    document.getElementById('editorPanelLabel').textContent = displayName;
    const overlay = document.getElementById('imagePreviewOverlay');
    if (fmeta && fmeta.is_binary) {
        const ext = displayName.split('.').pop().toLowerCase();
        const imageExts = ['png', 'jpg', 'jpeg', 'gif', 'bmp', 'svg', 'webp'];
        if (imageExts.includes(ext)) {
            // Show image preview
            const mimeMap = {png:'image/png', jpg:'image/jpeg', jpeg:'image/jpeg', gif:'image/gif', bmp:'image/bmp', svg:'image/svg+xml', webp:'image/webp'};
            const mime = mimeMap[ext] || 'image/png';
            const content = fileContentsCache[fileId];
            document.getElementById('imagePreviewImg').src = `data:${mime};base64,${content}`;
            document.getElementById('imagePreviewName').textContent = displayName;
            // Estimate file size from base64 length
            const sizeBytes = Math.round((content || '').length * 3 / 4);
            const sizeStr = sizeBytes > 1024*1024 ? (sizeBytes/1024/1024).toFixed(1)+' MB' : sizeBytes > 1024 ? (sizeBytes/1024).toFixed(1)+' KB' : sizeBytes+' B';
            document.getElementById('imagePreviewSize').textContent = sizeStr;
            overlay.style.display = 'block';
            liveEditor.style.display = 'none';
        } else {
            overlay.style.display = 'none';
            liveEditor.style.display = '';
            liveEditor.value = `[Binary file: ${displayName}]\n\nThis file cannot be edited in the text editor.`;
        }
        liveEditor.readOnly = true;
    } else {
        overlay.style.display = 'none';
        liveEditor.style.display = '';
        if (currentProject) liveEditor.readOnly = false;
        liveEditor.focus();
    }
}

function startNewFile() {
    const list = document.getElementById('fileTreeList');
    // Add input at the end
    const li = document.createElement('li');
    li.style.padding = '4px 8px';
    const input = document.createElement('input');
    input.className = 'file-tree-new-input';
    input.placeholder = 'filename.tex';
    input.style.margin = '0';
    li.appendChild(input);
    list.appendChild(li);
    input.focus();

    async function create() {
        const filename = input.value.trim();
        li.remove();
        if (!filename) return;
        try {
            if (currentProject) {
                const res = await authFetch(`/api/projects/${currentProject.id}/files`, {
                    method: 'POST',
                    body: JSON.stringify({ filename, content: '' }),
                });
                if (res.ok) {
                    const f = await res.json();
                    projectFiles.push({ id: f.id, filename: f.filename, updated_at: f.updated_at });
                    fileContentsCache[f.id] = '';
                    renderFileTree();
                    openFile(f.id);
                } else {
                    const err = await res.json();
                    alert(err.detail || 'Failed to create file');
                }
            }
        } catch(e) { /* ignore */ }
    }

    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') { e.preventDefault(); create(); }
        if (e.key === 'Escape') li.remove();
    });
    input.addEventListener('blur', create);
}

// Context menu
function showFileContextMenu(e, fileId) {
    e.preventDefault();
    e.stopPropagation();
    contextMenuFileId = fileId;
    const menu = document.getElementById('fileContextMenu');
    menu.style.left = e.clientX + 'px';
    menu.style.top = e.clientY + 'px';
    menu.classList.add('active');
}

document.addEventListener('click', () => {
    document.getElementById('fileContextMenu').classList.remove('active');
});

function contextRenameFile() {
    if (!contextMenuFileId) return;
    const item = document.querySelector(`.file-tree-item[data-file-id="${contextMenuFileId}"]`);
    if (!item) return;
    const nameEl = item.querySelector('.file-tree-name');
    const oldDisplayName = nameEl.textContent;
    const pf = projectFiles.find(f => f.id === contextMenuFileId);
    const oldFullPath = pf ? pf.filename : oldDisplayName;
    const folderPrefix = oldFullPath.includes('/') ? oldFullPath.substring(0, oldFullPath.lastIndexOf('/') + 1) : '';
    const input = document.createElement('input');
    input.className = 'file-tree-rename-input';
    input.value = oldDisplayName;
    nameEl.replaceWith(input);
    input.focus();
    input.select();

    async function doRename() {
        const newBaseName = input.value.trim();
        const span = document.createElement('span');
        span.className = 'file-tree-name';
        if (!newBaseName || newBaseName === oldDisplayName) {
            span.textContent = oldDisplayName;
            input.replaceWith(span);
            return;
        }
        const newFullPath = folderPrefix + newBaseName;
        try {
            if (currentProject) {
                const res = await authFetch(`/api/projects/${currentProject.id}/files/${contextMenuFileId}`, {
                    method: 'PUT',
                    body: JSON.stringify({ filename: newFullPath }),
                });
                if (res.ok) {
                    if (pf) pf.filename = newFullPath;
                    span.textContent = newBaseName;
                    if (activeFileId === contextMenuFileId) {
                        document.getElementById('editorPanelLabel').textContent = newBaseName;
                    }
                } else {
                    const err = await res.json();
                    alert(err.detail || 'Rename failed');
                    span.textContent = oldDisplayName;
                }
            }
        } catch(e) {
            span.textContent = oldDisplayName;
        }
        input.replaceWith(span);
    }

    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') { e.preventDefault(); doRename(); }
        if (e.key === 'Escape') { input.value = oldName; doRename(); }
    });
    input.addEventListener('blur', doRename);
}

async function contextSetMainFile() {
    if (!contextMenuFileId || !currentProject) return;
    const pf = projectFiles.find(f => f.id === contextMenuFileId);
    if (!pf) return;
    try {
        await authFetch(`/api/projects/${currentProject.id}/main-file`, {
            method: 'PATCH',
            body: JSON.stringify({ main_file: pf.filename }),
        });
        currentProject.main_file = pf.filename;
        renderFileTree();
        setLiveStatus('saved', `Main file: ${pf.filename}`);
        setTimeout(() => setLiveStatus('ready', 'Ready'), 2000);
    } catch(e) { /* ignore */ }
}

async function contextDeleteFile() {
    if (!contextMenuFileId || !currentProject) return;
    const pf = projectFiles.find(f => f.id === contextMenuFileId);
    if (!pf) return;
    if (!confirm(`Delete "${pf.filename}"?`)) return;
    try {
        const res = await authFetch(`/api/projects/${currentProject.id}/files/${contextMenuFileId}`, {
            method: 'DELETE',
        });
        if (res.ok) {
            projectFiles = projectFiles.filter(f => f.id !== contextMenuFileId);
            delete fileContentsCache[contextMenuFileId];
            if (activeFileId === contextMenuFileId) {
                activeFileId = null;
                if (projectFiles.length > 0) {
                    openFile(projectFiles[0].id);
                } else {
                    liveEditor.value = '';
                    document.getElementById('editorPanelLabel').textContent = 'LaTeX Source';
                }
            }
            renderFileTree();
        }
    } catch(e) { /* ignore */ }
}

/* ═══════════════════════════════════════
   ZIP Upload / Download
   ═══════════════════════════════════════ */
function triggerZipUpload() {
    document.getElementById('zipUploadInput').click();
}

document.getElementById('zipUploadInput').addEventListener('change', async (e) => {
    const file = e.target.files[0];
    if (!file || !currentProject) return;
    e.target.value = '';

    const formData = new FormData();
    formData.append('file', file);

    try {
        setLiveStatus('compiling', 'Uploading ZIP...');
        const res = await authFetch(`/api/projects/${currentProject.id}/upload-zip`, {
            method: 'POST',
            headers: {}, // Let browser set Content-Type for FormData
            body: formData,
        });
        if (res.ok) {
            const data = await res.json();
            projectFiles = data.files;
            fileContentsCache = {};
        expandedFolders = new Set();
            renderFileTree();
            // Open main file
            const mainFile = currentProject.main_file || 'main.tex';
            const mainF = projectFiles.find(f => f.filename === mainFile || f.filename.endsWith('/main.tex'));
            if (mainF) {
                openFile(mainF.id);
            } else if (projectFiles.length > 0) {
                openFile(projectFiles[0].id);
            }
            setLiveStatus('saved', 'ZIP uploaded');
            setTimeout(() => setLiveStatus('ready', 'Ready'), 2000);
        } else {
            const err = await res.json();
            alert(err.detail || 'Upload failed');
            setLiveStatus('error', 'Upload failed');
        }
    } catch(e) {
        alert('Upload failed: ' + e.message);
        setLiveStatus('error', 'Upload failed');
    }
});

async function downloadProjectZip() {
    if (!currentProject) return;
    try {
        const res = await authFetch(`/api/projects/${currentProject.id}/download-zip`);
        if (res.ok) {
            const blob = await res.blob();
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = (currentProject.title || 'project') + '.zip';
            a.click();
            URL.revokeObjectURL(url);
        }
    } catch(e) { /* ignore */ }
}

/* ═══════════════════════════════════════
   Dashboard ZIP Upload / Download
   ═══════════════════════════════════════ */
async function downloadProjectZipById(projectId, title) {
    try {
        const res = await authFetch(`/api/projects/${projectId}/download-zip`);
        if (res.ok) {
            const blob = await res.blob();
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = (title || 'project') + '.zip';
            a.click();
            URL.revokeObjectURL(url);
        }
    } catch(e) { /* ignore */ }
}

document.getElementById('dashboardZipInput').addEventListener('change', async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    e.target.value = '';

    // Derive project title from ZIP filename (strip .zip extension)
    const title = file.name.replace(/\.zip$/i, '') || 'Uploaded Project';

    try {
        // Create a new project
        const createRes = await authFetch('/api/projects', {
            method: 'POST',
            body: JSON.stringify({ title, source: '' }),
        });
        if (!createRes.ok) {
            alert('Failed to create project');
            return;
        }
        const project = await createRes.json();

        // Upload the ZIP into the new project
        const formData = new FormData();
        formData.append('file', file);
        const uploadRes = await authFetch(`/api/projects/${project.id}/upload-zip`, {
            method: 'POST',
            headers: {},
            body: formData,
        });
        if (!uploadRes.ok) {
            const err = await uploadRes.json();
            alert(err.detail || 'ZIP upload failed');
            return;
        }

        // Refresh the project list
        loadProjects();
    } catch(e) {
        alert('Upload failed: ' + e.message);
    }
});

/* ═══════════════════════════════════════
   Editable Project Title
   ═══════════════════════════════════════ */
document.getElementById('liveHeaderTitle').addEventListener('click', function() {
    if (!currentProject) return;
    const titleEl = this;
    const currentTitle = currentProject.title;

    const input = document.createElement('input');
    input.className = 'live-header-title-input';
    input.value = currentTitle;
    titleEl.textContent = '';
    titleEl.appendChild(input);
    input.focus();
    input.select();

    async function finishEdit() {
        const newTitle = input.value.trim() || currentTitle;
        titleEl.textContent = newTitle;
        if (newTitle !== currentTitle) {
            try {
                await authFetch(`/api/projects/${currentProject.id}/title`, {
                    method: 'PATCH',
                    body: JSON.stringify({ title: newTitle }),
                });
                currentProject.title = newTitle;
            } catch(e) {
                titleEl.textContent = currentTitle;
            }
        }
    }

    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') { e.preventDefault(); input.blur(); }
        if (e.key === 'Escape') { input.value = currentTitle; input.blur(); }
    });
    input.addEventListener('blur', finishEdit);
});

// Draggable divider (editor/preview)
(() => {
    const divider = document.getElementById('liveDivider');
    const editorPanel = document.querySelector('.live-editor-panel');
    const pdfPanel = document.querySelector('.live-pdf-panel');
    const liveBody = document.querySelector('.live-body');
    let dragging = false;

    divider.addEventListener('mousedown', (e) => {
        e.preventDefault();
        dragging = true;
        divider.classList.add('dragging');
        document.body.style.cursor = 'col-resize';
        document.body.style.userSelect = 'none';
        pdfPanel.style.pointerEvents = 'none';
    });

    document.addEventListener('mousemove', (e) => {
        if (!dragging) return;
        const rect = liveBody.getBoundingClientRect();
        const fileTree = document.getElementById('liveFileTree');
        const treeDivider = document.getElementById('liveTreeDivider');
        const treeWidth = fileTree.style.display === 'none' ? 0 : fileTree.offsetWidth + treeDivider.offsetWidth;
        const offset = e.clientX - rect.left - treeWidth;
        const availableWidth = rect.width - treeWidth - divider.offsetWidth;
        const pct = (offset / availableWidth) * 100;
        const clamped = Math.min(Math.max(pct, 10), 90);
        editorPanel.style.flex = 'none';
        editorPanel.style.width = clamped + '%';
        pdfPanel.style.flex = 'none';
        pdfPanel.style.width = (100 - clamped) + '%';
    });

    document.addEventListener('mouseup', () => {
        if (!dragging) return;
        dragging = false;
        divider.classList.remove('dragging');
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
        pdfPanel.style.pointerEvents = '';
    });
})();

// Draggable tree divider
(() => {
    const treeDivider = document.getElementById('liveTreeDivider');
    const fileTree = document.getElementById('liveFileTree');
    let dragging = false;

    treeDivider.addEventListener('mousedown', (e) => {
        e.preventDefault();
        dragging = true;
        treeDivider.classList.add('dragging');
        document.body.style.cursor = 'col-resize';
        document.body.style.userSelect = 'none';
    });

    document.addEventListener('mousemove', (e) => {
        if (!dragging) return;
        const liveBody = document.querySelector('.live-body');
        const rect = liveBody.getBoundingClientRect();
        const width = e.clientX - rect.left;
        const clamped = Math.min(Math.max(width, 140), 400);
        fileTree.style.width = clamped + 'px';
    });

    document.addEventListener('mouseup', () => {
        if (!dragging) return;
        dragging = false;
        treeDivider.classList.remove('dragging');
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
    });
})();

// Handle Tab key in editor
liveEditor.addEventListener('keydown', (e) => {
    if (e.key === 'Tab') {
        e.preventDefault();
        const start = liveEditor.selectionStart;
        const end   = liveEditor.selectionEnd;
        liveEditor.value = liveEditor.value.substring(0, start) + '    ' + liveEditor.value.substring(end);
        liveEditor.selectionStart = liveEditor.selectionEnd = start + 4;
    }
    // Ctrl/Cmd+S to save
    if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault();
        if (currentProject || (currentShareLink && currentShareLink.access_level === 'contributor')) {
            saveProject();
        }
    }
});

/* ═══════════════════════════════════════
   Utilities
   ═══════════════════════════════════════ */
function escHtml(str) {
    const d = document.createElement('div');
    d.textContent = str;
    return d.innerHTML;
}

/* ═══════════════════════════════════════
   Init
   ═══════════════════════════════════════ */
updateAuthUI();
router();
