const API = '';

async function fetchJSON(url, options = {}) {
    const res = await fetch(API + url, options);
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
}

async function loadDashboardStats() {
    try {
        const [assets, inspections, summary] = await Promise.all([
            fetchJSON('/api/assets'),
            fetchJSON('/api/inspections'),
            fetchJSON('/api/summary'),
        ]);

        document.getElementById('total-assets').textContent = assets.length;
        document.getElementById('total-inspections').textContent = inspections.length;

        let totalDefects = 0;
        let criticalCount = 0;
        const classCounts = {};
        const severityCounts = { low: 0, medium: 0, high: 0, critical: 0 };

        for (const [cls, severities] of Object.entries(summary)) {
            let clsTotal = 0;
            for (const [sev, count] of Object.entries(severities)) {
                clsTotal += count;
                severityCounts[sev] = (severityCounts[sev] || 0) + count;
                if (sev === 'critical') criticalCount += count;
            }
            classCounts[cls] = clsTotal;
            totalDefects += clsTotal;
        }

        document.getElementById('total-defects').textContent = totalDefects;
        document.getElementById('critical-count').textContent = criticalCount;

        renderDefectChart(classCounts);
        renderSeverityChart(severityCounts);
    } catch (err) {
        console.error('Failed to load stats:', err);
    }
}

function renderDefectChart(data) {
    const ctx = document.getElementById('defectChart');
    if (!ctx) return;

    new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: Object.keys(data).length ? Object.keys(data) : ['No Defects'],
            datasets: [{
                data: Object.values(data).length ? Object.values(data) : [1],
                backgroundColor: [
                    '#ef4444', '#f97316', '#fbbf24', '#34d399',
                    '#4f8cff', '#a78bfa', '#f472b6', '#94a3b8',
                ],
            }],
        },
        options: {
            responsive: true,
            plugins: { legend: { position: 'bottom', labels: { color: '#9aa0a6' } } },
        },
    });
}

function renderSeverityChart(data) {
    const ctx = document.getElementById('severityChart');
    if (!ctx) return;

    const colors = { low: '#34d399', medium: '#fbbf24', high: '#ef4444', critical: '#dc2626' };

    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: Object.keys(data),
            datasets: [{
                label: 'Count',
                data: Object.values(data),
                backgroundColor: Object.keys(data).map(k => colors[k] || '#4f8cff'),
            }],
        },
        options: {
            responsive: true,
            plugins: { legend: { display: false } },
            scales: {
                y: { ticks: { color: '#9aa0a6' }, grid: { color: '#2d3348' } },
                x: { ticks: { color: '#9aa0a6' }, grid: { display: false } },
            },
        },
    });
}

async function loadPredictions() {
    const container = document.getElementById('predictions-list');
    if (!container) return;

    try {
        const predictions = await fetchJSON('/api/predict');
        if (predictions.length === 0) {
            container.innerHTML = '<p class="loading">No prediction data yet. Run inspections first.</p>';
            return;
        }

        container.innerHTML = predictions.map(p => `
            <div class="prediction-item" style="padding: 12px; margin-bottom: 10px; background: rgba(255,255,255,0.03); border-radius: 8px; border-left: 4px solid ${p.risk_level === 'critical' ? '#dc2626' : (p.risk_level === 'high' ? '#ef4444' : '#fbbf24')};">
                <strong>Asset #${p.asset_id}</strong>
                <span class="risk-${p.risk_level}"> — ${p.risk_level.toUpperCase()} RISK</span>
                <p style="color: var(--text-secondary); font-size: 0.88rem; margin-top: 6px;">
                    ${p.recommended_action}
                </p>
                <p style="font-size: 0.8rem; color: #9aa0a6; margin-top: 4px;">
                    Target Window: ${p.maintenance_window.recommended_date}
                </p>
            </div>
        `).join('');
    } catch (err) {
        container.innerHTML = '<p class="loading">Could not load predictions.</p>';
    }
}

let inspectionRows = [];

function formatInspectionDate(value) {
    if (!value) return '--';
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

function renderInspectionsTable() {
    const body = document.getElementById('inspections-body');
    if (!body) return;

    const query = (document.getElementById('search-inspections')?.value || '').trim().toLowerCase();
    const status = document.getElementById('status-filter')?.value || '';
    const rows = inspectionRows.filter((inspection) => {
        const searchable = `${inspection.id} ${inspection.asset_name} ${inspection.status}`.toLowerCase();
        return (!query || searchable.includes(query)) && (!status || inspection.status === status);
    });

    if (!rows.length) {
        body.innerHTML = '<tr><td colspan="7" class="loading">No inspections found.</td></tr>';
        return;
    }

    body.innerHTML = rows.map((inspection) => `
        <tr>
            <td>#${inspection.id}</td>
            <td>${inspection.asset_name}</td>
            <td>${inspection.image_count ?? 0}</td>
            <td>${inspection.defect_count ?? 0}</td>
            <td><span class="status-${inspection.status}">${inspection.status}</span></td>
            <td>${formatInspectionDate(inspection.started_at)}</td>
            <td>${formatInspectionDate(inspection.completed_at)}</td>
        </tr>
    `).join('');
}

async function loadInspectionsTable() {
    const body = document.getElementById('inspections-body');
    if (!body) return;

    try {
        const [inspections, assets] = await Promise.all([
            fetchJSON('/api/inspections'),
            fetchJSON('/api/assets'),
        ]);
        const assetNames = Object.fromEntries(assets.map((asset) => [asset.id, asset.name]));
        inspectionRows = inspections.map((inspection) => ({
            ...inspection,
            asset_name: assetNames[inspection.asset_id] || `Asset #${inspection.asset_id}`,
        }));
        renderInspectionsTable();
    } catch (err) {
        body.innerHTML = `<tr><td colspan="7" style="color: var(--danger);">Could not load inspections: ${err.message}</td></tr>`;
    }

    document.getElementById('search-inspections')?.addEventListener('input', renderInspectionsTable);
    document.getElementById('status-filter')?.addEventListener('change', renderInspectionsTable);
}

function formatInspectionOutput(result) {
    if (result.quality_status === 'insufficient') {
        return `
            <div style="margin-top: 16px; padding: 16px; background: rgba(239, 68, 68, 0.12); border: 1px solid rgba(239, 68, 68, 0.3); border-radius: 8px; color: #fca5a5;">
                <h4 style="margin: 0 0 8px 0; font-size: 1.05rem; color: #ef4444;">⚠️ Quality Warning</h4>
                <p style="margin: 0; font-size: 0.95rem; line-height: 1.5;">${result.message}</p>
            </div>`;
    }

    const priorityColors = {
        'Routine': '#34d399',
        'Medium': '#fbbf24',
        'High': '#ef4444',
        'Urgent': '#dc2626'
    };
    const prioColor = priorityColors[result.maintenance_priority] || '#34d399';

    const assetNames = {
        'building_wall': 'Building Wall',
        'bridge_span': 'Bridge Span',
        'tower_mast': 'Tower/Mast'
    };
    const displayName = assetNames[result.asset_type] || result.asset_name || 'Infrastructure Asset';

    let defectsBlock = '';
    if (result.defects_found > 0) {
        defectsBlock = `
            <p><strong>Defect:</strong> ${result.defect_type}</p>
            <p><strong>Severity:</strong> ${result.severity}</p>
            <p><strong>Confidence:</strong> ${result.confidence}%</p>
        `;
    } else {
        defectsBlock = `
            <p style="color: #34d399; font-weight: 500;">No visible defect detected.</p>
        `;
    }

    let imageBlock = '';
    if (result.annotated_image_url) {
        imageBlock = `
            <div style="margin-top: 16px;">
                <p style="margin-bottom: 6px; font-weight: 600; color: #9aa0a6;">Detected Image Output:</p>
                <img src="${result.annotated_image_url}" alt="Annotated Inspection Result" style="width: 100%; max-height: 380px; object-fit: contain; border-radius: 8px; border: 1px solid #2d3348; background: #000;" />
            </div>
        `;
    } else if (result.annotated_video_url) {
        imageBlock = `
            <div style="margin-top: 16px;">
                <p style="margin-bottom: 6px; font-weight: 600; color: #9aa0a6;">Annotated Video Output:</p>
                <video src="${result.annotated_video_url}" controls playsinline style="width: 100%; max-height: 380px; border-radius: 8px; border: 1px solid #2d3348; background: #000;"></video>
            </div>
        `;
    }

    return `
        <div style="margin-top: 16px; padding: 18px; background: #181c28; border: 1px solid #2d3348; border-radius: 10px; font-family: monospace, sans-serif; line-height: 1.6; color: #e2e8f0;">
            <div style="border-bottom: 1px dashed #374151; padding-bottom: 8px; margin-bottom: 12px;">
                <h4 style="margin: 0; color: #60a5fa; letter-spacing: 1px; font-size: 1.1rem;">INSPECTION COMPLETE</h4>
            </div>
            
            <p><strong>Asset:</strong> ${displayName}</p>
            <p><strong>Asset ID:</strong> ${result.asset_id}</p>
            
            <p style="margin-top: 10px;"><strong>Defects Found:</strong> ${result.defects_found}</p>
            
            ${defectsBlock}
            
            <div style="margin: 12px 0; padding: 10px; background: #1e2436; border-radius: 6px;">
                <p><strong>Condition Score:</strong> <span style="font-size: 1.1rem; font-weight: bold; color: ${result.condition_score > 75 ? '#34d399' : (result.condition_score > 50 ? '#fbbf24' : '#ef4444')}">${result.condition_score}/100</span></p>
                <p><strong>Maintenance Priority:</strong> <span style="color: ${prioColor}; font-weight: bold;">${result.maintenance_priority}</span></p>
                <p><strong>Asset Trend:</strong> <span style="color: ${result.trend === 'Deteriorating' ? '#ef4444' : '#60a5fa'}">${result.trend}</span></p>
            </div>
            
            <p><strong>Recommended Maintenance:</strong><br><span style="color: #cbd5e1;">${result.recommended_maintenance}</span></p>
            
            <p style="margin-top: 10px;"><strong>Next Inspection:</strong> ${result.next_inspection_days} days</p>
            
            ${imageBlock}
            
            <div style="margin-top: 12px; font-size: 0.75rem; color: #64748b; font-style: italic;">
                * System provides AI-assisted maintenance recommendations. Not a formal structural safety certification.
            </div>
        </div>
    `;
}

document.addEventListener('DOMContentLoaded', () => {
    const menuToggle = document.getElementById('menu-toggle');
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebar-overlay');
    if (menuToggle && sidebar && overlay) {
        const closeMenu = () => {
            sidebar.classList.remove('open');
            overlay.classList.remove('show');
        };
        menuToggle.addEventListener('click', () => {
            sidebar.classList.toggle('open');
            overlay.classList.toggle('show');
        });
        overlay.addEventListener('click', closeMenu);
    }

    if (document.getElementById('total-assets')) {
        loadDashboardStats();
    }
    if (document.getElementById('predictions-list')) {
        loadPredictions();
    }
    const uploadInput = document.getElementById('image-upload');
    if (uploadInput) {
        uploadInput.addEventListener('change', () => {
            const source = document.getElementById('inspect-source');
            if (source) source.value = 'mobile';
        });
    }

    const form = document.getElementById('inspect-form');
    if (form) {
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            const resultsDiv = document.getElementById('inspect-results');
            resultsDiv.innerHTML = '<p class="loading">Running inspection and analyzing media...</p>';

            const formData = new FormData(form);
            try {
                const result = await fetchJSON('/api/inspect', { method: 'POST', body: formData });
                resultsDiv.innerHTML = formatInspectionOutput(result);
                loadDashboardStats();
                loadPredictions();
            } catch (err) {
                resultsDiv.innerHTML = `<p style="color: var(--danger); padding: 12px; background: rgba(239, 68, 68, 0.1); border-radius: 6px;">Inspection failed: ${err.message}</p>`;
            }
        });
    }

});
