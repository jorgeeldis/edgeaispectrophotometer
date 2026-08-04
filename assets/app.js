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
  integrationTimeMs: 100,
  gain: 1,
  averaging: 1,
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
saveDataBtn?.addEventListener("click", saveDataAsCsv);
settingsSaveBtn?.addEventListener("click", saveSettings);
settingsModal?.addEventListener("click", (e) => {
  if (e.target === settingsModal) closeSettingsModal();
});

function setScanStatus(text) {
  if (scanStatus) scanStatus.textContent = text;
}

function captureBaseline() {
  socket.emit("run_arduino_function", {});
  console.log("Max Value: ", maxValue);
  console.log("Min Value: ", minValue);
  console.log("Mean Value: ", meanValue);
  console.log("Noise Value: ", noiseValue);
  document.getElementById("readout-title").textContent = "Peak Amplitude";
  document.getElementById("rd-max").textContent = "Max: " + maxValue.toFixed(4) + "mW @ " + wavelengths[baselineData.indexOf(maxValue)] + " nm";
  document.getElementById("rd-min").textContent = "Min: " + minValue.toFixed(4) + "mW @ " + wavelengths[baselineData.indexOf(minValue)] + " nm";
  document.getElementById("rd-mean").textContent = "Mean: " + meanValue.toFixed(4) + "mW";
  document.getElementById("rd-noise").textContent = "Noise: " + noiseValue.toFixed(4) + " mW";
  document.getElementById("peak-abs").textContent = maxValue.toFixed(4);

}

function runSingleScan() {
  socket.emit("get_single_scan", {});
  console.log("Max Value: ", maxValue);
  console.log("Min Value: ", minValue);
  console.log("Mean Value: ", meanValue);
  console.log("Noise Value: ", noiseValue);
  document.getElementById("readout-title").textContent = "Peak Absorbance";
  document.getElementById("rd-max").textContent = "Max: " + maxValue.toFixed(4) + "dB @ " + wavelengths[singleScanData.indexOf(maxValue)] + " nm";
  document.getElementById("rd-min").textContent = "Min: " + minValue.toFixed(4) + "dB @ " + wavelengths[singleScanData.indexOf(minValue)] + " nm";
  document.getElementById("rd-mean").textContent = "Mean: " + meanValue.toFixed(4) + "dB";
  document.getElementById("rd-noise").textContent = "Noise: " + noiseValue.toFixed(4) + " dB";
  document.getElementById("peak-abs").textContent = maxValue.toFixed(4);

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

function saveDataAsCsv() {
  if (!scanState.lastScan) return;

  const { raw, absorbance, timestamp } = scanState.lastScan;
  const rows = ["Wavelength (nm),Raw Signal,Absorbance (dB)"];
  wavelengths.forEach((w, i) => {
    rows.push(`${w},${raw[i].toFixed(4)},${absorbance[i].toFixed(4)}`);
  });

  const blob = new Blob([rows.join("\n")], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `scan-${timestamp.toISOString().replace(/[:.]/g, "-")}.csv`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
  setScanStatus("Scan data saved to CSV");
}

function saveSettings() {
  scanSettings.integrationTimeMs =
    Number(integrationTimeInput.value) || scanSettings.integrationTimeMs;
  scanSettings.gain = Number(gainSelect.value) || scanSettings.gain;
  scanSettings.averaging = Math.max(
    1,
    Number(averagingInput.value) || scanSettings.averaging,
  );
  console.log("Settings updated");
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

const ui = new WebUI();
ui.on_connect(onUIConnected);
ui.on_disconnect(onUIDisconnected);
