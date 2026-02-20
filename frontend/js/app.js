/* ================================================================
   CortexKey — Main Frontend Application
   
   Works in two modes:
     • LOCAL  — WebSocket (Flask + SocketIO on localhost)
     • CLOUD  — Stateless REST (Vercel serverless functions)
   
   Auto-detects which mode based on /api/health response.
   ================================================================ */

(() => {
"use strict";

// ----------------------------------------------------------------
// CONFIG
// ----------------------------------------------------------------
const API       = "";                         // same origin
const WS_URL    = window.location.origin;     // SocketIO auto-detects
const SCOPE_PTS = 80;                         // points on oscilloscope
const SCOPE_Y_RANGE = 5;                      // ±mV
const CHUNK_DELAY_MS = 500;                   // animation delay per chunk (cloud mode)

// ----------------------------------------------------------------
// DOM refs
// ----------------------------------------------------------------
const $ = (s) => document.querySelector(s);
const connectionDot   = $("#connectionDot");
const connectionText  = $("#connectionText");
const btnStartAuth    = $("#btnStartAuth");
const btnMockAuth     = $("#btnMockAuth");
const btnMockImp      = $("#btnMockImp");
const scopeCanvas     = $("#scopeCanvas");
const scopeCtx        = scopeCanvas.getContext("2d");
const barTheta        = $("#barTheta");
const barAlpha        = $("#barAlpha");
const barBeta         = $("#barBeta");
const valTheta        = $("#valTheta");
const valAlpha        = $("#valAlpha");
const valBeta         = $("#valBeta");
const gaugeArc        = $("#gaugeArc");
const gaugeLabel      = $("#gaugeLabel");
const statusCard      = $("#statusCard");
const statusIcon      = $("#statusIcon");
const statusMsg       = $("#statusMsg");
const statusSub       = $("#statusSub");
const logScroll       = $("#logScroll");

// ----------------------------------------------------------------
// STATE
// ----------------------------------------------------------------
let waveform        = new Array(SCOPE_PTS).fill(0);
let confidence      = 0;
let authStatus      = "idle";
let currentMock     = "auth";
let animFrameId     = null;
let socket          = null;
let isCloudMode     = false;   // true when running on Vercel
let _scanAbort      = false;   // cancel cloud animation

// ----------------------------------------------------------------
// LOG
// ----------------------------------------------------------------
function log(msg, type = "info") {
    const el = document.createElement("div");
    el.className = `log-entry ${type}`;
    const now = new Date();
    const ts  = now.toLocaleTimeString("en-GB", { hour12: false });
    el.innerHTML = `<span class="ts">${ts}</span> ${msg}`;
    logScroll.appendChild(el);
    logScroll.scrollTop = logScroll.scrollHeight;
    while (logScroll.children.length > 200) logScroll.removeChild(logScroll.firstChild);
}

// ----------------------------------------------------------------
// API helpers
// ----------------------------------------------------------------
async function api(path, method = "GET", body = null) {
    const opts = { method, headers: { "Content-Type": "application/json" } };
    if (body) opts.body = JSON.stringify(body);
    try {
        const res = await fetch(`${API}${path}`, opts);
        return await res.json();
    } catch (e) {
        log(`API error: ${e.message}`, "error");
        return null;
    }
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

// ----------------------------------------------------------------
// WebSocket (local mode only)
// ----------------------------------------------------------------
function connectWS() {
    if (typeof io === "undefined") {
        log("SocketIO not available — using REST mode", "info");
        isCloudMode = true;
        return;
    }
    try {
        socket = io(WS_URL, { transports: ["websocket", "polling"], reconnectionAttempts: 3, timeout: 3000 });

        socket.on("connect", () => {
            isCloudMode = false;
            setConnection("online");
            log("WebSocket connected", "success");
        });
        socket.on("disconnect", () => {
            setConnection("offline");
            log("WebSocket disconnected", "error");
        });
        socket.on("connect_error", () => {
            log("WebSocket unavailable — using cloud REST mode", "info");
            isCloudMode = true;
            socket.close();
        });

        socket.on("waveform_update", (data) => {
            if (data.waveform && data.waveform.length) {
                waveform = waveform.concat(data.waveform).slice(-SCOPE_PTS);
            }
        });

        socket.on("confidence_update", (data) => {
            confidence = data.confidence;
            updateGauge(confidence);
            if (data.band_powers) updateBands(data.band_powers);
            log(`Confidence: ${(confidence * 100).toFixed(1)}% (chunk ${data.chunk})`,
                confidence >= 0.65 ? "success" : "info");
        });

        socket.on("auth_complete", (data) => {
            authStatus = data.status;
            confidence = data.confidence;
            updateGauge(confidence);
            updateStatus(authStatus);
            btnStartAuth.disabled = false;
            btnStartAuth.textContent = "Start Authentication";
            log(`Result: ${authStatus.toUpperCase()} (${(confidence*100).toFixed(1)}%)`,
                authStatus === "authenticated" ? "success" : "error");
        });
    } catch (e) {
        isCloudMode = true;
    }
}

// ----------------------------------------------------------------
// Connection indicator
// ----------------------------------------------------------------
function setConnection(state) {
    connectionDot.className = `status-dot ${state}`;
    connectionText.textContent = state === "online" ? "System Online" :
                                  state === "offline" ? "Disconnected" : "Connecting…";
}

// ----------------------------------------------------------------
// Client-side mock waveform (for idle animation in cloud mode)
// ----------------------------------------------------------------
let _idleT = 0;
function generateIdleWaveform() {
    const pts = [];
    for (let i = 0; i < 4; i++) {
        const t = _idleT;
        _idleT += 1 / 250;
        if (currentMock === "auth") {
            pts.push(
                2.5 * Math.sin(2 * Math.PI * 10 * t)
              + 1.2 * Math.sin(2 * Math.PI * 20 * t)
              + 0.6 * Math.sin(2 * Math.PI * 6 * t)
              + 0.3 * (Math.random() * 2 - 1)
            );
        } else {
            pts.push(1.5 * (Math.random() * 2 - 1));
        }
    }
    return pts;
}

// ----------------------------------------------------------------
// Cloud-mode authentication (animate pre-computed chunks)
// ----------------------------------------------------------------
async function runCloudAuth() {
    _scanAbort = false;
    authStatus = "scanning";
    updateStatus("scanning");
    btnStartAuth.textContent = "Stop";
    log("Starting authentication scan (cloud)…", "info");

    const data = await api("/api/auth/start", "POST", { mode: currentMock });
    if (!data || !data.chunks) {
        log("API call failed", "error");
        authStatus = "idle";
        updateStatus("idle");
        btnStartAuth.textContent = "Start Authentication";
        return;
    }

    // Animate each chunk with a delay
    for (const chunk of data.chunks) {
        if (_scanAbort) {
            authStatus = "idle";
            updateStatus("idle");
            btnStartAuth.textContent = "Start Authentication";
            log("Authentication cancelled", "info");
            return;
        }

        if (chunk.waveform && chunk.waveform.length) {
            waveform = waveform.concat(chunk.waveform).slice(-SCOPE_PTS);
        }

        confidence = chunk.confidence;
        updateGauge(confidence);

        if (chunk.band_powers) updateBands(chunk.band_powers);

        log(`Confidence: ${(confidence * 100).toFixed(1)}% (chunk ${chunk.chunk})`,
            confidence >= 0.65 ? "success" : "info");

        await sleep(CHUNK_DELAY_MS);
    }

    authStatus = data.status;
    confidence = data.confidence;
    updateGauge(confidence);
    updateStatus(authStatus);
    btnStartAuth.disabled = false;
    btnStartAuth.textContent = "Start Authentication";
    log(`Result: ${authStatus.toUpperCase()} (${(confidence*100).toFixed(1)}%)`,
        authStatus === "authenticated" ? "success" : "error");
}

// ----------------------------------------------------------------
// Oscilloscope rendering (Canvas 2D)
// ----------------------------------------------------------------
function initScope() {
    resizeScope();
    window.addEventListener("resize", resizeScope);
    renderLoop();
}

function resizeScope() {
    const rect = scopeCanvas.parentElement.getBoundingClientRect();
    scopeCanvas.width  = Math.floor(rect.width - 32);
    scopeCanvas.height = 220;
}

function renderLoop() {
    drawScope();
    animFrameId = requestAnimationFrame(renderLoop);
}

function drawScope() {
    const W = scopeCanvas.width;
    const H = scopeCanvas.height;
    const ctx = scopeCtx;

    ctx.clearRect(0, 0, W, H);

    // Grid
    ctx.strokeStyle = "rgba(34,211,238,0.07)";
    ctx.lineWidth = 1;
    const cols = 20, rows = 10;
    for (let i = 0; i <= cols; i++) {
        const x = (W / cols) * i;
        ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke();
    }
    for (let i = 0; i <= rows; i++) {
        const y = (H / rows) * i;
        ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke();
    }

    // Center line
    ctx.strokeStyle = "rgba(34,211,238,0.15)";
    ctx.beginPath(); ctx.moveTo(0, H/2); ctx.lineTo(W, H/2); ctx.stroke();

    // Y-axis labels
    ctx.fillStyle = "rgba(148,163,184,0.5)";
    ctx.font = "10px monospace";
    ctx.fillText(`+${SCOPE_Y_RANGE} mV`, 4, 14);
    ctx.fillText(` 0 mV`, 4, H/2 - 4);
    ctx.fillText(`-${SCOPE_Y_RANGE} mV`, 4, H - 6);

    if (waveform.length < 2) return;

    ctx.strokeStyle = "#22d3ee";
    ctx.lineWidth = 2;
    ctx.shadowColor = "rgba(34,211,238,0.6)";
    ctx.shadowBlur = 8;
    ctx.beginPath();
    for (let i = 0; i < waveform.length; i++) {
        const x = (i / (SCOPE_PTS - 1)) * W;
        const val = waveform[i] || 0;
        const y = H / 2 - (val / SCOPE_Y_RANGE) * (H / 2);
        if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    }
    ctx.stroke();
    ctx.shadowBlur = 0;

    ctx.strokeStyle = "rgba(34,211,238,0.15)";
    ctx.lineWidth = 6;
    ctx.beginPath();
    for (let i = 0; i < waveform.length; i++) {
        const x = (i / (SCOPE_PTS - 1)) * W;
        const val = waveform[i] || 0;
        const y = H / 2 - (val / SCOPE_Y_RANGE) * (H / 2);
        if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    }
    ctx.stroke();
}

// ----------------------------------------------------------------
// Gauge
// ----------------------------------------------------------------
const GAUGE_CIRCUM = 2 * Math.PI * 85;

function updateGauge(value) {
    const pct = Math.max(0, Math.min(1, value));
    const offset = GAUGE_CIRCUM * (1 - pct);
    gaugeArc.style.strokeDashoffset = offset;

    let colour;
    if (pct < 0.4)       colour = "#f87171";
    else if (pct < 0.65) colour = "#fbbf24";
    else                  colour = "#34d399";

    gaugeArc.style.stroke = colour;
    gaugeArc.style.filter = `drop-shadow(0 0 8px ${colour})`;
    gaugeLabel.innerHTML = `${Math.round(pct * 100)}<span>%</span>`;
}

// ----------------------------------------------------------------
// Band power bars
// ----------------------------------------------------------------
function updateBands(bp) {
    const maxPow = 3.0;
    const pct = (v) => Math.min(100, (v / maxPow) * 100).toFixed(1);

    barTheta.style.width = `${pct(bp.theta)}%`;
    barAlpha.style.width = `${pct(bp.alpha)}%`;
    barBeta.style.width  = `${pct(bp.beta)}%`;

    valTheta.textContent = bp.theta.toFixed(2);
    valAlpha.textContent = bp.alpha.toFixed(2);
    valBeta.textContent  = bp.beta.toFixed(2);
}

// ----------------------------------------------------------------
// Status card
// ----------------------------------------------------------------
function updateStatus(status) {
    statusCard.className = `status-card ${status}`;
    switch (status) {
        case "idle":
            statusIcon.textContent = "🧠";
            statusMsg.textContent  = "Ready to scan";
            statusSub.textContent  = "Place electrodes and press Start";
            break;
        case "scanning":
            statusIcon.textContent = "🧠";
            statusMsg.textContent  = "SCANNING…";
            statusSub.textContent  = "Reading neural signature";
            break;
        case "authenticated":
            statusIcon.textContent = "✅";
            statusMsg.textContent  = "ACCESS GRANTED";
            statusSub.textContent  = `Confidence: ${(confidence*100).toFixed(1)}%`;
            break;
        case "denied":
            statusIcon.textContent = "❌";
            statusMsg.textContent  = "ACCESS DENIED";
            statusSub.textContent  = `Confidence: ${(confidence*100).toFixed(1)}%`;
            break;
    }
}

// ----------------------------------------------------------------
// Button handlers
// ----------------------------------------------------------------
btnStartAuth.addEventListener("click", async () => {
    if (authStatus === "scanning") {
        _scanAbort = true;
        await api("/api/auth/stop", "POST");
        authStatus = "idle";
        updateStatus("idle");
        btnStartAuth.textContent = "Start Authentication";
        log("Authentication cancelled", "info");
        return;
    }

    // Reset UI
    confidence = 0;
    updateGauge(0);
    updateBands({ theta: 0, alpha: 0, beta: 0 });

    if (isCloudMode) {
        runCloudAuth();
    } else {
        authStatus = "scanning";
        updateStatus("scanning");
        btnStartAuth.textContent = "Stop";
        log("Starting authentication scan…", "info");
        await api("/api/auth/start", "POST");
    }
});

btnMockAuth.addEventListener("click", async () => {
    currentMock = "auth";
    btnMockAuth.classList.add("active");
    btnMockImp.classList.remove("active");
    await api("/api/demo/mode", "POST", { mode: "auth" });
    log("Switched to Mock Authenticated mode", "info");
});

btnMockImp.addEventListener("click", async () => {
    currentMock = "impostor";
    btnMockImp.classList.add("active");
    btnMockAuth.classList.remove("active");
    await api("/api/demo/mode", "POST", { mode: "impostor" });
    log("Switched to Mock Impostor mode", "info");
});

btnMockAuth.classList.add("active");

// ----------------------------------------------------------------
// Idle waveform animation
// ----------------------------------------------------------------
function idleWaveformLoop() {
    if (authStatus !== "scanning") {
        if (isCloudMode) {
            const pts = generateIdleWaveform();
            waveform = waveform.concat(pts).slice(-SCOPE_PTS);
        } else {
            api("/api/auth/status").then(data => {
                if (data && data.waveform && data.waveform.length) {
                    waveform = waveform.concat(data.waveform).slice(-SCOPE_PTS);
                }
            });
        }
    }
    setTimeout(idleWaveformLoop, isCloudMode ? 16 : 250);
}

// ----------------------------------------------------------------
// BOOT
// ----------------------------------------------------------------
async function boot() {
    log("CortexKey Neural Authentication System", "success");
    log("Initializing…", "info");

    initScope();

    // Check backend health
    const h = await api("/api/health");
    if (h) {
        setConnection("online");
        log(`Backend online — mode: ${h.mock_mode || "mock"}`, "success");

        if (h.deployment === "vercel") {
            isCloudMode = true;
            log("Running in cloud mode (Vercel)", "info");
        } else {
            connectWS();
        }
    } else {
        setConnection("offline");
        log("Backend unreachable — check if server is running", "error");
    }

    idleWaveformLoop();
}

boot();

})();
