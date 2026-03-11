const API_BASE = "http://127.0.0.1:8000";

// ── CLOCK ──
function updateClock() {
  const now = new Date();
  document.getElementById("clock").textContent =
    now.toTimeString().slice(0, 8);
}
setInterval(updateClock, 1000);
updateClock();

// ── FAKE SYS STATS ──
function animateStats() {
  const stats = [
    { bar: "bar-cpu", val: "val-cpu", min: 18, max: 72, suffix: "%" },
    { bar: "bar-mem", val: "val-mem", min: 40, max: 65, suffix: "%" },
    { bar: "bar-net", val: "val-net", min: 5,  max: 90, suffix: "%" },
  ];
  stats.forEach(s => {
    const v = Math.floor(Math.random() * (s.max - s.min) + s.min);
    document.getElementById(s.bar).style.width = v + "%";
    document.getElementById(s.val).textContent = v + s.suffix;
  });
}
animateStats();
setInterval(animateStats, 3000);

// ── FAKE COORDS ──
function animateCoords() {
  document.getElementById("lat").textContent =
    (Math.random() * 180 - 90).toFixed(4);
  document.getElementById("lon").textContent =
    (Math.random() * 360 - 180).toFixed(4);
  document.getElementById("alt").textContent =
    Math.floor(Math.random() * 120 + 10) + " m";
}
animateCoords();
setInterval(animateCoords, 4000);

// ── LOG ──
function log(msg, type = "") {
  const box = document.getElementById("logBox");
  const line = document.createElement("div");
  line.className = "log-line" + (type ? " " + type : "");
  const ts = new Date().toTimeString().slice(0, 8);
  line.textContent = `[${ts}] ${msg}`;
  box.appendChild(line);
  box.scrollTop = box.scrollHeight;
}

// ── MISSION START ──
async function startMission() {
  const btn = document.getElementById("launchBtn");
  btn.disabled = true;

  log("Initializing subsystems...");

  await sleep(400);
  log("YOLO model loading...");
  await sleep(300);
  log("Connecting to stream source...");

  try {
    const res = await fetch(`${API_BASE}/Mission-Start`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const mid = data.mission_id;

    log(`Mission ID assigned: ${mid}`, "ok");
    log("Stream thread started.", "ok");
    log("Storage process online.", "ok");

    document.getElementById("missionId").textContent = String(mid).slice(0, 8).toUpperCase();

    // Add to mission list
    const list = document.getElementById("missionList");
    list.innerHTML = "";
    const item = document.createElement("div");
    item.className = "mission-item active";
    item.textContent = `▶ MISSION #${String(mid).slice(0,8).toUpperCase()} — ACTIVE`;
    list.appendChild(item);

    // Store mission_id for stream page
    localStorage.setItem("mission_id", mid);

    // Show stream link
    document.getElementById("streamLink").classList.remove("hidden");

  } catch (e) {
    log("ERROR: " + e.message, "err");
    btn.disabled = false;
  }
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }