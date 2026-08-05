// SPDX-License-Identifier: GPL-3.0-or-later
// Edge-AI Spectrophotometer — Home tab

const socket = io();

// ---------------------------------------------------------------- constants

// 12 channels, wavelength order — must match CH_ORDER in sketch.ino
const wavelengths = [405, 425, 450, 475, 515, 555, 600, 640, 690, 745, 855, 940];

const SATURATION = 65000;

const TESTER = document.getElementById("tester");

const RETRO_CONFIG = { displayModeBar: false, responsive: true };

function retroLayout(yTitle) {
  return {
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    margin: { t: 14, l: 62, r: 16, b: 42 },
    autosize: true,
    height: 330,
    font: { family: "ui-monospace, Menlo, Consolas, monospace", size: 14, color: "#8FA98B" },
    xaxis: {
      title: { text: "WAVELENGTH (nm)", font: { size: 14 } },
      gridcolor: "rgba(143,169,139,.16)",
      zerolinecolor: "rgba(143,169,139,.3)",
      linecolor: "rgba(143,169,139,.4)",
      tickfont: { size: 14 },
    },
    yaxis: {
      title: { text: yTitle, font: { size: 14 } },
      gridcolor: "rgba(143,169,139,.16)",
      zerolinecolor: "rgba(143,169,139,.3)",
      linecolor: "rgba(143,169,139,.4)",
      tickfont: { size: 14 },
    },
    showlegend: false,
  };
}

const LAYOUT_BASELINE = retroLayout("SIGNAL (ADC counts)");
const LAYOUT_SCAN     = retroLayout("ABSORBANCE (AU)");

const TRACE = {
  type: "scatter",
  mode: "lines+markers",
  line: { color: "#FFB347", width: 2, shape: "spline" },
  marker: { color: "#FFD08A", size: 5 },
};

// ---------------------------------------------------------------- state

const scanState = {
  baseline: null,   // { raw:[12], darkStd:[12], saturated:bool }
  lastScan: null,   // { raw:[12], absorbance:[12]|null, saturated:bool }
};

const scanSettings = {
  name: "Sample 1",
  category: "Other",
  isReference: false,
  knownValue: 0,
};

let continuousIntervalId = null;
let isContinuous = false;

// ---------------------------------------------------------------- elements

const baselineBtn        = document.getElementById("baseline-btn");
const singleScanBtn      = document.getElementById("single-scan-btn");
const continuousBtn      = document.getElementById("continuous-btn");
const saveDataBtn        = document.getElementById("save-data-btn");
const settingsBtn        = document.getElementById("settings-btn");
const scanStatus         = document.getElementById("scan-status");
const settingsModal      = document.getElementById("settings-modal");
const settingsCancelBtn  = document.getElementById("settings-cancel-btn");
const settingsSaveBtn    = document.getElementById("settings-save-btn");

saveDataBtn.disabled = true;

// ---------------------------------------------------------------- helpers

function setScanStatus(text, isError = false) {
  if (!scanStatus) return;
  scanStatus.textContent = text;
  scanStatus.style.color = isError ? "#C24634" : "";
}

const showError = (msg) => setScanStatus(msg, true);

function isValidVector(v) {
  return Array.isArray(v) && v.length === wavelengths.length;
}

function plot(values, layout) {
  Plotly.react(TESTER, [{ ...TRACE, x: wavelengths, y: values }], layout, RETRO_CONFIG);
}

// unit: "counts" for baseline, "AU" for absorbance
function updateReadout(values, title, unit, noise) {
  const max  = Math.max(...values);
  const min  = Math.min(...values);
  const mean = values.reduce((a, b) => a + b, 0) / values.length;
  const dp   = unit === "AU" ? 4 : 0;

  document.getElementById("readout-title").textContent = title;
  document.getElementById("rd-max").textContent =
    `${max.toFixed(dp)} ${unit} @ ${wavelengths[values.indexOf(max)]} nm`;
  document.getElementById("rd-min").textContent =
    `${min.toFixed(dp)} ${unit} @ ${wavelengths[values.indexOf(min)]} nm`;
  document.getElementById("rd-mean").textContent = `${mean.toFixed(dp)} ${unit}`;
  document.getElementById("rd-noise").textContent =
    noise == null ? "—" : `${noise.toFixed(dp)} ${unit}`;
  document.getElementById("peak-abs").textContent = max.toFixed(dp);
}

// mean of the per-channel dark standard deviations
function meanNoise() {
  const s = scanState.baseline?.darkStd;
  return isValidVector(s) ? s.reduce((a, b) => a + b, 0) / s.length : null;
}

// ---------------------------------------------------------------- socket in

socket.on("baseline_result", (payload) => {
  const raw = payload?.raw ?? payload;
  if (!isValidVector(raw)) {
    return showError(`Baseline malformed — expected ${wavelengths.length} channels.`);
  }

  const saturated = raw.some((v) => v >= SATURATION);
  scanState.baseline = { raw, darkStd: payload?.dark_std ?? null, saturated };
  scanState.lastScan = null;
  saveDataBtn.disabled = true;

  plot(raw, LAYOUT_BASELINE);
  updateReadout(raw, "Peak Signal", "counts", meanNoise());

  setScanStatus(
    saturated
      ? "Baseline captured — CHANNEL SATURATED, dim the LED and retry."
      : "Baseline captured.",
    saturated
  );
});

socket.on("scan_result", (payload) => {
  const raw = payload?.raw ?? payload;
  if (!isValidVector(raw)) {
    return showError(`Scan malformed — expected ${wavelengths.length} channels.`);
  }

  const absorbance = isValidVector(payload?.absorbance) ? payload.absorbance : null;
  const saturated  = raw.some((v) => v >= SATURATION);

  scanState.lastScan = { raw, absorbance, saturated };
  saveDataBtn.disabled = false;

  if (absorbance) {
    plot(absorbance, LAYOUT_SCAN);
    updateReadout(absorbance, "Peak Absorbance", "AU", null);
  } else {
    plot(raw, LAYOUT_BASELINE);
    updateReadout(raw, "Peak Signal", "counts", meanNoise());
  }

  if (saturated)          setScanStatus("Scan captured — CHANNEL SATURATED.", true);
  else if (!absorbance)   setScanStatus("Scan captured (raw counts — no baseline yet).");
  else                    setScanStatus("Scan captured.");
});

socket.on("save_ok", (d) => setScanStatus(`Saved: ${d.name}`));
socket.on("error",   (d) => showError(d.msg ?? "Unknown error"));

socket.on("connect",    () => setScanStatus("Connected."));
socket.on("disconnect", () => {
  showError("Connection lost.");
  stopContinuous();
});

// ---------------------------------------------------------------- actions

function captureBaseline() {
  setScanStatus("Capturing baseline…");
  socket.emit("capture_baseline", {});
}

function runSingleScan() {
  setScanStatus("Scanning…");
  socket.emit("single_scan", {});
}

function startContinuous() {
  isContinuous = true;
  continuousBtn.textContent = "Stop";
  continuousBtn.classList.add("running");
  socket.emit("single_scan", {});
  continuousIntervalId = setInterval(() => socket.emit("single_scan", {}), 2000);
}

function stopContinuous() {
  isContinuous = false;
  continuousBtn.textContent = "Continuous";
  continuousBtn.classList.remove("running");
  clearInterval(continuousIntervalId);
  continuousIntervalId = null;
}

function toggleContinuousScan() {
  isContinuous ? stopContinuous() : startContinuous();
}

function saveData() {
  if (!scanState.lastScan?.raw?.length) {
    return showError("No scan to save — run a Single Scan first.");
  }
  if (!scanSettings.name || !scanSettings.category) {
    return showError("Set a name and category in Settings before saving.");
  }
  if (scanState.lastScan.saturated &&
      !confirm("This scan has a saturated channel. Save anyway?")) {
    return;
  }

  socket.emit("save_scan_data", {
    name:         scanSettings.name,
    category:     scanSettings.category,
    is_reference: scanSettings.isReference ? 1 : 0,
    known_value:  scanSettings.isReference ? 0 : scanSettings.knownValue,
    raw_counts:   scanState.lastScan.raw,
    saturated:    scanState.lastScan.saturated ? 1 : 0,
  });
}

// ---------------------------------------------------------------- settings

function openSettingsModal() {
  document.getElementById("setting-name").value        = scanSettings.name;
  document.getElementById("setting-category").value    = scanSettings.category;
  document.getElementById("setting-reference").value   = scanSettings.isReference ? "Yes" : "No";
  document.getElementById("setting-known-value").value = scanSettings.knownValue;
  settingsModal.classList.remove("hidden");
}

function closeSettingsModal() {
  settingsModal.classList.add("hidden");
}

function saveSettings() {
  const name = document.getElementById("setting-name").value.trim();
  if (!name) return showError("Sample name cannot be empty.");

  scanSettings.name        = name;
  scanSettings.category    = document.getElementById("setting-category").value;
  scanSettings.isReference = document.getElementById("setting-reference").value === "Yes";

  // A reference IS the 0% point of the dilution series
  const kv = parseFloat(document.getElementById("setting-known-value").value);
  scanSettings.knownValue = scanSettings.isReference ? 0 : (Number.isFinite(kv) ? kv : 0);

  document.getElementById("rd-name").textContent     = scanSettings.name;
  document.getElementById("rd-category").textContent = scanSettings.category;
  document.getElementById("rd-ref").textContent      = scanSettings.isReference ? "YES" : "NO";
  const kvEl = document.getElementById("rd-known-value");
  if (kvEl) kvEl.textContent = scanSettings.knownValue;

  closeSettingsModal();
  setScanStatus("Settings updated.");
}

// ---------------------------------------------------------------- tabs

function switchTab(event, tabId) {
  document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
  document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));

  document.getElementById(tabId).classList.add("active");
  event.currentTarget.classList.add("active");

  // Plotly renders at zero width inside a hidden panel
  if (tabId === "tab1" && window.Plotly) Plotly.Plots.resize(TESTER);
}

// ---------------------------------------------------------------- init

baselineBtn?.addEventListener("click", captureBaseline);
singleScanBtn?.addEventListener("click", runSingleScan);
continuousBtn?.addEventListener("click", toggleContinuousScan);
saveDataBtn?.addEventListener("click", saveData);
settingsBtn?.addEventListener("click", openSettingsModal);
settingsSaveBtn?.addEventListener("click", saveSettings);
settingsCancelBtn?.addEventListener("click", closeSettingsModal);
settingsModal?.addEventListener("click", (e) => {
  if (e.target === settingsModal) closeSettingsModal();
});

plot(wavelengths.map(() => 0), LAYOUT_SCAN);
setScanStatus("Ready — press Baseline to begin.");