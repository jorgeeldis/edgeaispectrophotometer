// SPDX-FileCopyrightText: Copyright (C) Arduino s.r.l. and/or its affiliated companies
//
// SPDX-License-Identifier: MPL-2.0

let continuousIntervalId;

const socket = io();
const scanState = {
  baseline: [], // dark-reference reading, per channel
  lastScan: [], // { raw, absorbance, timestamp }
};
darkStd = 0;

socket.on("sendBaseline", (baselineData) => {
  console.log("Received baseline from Arduino:", baselineData);

  // Guard clause: Make sure we actually received valid array data
  if (!baselineData || !Array.isArray(baselineData)) {
    console.error("Expected an array but received:", baselineData);
    // If you kept the payload dictionary style {"value": [...]}, you would do:
    // baselineData = baselineData.value;
  }

  // Store the real sensor array into your state
  scanState.baseline = baselineData;
  maxValue = Math.max(...baselineData);
  minValue = Math.min(...baselineData);
  meanValue = baselineData.reduce((a, b) => a + b, 0) / baselineData.length;
  setScanStatus("Baseline (dark reference) captured from hardware!");

  // Redraw your Plotly graph with the real sensor data array
  Plotly.react(
    TESTER,
    [
      {
        x: wavelengths,
        y: scanState.baseline,
        type: "scatter",
        mode: "lines+markers",
        name: "Absorbance",
        line: { color: "#FFB347", width: 2, shape: "spline" },
        marker: { color: "#FFD08A", size: 5 },
      },
    ],
    RETRO_LAYOUT_BASELINE,
    RETRO_CONFIG,
  );

  document.getElementById("readout-title").textContent = "Peak Amplitude";
  document.getElementById("rd-max").textContent = maxValue.toFixed(4) + "mW @ " + wavelengths[baselineData.indexOf(maxValue)] + " nm";
  document.getElementById("rd-min").textContent = minValue.toFixed(4) + "mW @ " + wavelengths[baselineData.indexOf(minValue)] + " nm";
  document.getElementById("rd-mean").textContent = meanValue.toFixed(4) + "mW";
  document.getElementById("rd-noise").textContent = noiseValue.toFixed(4) + " mW";
  document.getElementById("peak-abs").textContent = maxValue.toFixed(4);
});

socket.on("sendSingleScan", (singleScanData) => {
  console.log("Received single scan from Arduino:", singleScanData);

  // Guard clause: Make sure we actually received valid array data
  if (!singleScanData || !Array.isArray(singleScanData)) {
    console.error("Expected an array but received:", singleScanData);
  }

  // Store the real sensor array into your state
  scanState.lastScan = singleScanData;
  maxValue = Math.max(...singleScanData);
  minValue = Math.min(...singleScanData);
  meanValue = singleScanData.reduce((a, b) => a + b, 0) / singleScanData.length;
  noiseValue = 0;
  setScanStatus("Single scan captured from hardware!");

  // Redraw your Plotly graph with the real sensor data array
  Plotly.react(
    TESTER,
    [
      {
        x: wavelengths,
        y: scanState.lastScan,
        type: "scatter",
        mode: "lines+markers",
        name: "Absorbance",
        line: { color: "#FFB347", width: 2, shape: "spline" },
        marker: { color: "#FFD08A", size: 5 },
      },
    ],
    RETRO_LAYOUT,
    RETRO_CONFIG,
  );
  
  document.getElementById("readout-title").textContent = "Peak Absorbance";
  document.getElementById("rd-max").textContent = maxValue.toFixed(4) + "dB @ " + wavelengths[singleScanData.indexOf(maxValue)] + " nm";
  document.getElementById("rd-min").textContent = minValue.toFixed(4) + "dB @ " + wavelengths[singleScanData.indexOf(minValue)] + " nm";
  document.getElementById("rd-mean").textContent = meanValue.toFixed(4) + "dB";
  document.getElementById("rd-noise").textContent = noiseValue.toFixed(4) + " dB";
  document.getElementById("peak-abs").textContent = maxValue.toFixed(4);
});

socket.on("saveDataResponse", (response) => {
  if (response.success) {
    console.log("Save successful", response);
    setScanStatus("Measurement saved.");
    socket.emit("get_saved_measurements", {});
  } else {
    console.error("Save failed", response.error);
    showError(response.error || "Failed to save measurement.");
  }
});

socket.on("savedMeasurements", (measurements) => {
  renderMeasurementsTable(measurements);
});

socket.on("connect", () => {
  socket.emit("get_saved_measurements", {});
});

const RETRO_LAYOUT_BASELINE = {
  paper_bgcolor: "rgba(0,0,0,0)",
  plot_bgcolor: "rgba(0,0,0,0)",
  margin: { t: 14, l: 52, r: 16, b: 42 },
  autosize: true,
  height: 330,
  font: {
    family: "ui-monospace, Menlo, Consolas, monospace",
    size: 14,
    color: "#8FA98B",
  },
  xaxis: {
    title: { text: "WAVELENGTH (nm)", font: { size: 14 } },
    gridcolor: "rgba(143,169,139,.16)",
    zerolinecolor: "rgba(143,169,139,.3)",
    linecolor: "rgba(143,169,139,.4)",
    tickfont: { size: 14 },
  },
  yaxis: {
    title: { text: "AMPLITUDE (mW/cm)", font: { size: 14 } },
    gridcolor: "rgba(143,169,139,.16)",
    zerolinecolor: "rgba(143,169,139,.3)",
    linecolor: "rgba(143,169,139,.4)",
    tickfont: { size: 14 },
  },
  showlegend: false,
};

const RETRO_LAYOUT = {
  paper_bgcolor: "rgba(0,0,0,0)",
  plot_bgcolor: "rgba(0,0,0,0)",
  margin: { t: 14, l: 52, r: 16, b: 42 },
  autosize: true,
  height: 330,
  font: {
    family: "ui-monospace, Menlo, Consolas, monospace",
    size: 14,
    color: "#8FA98B",
  },
  xaxis: {
    title: { text: "WAVELENGTH (nm)", font: { size: 14 } },
    gridcolor: "rgba(143,169,139,.16)",
    zerolinecolor: "rgba(143,169,139,.3)",
    linecolor: "rgba(143,169,139,.4)",
    tickfont: { size: 14 },
  },
  yaxis: {
    title: { text: "ABSORBANCE (dB)", font: { size: 14 } },
    gridcolor: "rgba(143,169,139,.16)",
    zerolinecolor: "rgba(143,169,139,.3)",
    linecolor: "rgba(143,169,139,.4)",
    tickfont: { size: 14 },
  },
  showlegend: false,
};

const RETRO_CONFIG = { displayModeBar: false, responsive: true };

TESTER = document.getElementById("tester");

// Mock wavelengths (nm) - 14 channels from AS7343
const wavelengths = [
  340, 405, 425, 450, 475, 515, 550, 555, 600, 620, 670, 730, 855, 1000,
];

const scanSettings = {
  name: "Sample 1",
  gain: 1,
  isRef: "No",
  category: "Other",
  known_value: 0,
};

const baselineBtn = document.getElementById("baseline-btn");
const singleScanBtn = document.getElementById("single-scan-btn");
const continuousBtn = document.getElementById("continuous-btn");
const saveDataBtn = document.getElementById("save-data-btn");
const settingsBtn = document.getElementById("settings-btn");
const scanStatus = document.getElementById("scan-status");
const settingsModal = document.getElementById("settings-modal");
const settingsCancelBtn = document.getElementById("settings-cancel-btn");
const settingsSaveBtn = document.getElementById("settings-save-btn");
const integrationTimeInput = document.getElementById(
  "setting-integration-time",
);
const gainSelect = document.getElementById("setting-gain");
const averagingInput = document.getElementById("setting-averaging");

saveDataBtn.disabled = true;
isContinuous = false;

Plotly.newPlot(
  TESTER,
  [
    {
      x: wavelengths,
      y: wavelengths.map(() => 0),
      type: "scatter",
      mode: "lines+markers",
      name: "Absorbance",
      line: { color: "#FFB347", width: 2, shape: "spline" },
      marker: { color: "#FFD08A", size: 5 },
    },
  ],
  RETRO_LAYOUT,
  RETRO_CONFIG,
);

baselineBtn?.addEventListener("click", captureBaseline);
singleScanBtn?.addEventListener("click", runSingleScan);
continuousBtn?.addEventListener("click", toggleContinuousScan);
saveDataBtn?.addEventListener("click", saveData);
settingsSaveBtn?.addEventListener("click", saveSettings);
settingsModal?.addEventListener("click", (e) => {
  if (e.target === settingsModal) closeSettingsModal();
});

function setScanStatus(text) {
  if (scanStatus) scanStatus.textContent = text;
}

function showError(message) {
  console.error(message);
  setScanStatus(message);
}

function captureBaseline() {
  socket.emit("run_arduino_function", {});
}

function runSingleScan() {
  socket.emit("get_single_scan", {});
}

function toggleContinuousScan() {
  document.getElementById("readout-title").textContent = "Peak Absorbance";

  if (continuousBtn.textContent === "Continuous") {
    continuousIntervalId = setInterval(() => {
      socket.emit("get_single_scan", {});
    }, 2000);
    continuousBtn.textContent = "Stop";
  } else {
    clearInterval(continuousIntervalId);
    continuousIntervalId = null;
    continuousBtn.textContent = "Continuous";
  }
}

function saveData() {
  if (!scanState.lastScan || scanState.lastScan.length === 0) {
    return showError("No scan to save — run a Single Scan first.");
  }
  if (!scanSettings.name || !scanSettings.category) {
    return showError("Set a name and category in Settings before saving.");
  }

  const isReference = scanSettings.isRef && scanSettings.isRef.toString().toLowerCase() === "yes";

  socket.emit("save_scan_data", {
    created_at: new Date().toISOString(),
    name: scanSettings.name,
    category: scanSettings.category,
    baseline_id: null,
    raw_counts: scanState.lastScan,
    saturated: 0,
    is_reference: isReference ? 1 : 0,
    known_value: isReference ? 0 : scanSettings.known_value,
  });
}

function renderMeasurementsTable(measurements) {
  const tbody = document.getElementById("measures-body");
  if (!tbody) return;

  tbody.innerHTML = "";

  measurements.forEach((measurement) => {
    const rawCounts = Array.isArray(measurement.raw_counts)
      ? measurement.raw_counts
      : JSON.parse(measurement.raw_counts || "[]");

    const row = document.createElement("tr");
    const nameCell = document.createElement("th");
    nameCell.setAttribute("scope", "row");
    nameCell.textContent = measurement.name || "Unnamed";
    row.appendChild(nameCell);

    rawCounts.slice(0, 12).forEach((value) => {
      const cell = document.createElement("td");
      cell.textContent = typeof value === "number" ? value.toFixed(2) : value;
      row.appendChild(cell);
    });

    tbody.appendChild(row);
  });
}

function saveSettings() {
  scanSettings.name = document.getElementById("setting-name").value;
  scanSettings.gain = document.getElementById("setting-gain").value;
  scanSettings.isRef = document.getElementById("setting-reference").value;
  scanSettings.category = document.getElementById("setting-category").value;
  scanSettings.known_value = parseFloat(document.getElementById("setting-known-value").value) || 0;
  document.getElementById("rd-name").textContent = scanSettings.name;
  document.getElementById("rd-gain").textContent = scanSettings.gain + "x";
  document.getElementById("rd-ref").textContent = scanSettings.isRef ? "YES" : "NO";
  document.getElementById("rd-category").textContent = scanSettings.category;
  console.log("Settings updated: ", scanSettings);
}

function switchTab(event, tabId) {
  // Hide all content panels
  const panels = document.querySelectorAll(".tab-panel");
  panels.forEach((panel) => panel.classList.remove("active"));

  // Remove the active class from all buttons
  const buttons = document.querySelectorAll(".tab-btn");
  buttons.forEach((btn) => btn.classList.remove("active"));

  // Show the specific clicked panel and mark button as active
  document.getElementById(tabId).classList.add("active");
  event.currentTarget.classList.add("active");
}

function onUIConnected() {
  console.log("UI connected");
  socket.emit("get_saved_measurements", {});
}

function onUIDisconnected() {
  console.log("UI disconnected");
}

function closeSettingsModal() {
  if (!settingsModal) return;
  if (settingsModal.classList.contains("show")) {
    settingsModal.classList.remove("show");
  }
}

const ui = new WebUI();
ui.on_connect(onUIConnected);
ui.on_disconnect(onUIDisconnected);

function switchSubTab(event, panelId) {
  const container = event.currentTarget.closest(".tab-panel");
  container.querySelectorAll(".subtab-panel").forEach((p) => p.classList.remove("active"));
  container.querySelectorAll(".subtab-btn").forEach((b) => b.classList.remove("active"));
  container.querySelector("#" + panelId).classList.add("active");
  event.currentTarget.classList.add("active");
}