const cameraState = {
    stream: null,
    facingMode: "environment",
    blob: null,
};

function stopCamera() {
    if (cameraState.stream) {
        cameraState.stream.getTracks().forEach((track) => track.stop());
        cameraState.stream = null;
    }
}

async function startCamera() {
    const video = document.getElementById("camera-preview");
    const placeholder = document.getElementById("camera-placeholder");
    const snapshot = document.getElementById("camera-snapshot");
    const captureBtn = document.getElementById("capture-photo");
    const inspectBtn = document.getElementById("inspect-photo");
    const retakeBtn = document.getElementById("retake-photo");

    stopCamera();
    snapshot.hidden = true;
    video.hidden = false;
    cameraState.blob = null;
    inspectBtn.disabled = true;
    retakeBtn.disabled = true;

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        placeholder.hidden = false;
        placeholder.textContent = "This browser does not support camera access. Please use Chrome or Safari on mobile.";
        captureBtn.disabled = true;
        return;
    }

    const attempts = [
        { audio: false, video: { facingMode: cameraState.facingMode, width: { ideal: 1280 }, height: { ideal: 720 } } },
        { audio: false, video: { facingMode: cameraState.facingMode } },
        { audio: false, video: true },
        { audio: false, video: { facingMode: "environment" } },
        { audio: false, video: { facingMode: "user" } },
    ];

    let lastError = null;
    for (const constraints of attempts) {
        try {
            cameraState.stream = await navigator.mediaDevices.getUserMedia(constraints);
            video.srcObject = cameraState.stream;
            placeholder.hidden = true;
            captureBtn.disabled = false;
            return;
        } catch (err) {
            lastError = err;
            stopCamera();
        }
    }

    placeholder.hidden = false;
    const message = lastError && lastError.message ? lastError.message : "Camera access is unavailable on this device.";
    placeholder.textContent = `Camera access failed: ${message}. Use "open the phone camera app" below.`;
    captureBtn.disabled = true;
}

function showSnapshot(blob) {
    const video = document.getElementById("camera-preview");
    const snapshot = document.getElementById("camera-snapshot");
    const inspectBtn = document.getElementById("inspect-photo");
    const retakeBtn = document.getElementById("retake-photo");

    cameraState.blob = blob;
    snapshot.src = URL.createObjectURL(blob);
    snapshot.hidden = false;
    video.hidden = true;
    inspectBtn.disabled = false;
    retakeBtn.disabled = false;
}

function captureFrame() {
    const video = document.getElementById("camera-preview");
    const canvas = document.getElementById("camera-canvas");
    if (!video.videoWidth) return;

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext("2d").drawImage(video, 0, 0);
    canvas.toBlob((blob) => {
        if (blob) showSnapshot(blob);
    }, "image/jpeg", 0.92);
}

async function loadAssets() {
    const select = document.getElementById("camera-asset");
    try {
        const assets = await fetchJSON("/api/assets");
        if (!assets.length) {
            select.innerHTML = '<option value="1">Building Wall (ID: 1)</option><option value="2">Bridge Span (ID: 2)</option><option value="3">Tower/Mast (ID: 3)</option>';
            return;
        }
        select.innerHTML = assets.map((a) =>
            `<option value="${a.id}">${a.name} (ID: ${a.id})</option>`
        ).join("");
    } catch (err) {
        select.innerHTML = '<option value="1">Building Wall (ID: 1)</option><option value="2">Bridge Span (ID: 2)</option><option value="3">Tower/Mast (ID: 3)</option>';
    }
}

function formatCameraInspectionOutput(result) {
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
        </div>
    `;
}

async function inspectCapturedPhoto() {
    const results = document.getElementById("camera-results");
    if (!cameraState.blob) {
        results.innerHTML = '<p class="loading">Capture or choose a photo first.</p>';
        return;
    }

    results.innerHTML = '<p class="loading">Running inspection...</p>';
    const formData = new FormData();
    formData.append("image", cameraState.blob, "mobile_capture.jpg");
    formData.append("asset_id", document.getElementById("camera-asset").value);
    formData.append("source", "mobile");

    try {
        const result = await fetchJSON("/api/inspect", { method: "POST", body: formData });
        results.innerHTML = formatCameraInspectionOutput(result);
    } catch (err) {
        results.innerHTML = `<p style="color: var(--danger);">Inspection failed: ${err.message}</p>`;
    }
}

async function loadLanHint() {
    const hint = document.getElementById("lan-hint");
    if (!hint) return;

    try {
        const network = await fetchJSON("/api/network");
        hint.textContent = `http://${network.host}:${network.port}/camera`;
    } catch (err) {
        hint.textContent = `${window.location.origin}/camera`;
    }
}

document.addEventListener("DOMContentLoaded", () => {
    loadAssets();
    loadLanHint();

    document.getElementById("start-camera").addEventListener("click", startCamera);
    document.getElementById("flip-camera").addEventListener("click", () => {
        cameraState.facingMode = cameraState.facingMode === "environment" ? "user" : "environment";
        startCamera();
    });
    document.getElementById("capture-photo").addEventListener("click", captureFrame);
    document.getElementById("retake-photo").addEventListener("click", startCamera);
    document.getElementById("inspect-photo").addEventListener("click", inspectCapturedPhoto);

    document.getElementById("native-camera").addEventListener("change", (e) => {
        const file = e.target.files && e.target.files[0];
        if (!file) return;
        document.getElementById("camera-placeholder").hidden = true;
        showSnapshot(file);
    });

    window.addEventListener("pagehide", stopCamera);
});
