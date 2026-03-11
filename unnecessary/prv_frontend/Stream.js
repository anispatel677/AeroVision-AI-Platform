const API_BASE = "http://127.0.0.1:8000";
const mission_id = localStorage.getItem("mission_id");

let detectionCount = 0;
let frameCount = 0;
let lastFpsTime = Date.now();
let timelinePos = 0;

// ── CLOCK ──
function updateClock() {
  document.getElementById("clock").textContent =
    new Date().toTimeString().slice(0, 8);
}
setInterval(updateClock, 1000);
updateClock();

// ── MISSION LABELS ──
if (mission_id) {
  const tag = `MISSION ${String(mission_id).slice(0, 8).toUpperCase()}`;
  document.getElementById("missionTag").textContent = tag;
  document.getElementById("missionSubLabel").textContent = tag;
}

// ── STREAM via <img> tag — simple and stable ──
// The ONLY thing we do is set src once and never touch it again.
// No onload/onerror loops. The browser handles MJPEG natively.
const overlay = document.getElementById("streamOverlay");
const streamImg = document.getElementById("streamImg");

if (!mission_id) {

  overlay.querySelector("span").textContent = "NO ACTIVE MISSION";

} else {

  // Set src exactly once — browser streams MJPEG natively, no JS needed
  streamImg.src = `${API_BASE}/stream`;

  // Hide overlay once the first frame paints
  streamImg.addEventListener("load", () => {
    overlay.classList.add("hidden");
  }, { once: true });

  // FPS counter — use a MutationObserver on the img's natural size changing
  // instead of onload which fires on every frame and causes flicker
  let fpsInterval = setInterval(() => {
    if (streamImg.naturalWidth > 0) {
      clearInterval(fpsInterval);
      overlay.classList.add("hidden");
      startFpsCounter();
    }
  }, 200);
}

function startFpsCounter() {
  // Approximate FPS by sampling the img currentSrc timestamp hack
  // Real frame count isn't accessible from img tag — show fixed estimate
  document.getElementById("fps").textContent = "FPS: ~25";
  document.getElementById("resolution").textContent =
    `${streamImg.naturalWidth}×${streamImg.naturalHeight}`;
}

// ── DETECTIONS POLL ──
async function loadDetections() {

  if (!mission_id) return;

  try {
    const res = await fetch(`${API_BASE}/detections/${mission_id}`);
    if (!res.ok) return;
    const data = await res.json();

    const list = document.getElementById("detList");

    if (data.length === 0) {
      if (!list.querySelector(".det-card")) {
        list.innerHTML = '<div class="det-empty">NO DETECTIONS YET</div>';
      }
      return;
    }

    const existing = list.querySelectorAll(".det-card").length;
    if (data.length === existing) return;

    if (existing === 0) list.innerHTML = "";

    for (let i = existing; i < data.length; i++) {
      addDetectionCard(data[i], i + 1);
      addTimelineBlip();
    }

    detectionCount = data.length;
    document.getElementById("detCount").textContent = `DETECTIONS: ${detectionCount}`;
    document.getElementById("totalCount").textContent = detectionCount;

  } catch (e) {
    console.warn("Detection fetch error:", e);
  }
}

function addDetectionCard(d, index) {
  const list = document.getElementById("detList");
  const card = document.createElement("div");
  card.className = "det-card";
  const ts = new Date().toTimeString().slice(0, 8);

  card.innerHTML = `
    <img src="${d.url}" alt="Detection ${index}" loading="lazy" />
    <div class="det-card-body">
      <div class="det-card-id">▸ TARGET #${String(index).padStart(3, "0")}</div>
      <div class="det-card-coords">LAT ${d.lat.toFixed(4)} · LON ${d.long.toFixed(4)}</div>
      <div class="det-card-time">CAPTURED · ${ts}</div>
    </div>
  `;

  list.appendChild(card);
  list.scrollTop = list.scrollHeight;
}

function addTimelineBlip() {
  const track = document.getElementById("timeline");
  const blip = document.createElement("div");
  blip.className = "timeline-blip";
  timelinePos = Math.min(timelinePos + Math.random() * 6 + 2, 96);
  blip.style.left = timelinePos + "%";
  track.appendChild(blip);
}

setInterval(loadDetections, 3000);
loadDetections();