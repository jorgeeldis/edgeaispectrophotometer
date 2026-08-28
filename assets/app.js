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
noiseValue = 0;

socket.on("sendBaseline", (baselineData) => {
  console.log("Received baseline from Arduino:", baselineData);

  if (!baselineData || !Array.isArray(baselineData)) {
    console.error("Expected an array but received:", baselineData);
    return;
  }

  scanState.baseline = baselineData;
  maxValue = Math.max(...baselineData);
  minValue = Math.min(...baselineData);
  meanValue = baselineData.reduce((a, b) => a + b, 0) / baselineData.length;
  setScanStatus("Baseline (dark reference) captured from hardware!");

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
  document.getElementById("rd-max").textContent =
    maxValue.toFixed(4) +
    " counts @ " +
    wavelengths[baselineData.indexOf(maxValue)] +
    " nm";
  document.getElementById("rd-min").textContent =
    minValue.toFixed(4) +
    " counts @ " +
    wavelengths[baselineData.indexOf(minValue)] +
    " nm";
  document.getElementById("rd-mean").textContent = meanValue.toFixed(4) + " counts";
  document.getElementById("rd-noise").textContent =
    noiseValue.toFixed(4) + " counts";
  document.getElementById("peak-abs").textContent = maxValue.toFixed(4);
});

socket.on("sendSingleScan", (payload) => {
  console.log("Received single scan from Arduino:", payload);

  // Backend now sends { values, saturated } instead of a bare array, so a
  // saturated channel (fully opaque sample) can be flagged instead of
  // silently misreported as 0 absorbance.
  const singleScanData = payload?.values;

  // Guard clause: Make sure we actually received valid array data
  if (!singleScanData || !Array.isArray(singleScanData)) {
    console.error("Expected { values: [...] } but received:", payload);
    return;
  }

  // Store the real sensor array into your state
  scanState.lastScan = singleScanData;
  scanState.saturated = !!payload.saturated;
  saveDataBtn.disabled = false;
  maxValue = Math.max(...singleScanData);
  minValue = Math.min(...singleScanData);
  meanValue = singleScanData.reduce((a, b) => a + b, 0) / singleScanData.length;
  noiseValue = 0;
  setScanStatus(
    scanState.saturated
      ? "Single scan captured — one or more channels saturated (sample may be too concentrated/opaque for this gain)."
      : "Single scan captured from hardware!"
  );

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
  document.getElementById("rd-max").textContent =
    maxValue.toFixed(4) +
    "AU @ " +
    wavelengths[singleScanData.indexOf(maxValue)] +
    " nm";
  document.getElementById("rd-min").textContent =
    minValue.toFixed(4) +
    "AU @ " +
    wavelengths[singleScanData.indexOf(minValue)] +
    " nm";
  document.getElementById("rd-mean").textContent = meanValue.toFixed(4) + "AU";
  document.getElementById("rd-noise").textContent =
    noiseValue.toFixed(4) + " AU";
  document.getElementById("peak-abs").textContent = maxValue.toFixed(4);
});

socket.on("scanError", (payload) => {
  showError(payload?.message || "Scan failed.");
});

socket.on("savedMeasurements", (rows) => {
  renderMeasurementsTable(rows || []);
});

socket.on("saveDataResponse", (response) => {
  if (response.success) {
    console.log("Save successful", response);
    setScanStatus("Measurement saved.");
    socket.emit("get_saved_measurements", {});
    socket.emit("get_analysis", {});
  } else {
    console.error("Save failed", response.error);
    showError(response.error || "Failed to save measurement.");
  }
});

const analysisCategory = { value: "Other" };
const analysisSelect = document.getElementById("analysis-category");

analysisSelect.addEventListener("change", (e) => {
  analysisCategory.value = e.target.value;
  socket.emit("get_analysis", { category: analysisCategory.value });
});

socket.on("connect", () => {
  socket.emit("get_saved_measurements", {});
  socket.emit("get_analysis", { category: analysisCategory.value });
  socket.emit("get_reports", {});
  socket.emit("get_maintenance_status", {});
});

let analysisRows = [];

// Renders whatever compute_calibration_health() last sent. Only status,
// scan_counter, and dark_reference_age_hours are derived from real state on
// the backend — temperature/LED hours/drift are prototype placeholders (see
// main.py), rendered here exactly the same as the live fields.
function updateMaintenanceStatus(status) {
  const panel = document.getElementById("maintenance-status");
  if (panel) panel.textContent = status?.status || "healthy";
  const temp = document.getElementById("maintenance-temp");
  if (temp) temp.textContent = `${status?.temperature_c ?? 31.4} °C`;
  const led = document.getElementById("maintenance-led-hours");
  if (led) led.textContent = `${status?.led_hours ?? 142} h`;
  const fw = document.getElementById("maintenance-firmware");
  if (fw) fw.textContent = `${status?.firmware_version || "v0.4.1"}`;
  const age = document.getElementById("maintenance-dark-age");
  if (age) age.textContent = `${status?.dark_reference_age_hours ?? 18} h`;
  const drift = document.getElementById("maintenance-drift");
  if (drift) drift.textContent = `${status?.baseline_drift_percent ?? 1.4} %`;
  const service = document.getElementById("maintenance-service");
  if (service) service.textContent = `~${Math.max(0, 30 - (status?.dark_reference_age_hours ?? 18))} h`;
  const sensor = document.getElementById("maintenance-sensor");
  if (sensor) sensor.textContent = `${status?.sensor_health ?? "healthy"}`;

  const calLamp = document.getElementById("lamp-cal");
  if (calLamp) {
    const calClass = status?.status === "warning" ? "alert"
      : status?.status === "attention" ? "warn" : "on";
    calLamp.className = `lamp ${calClass}`;
  }
  const sensorLamp = document.getElementById("lamp-sensor");
  if (sensorLamp) {
    sensorLamp.className = `lamp ${status?.sensor_health === "healthy" ? "on" : "alert"}`;
  }
}

socket.on("maintenanceStatus", (status) => {
  updateMaintenanceStatus(status || {});
});

function appendChatMessage(role, text) {
  const log = document.getElementById("chat-log");
  if (!log) return;
  const line = document.createElement("div");
  line.style.marginBottom = "8px";
  line.textContent = `${role}: ${text}`;
  log.appendChild(line);
  log.scrollTop = log.scrollHeight;
}

socket.on("chatResponse", (payload) => {
  appendChatMessage("Assistant", payload?.content || "No response received.");
});

socket.on("buildReferenceResponse", (payload) => {
  if (!payload || !payload.success) {
    setAnalysisNote(payload?.reason || "Reference build failed.");
    return;
  }
  setAnalysisNote(`Reference built for ${payload.category} with ${payload.n_samples} replicates.`);
  socket.emit("get_analysis", { category: analysisCategory.value });
});

socket.on("sanityPlotResponse", (payload) => {
  renderSanityPlot(payload);
  if (!payload || !payload.levels) {
    setAnalysisNote(payload?.reason || "Sanity plot failed.");
    return;
  }
  setAnalysisNote(
    payload.success
      ? `Sanity plot passed: R² = ${payload.r2} for ${payload.category}.`
      : (payload.reason || `Sanity plot: R² = ${payload.r2} for ${payload.category}.`)
  );
});

function renderSanityPlot(payload) {
  const host = document.getElementById("sanity-plot-host");
  if (!host) return;
  // The backend only includes levels/signal once it has enough data to fit
  // a line at all — below that threshold there's nothing meaningful to
  // plot, so the chart stays hidden rather than showing an empty/broken one.
  if (!payload || !payload.levels || !payload.levels.length) {
    host.style.display = "none";
    return;
  }

  host.style.display = "block";
  const xs = payload.levels;
  const ys = payload.signal;
  const lineXs = [Math.min(...xs), Math.max(...xs)];
  const lineYs = lineXs.map((x) => payload.fit_slope * x + payload.fit_intercept);

  Plotly.react(
    "sanity-plot",
    [
      {
        x: xs, y: ys, type: "scatter", mode: "markers", name: "Measured",
        marker: { color: "#FFD08A", size: 9 },
      },
      {
        x: lineXs, y: lineYs, type: "scatter", mode: "lines", name: "Fit",
        line: { color: "#FFB347", width: 2 },
      },
    ],
    RETRO_LAYOUT_SANITY,
    RETRO_CONFIG,
  );
}

socket.on("trainModelResponse", (payload) => {
  if (!payload || !payload.success) {
    setAnalysisNote(payload?.reason || "Model training failed.");
    return;
  }
  setAnalysisNote(`Model trained for ${payload.category}: R² ${payload.r2}, RMSE ${payload.rmse}.`);
  socket.emit("get_analysis", { category: analysisCategory.value });
});

socket.on("reportsData", (rows) => {
  renderReports(rows || []);
});

socket.on("reportSaved", (payload) => {
  if (payload?.success) {
    setAnalysisNote(`Report saved for ${payload.category}.`);
    socket.emit("get_reports", {});
  } else {
    setAnalysisNote(payload?.error || "Report export failed.");
  }
});

function updateReportViewer(report) {
  const title = document.getElementById("report-viewer-title");
  if (title) {
    title.textContent = report
      ? `${report.type || "Report"} — ${report.category || "—"} — ${report.created_at ? new Date(report.created_at).toLocaleString() : "—"}`
      : "No report selected";
  }

  const link = document.getElementById("report-open-link");
  if (!link) return;
  if (report?.path) {
    link.href = report.path;
    link.style.display = "inline-block";
  } else {
    link.removeAttribute("href");
    link.style.display = "none";
  }
}

function renderReports(rows) {
  const tbody = document.getElementById("reports-body");
  const preview = document.getElementById("pdf-preview");

  if (!tbody) return;
  if (!rows.length) {
    tbody.innerHTML = `<tr><td colspan="2" style="text-align:center">No reports available.</td></tr>`;
    if (preview) preview.srcdoc = "<html><body style='font-family:monospace;padding:24px'>No report selected.</body></html>";
    updateReportViewer(null);
    return;
  }

  tbody.innerHTML = rows.map((r, i) => `
    <tr data-report-id="${r.id}" class="report-row ${i === 0 ? "selected" : ""}">
      <th scope="row">${r.type || `RPT-${String(r.id).padStart(4, "0")}`}</th>
      <td>${r.created_at ? new Date(r.created_at).toLocaleString() : "—"}</td>
    </tr>
  `).join("");

  tbody.querySelectorAll(".report-row").forEach((row) => {
    row.addEventListener("click", () => {
      tbody.querySelectorAll(".report-row").forEach((el) => el.classList.remove("selected"));
      row.classList.add("selected");
      const report = rows.find((item) => Number(item.id) === Number(row.dataset.reportId));
      if (preview) {
        // report.path is a relative URL like "reports/water_....html" — the
        // file was written directly into assets/reports/ by the backend, and
        // WebUI serves assets/ from disk, so it's already fetchable with no
        // extra route.
        if (report?.path) {
          preview.src = report.path;
        } else {
          preview.srcdoc = "<html><body style='font-family:monospace;padding:20px'>Report file not found.</body></html>";
        }
      }
      updateReportViewer(report);
    });
  });

  const first = tbody.querySelector(".report-row");
  first?.dispatchEvent(new Event("click"));
}

const buildReferenceBtn = document.getElementById("build-ref-btn");
const sanityPlotBtn = document.getElementById("sanity-plot-btn");
const trainSamplesBtn = document.getElementById("train-samples-btn");
const exportReportBtn = document.getElementById("export-analysis-btn");

buildReferenceBtn?.addEventListener("click", () => {
  socket.emit("build_reference", { category: analysisCategory.value });
});

sanityPlotBtn?.addEventListener("click", () => {
  socket.emit("sanity_plot", { category: analysisCategory.value });
});

trainSamplesBtn?.addEventListener("click", () => {
  socket.emit("train_model", { category: analysisCategory.value });
});

exportReportBtn?.addEventListener("click", () => {
  socket.emit("export_report", { category: analysisCategory.value });
});

document.getElementById("chat-send-btn")?.addEventListener("click", () => {
  const input = document.getElementById("chat-input");
  const question = input?.value?.trim();
  if (!question) return;
  appendChatMessage("User", question);
  input.value = "";
  socket.emit("chat_send", { question, category: analysisCategory.value });
});

const chatInput = document.getElementById("chat-input");
chatInput?.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    document.getElementById("chat-send-btn")?.click();
  }
});

const setAnalysisNote = (t) =>
  (document.getElementById("analysis-note").textContent = t || "");

document.getElementById("select-all").addEventListener("change", (e) => {
  const boxes = document.querySelectorAll("#analysis-body .row-sel");
  boxes.forEach(cb => (cb.checked = e.target.checked));
  boxes[0]?.dispatchEvent(new Event("change"));
});

socket.on("analysisData", (rows) => {
  analysisRows = rows;
  renderAnalysisTable(rows);
  renderMetrics([]);
});

function renderAnalysisTable(rows) {
  const tbody = document.getElementById("analysis-body");
  const cls = { PASS: "pass", ATTENTION: "warn", REJECT: "reject" };

  if (!rows.length) {
    tbody.innerHTML = `<tr><td colspan="7" style="text-align:center">
      No measurements in this category.</td></tr>`;
    return;
  }

  tbody.innerHTML = rows.map(r => `
    <tr>
      <td><input type="checkbox" class="row-sel" data-id="${r.id}"></td>
      <td>${r.name}${r.is_reference ? " ★" : ""}</td>
      <td>${r.category}</td>
      <td>${r.dev ?? "—"}</td>
      <td>${r.pred ?? "—"}</td>
      <td>${r.conf ?? "—"}</td>
      <td class="${cls[r.status] ?? ""}">${r.status ?? "—"}</td>
    </tr>`).join("");

  tbody.querySelectorAll(".row-sel").forEach(cb =>
    cb.addEventListener("change", () => {
      const ids = [...tbody.querySelectorAll(".row-sel:checked")]
        .map(c => Number(c.dataset.id));
      renderMetrics(analysisRows.filter(r => ids.includes(r.id)));
    })
  );
}

function renderMetrics(sel) {
  const host = document.getElementById("metrics-host");

  if (!sel.length) {
    host.innerHTML = `<h3>Metrics</h3><div class="metric-card-analysis">
      <p><strong>No selection</strong></p>
      <p>Select rows to compute metrics.</p></div>`;
    return;
  }

  if (sel.length === 1) {
    const r = sel[0];
    host.innerHTML = `<h3>Single-Level Metrics</h3><div class="metric-card-analysis">
      <p><strong>${r.name}</strong></p>
      <p>Deviation <strong>${r.dev ?? "—"} σ</strong></p>
      <p>Prediction <strong>${r.pred ?? "—"}</strong></p>
      <p>Confidence <strong>${r.conf ?? "—"}</strong></p>
      <p>Known value <strong>${r.known_value ?? "—"}</strong></p>
      <p>Status <strong>${pill(r.status)}</strong></p></div>`;
    return;
  }

  const devs = sel.map(r => r.dev).filter(v => v != null);
  const mean = devs.length ? devs.reduce((a, b) => a + b, 0) / devs.length : null;
  const anom = sel.filter(r => r.status === "REJECT").length;
  const worst = devs.length ? Math.max(...devs) : null;

  // quality score falls off with mean deviation; 0σ = 100%, 3σ = 0%
  const score = mean == null ? null : Math.max(0, Math.round(100 - (mean / 3) * 100));
  const status = score == null ? null
    : score >= 80 ? "PASS" : score >= 50 ? "ATTENTION" : "REJECT";

  host.innerHTML = `<h3>Batch-Level Metrics</h3><div class="metric-card-analysis">
    <p><strong>Batch — ${sel.length} measurements</strong></p>
    <p>Quality Score <strong>${score == null ? "—" : score + "%"}</strong></p>
    <p>Status <strong>${pill(status)}</strong></p>
    <p>Mean Deviation <strong>${mean == null ? "—" : mean.toFixed(2) + " σ"}</strong></p>
    <p>Worst Deviation <strong>${worst == null ? "—" : worst.toFixed(2) + " σ"}</strong></p>
    <p>Anomalies <strong>${anom}</strong></p></div>`;
}

function pill(s) {
  const m = { PASS: "good", ATTENTION: "attention", REJECT: "critical" };
  return s ? `<span class="pill ${m[s]}">${s}</span>` : "—";
}

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
    title: { text: "RAW COUNTS", font: { size: 14 } },
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
    title: { text: "ABSORBANCE (AU)", font: { size: 14 } },
    gridcolor: "rgba(143,169,139,.16)",
    zerolinecolor: "rgba(143,169,139,.3)",
    linecolor: "rgba(143,169,139,.4)",
    tickfont: { size: 14 },
  },
  showlegend: false,
};

const RETRO_LAYOUT_SANITY = {
  paper_bgcolor: "rgba(0,0,0,0)",
  plot_bgcolor: "rgba(0,0,0,0)",
  margin: { t: 14, l: 60, r: 16, b: 42 },
  autosize: true,
  height: 260,
  font: {
    family: "ui-monospace, Menlo, Consolas, monospace",
    size: 14,
    color: "#8FA98B",
  },
  xaxis: {
    title: { text: "KNOWN VALUE", font: { size: 14 } },
    gridcolor: "rgba(143,169,139,.16)",
    zerolinecolor: "rgba(143,169,139,.3)",
    linecolor: "rgba(143,169,139,.4)",
    tickfont: { size: 14 },
  },
  yaxis: {
    title: { text: "SIGNAL (SUM)", font: { size: 14 } },
    gridcolor: "rgba(143,169,139,.16)",
    zerolinecolor: "rgba(143,169,139,.3)",
    linecolor: "rgba(143,169,139,.4)",
    tickfont: { size: 14 },
  },
  showlegend: true,
};

const RETRO_CONFIG = { displayModeBar: false, responsive: true };

TESTER = document.getElementById("tester");

// Wavelengths (nm) for the 12 AS7343 channels used by the firmware:
// F1, F2, FZ, F3, F4, F5, FY, FXL, F6, F7, F8, NIR
const wavelengths = [
  405, 425, 450, 475, 515, 550, 555, 600, 640, 690, 745, 855,
];

const scanSettings = {
  name: "Sample 1",
  gain: 1,
  isRef: "No",
  category: "Other",
  known_value: null,
};

const baselineBtn = document.getElementById("baseline-btn");
const singleScanBtn = document.getElementById("single-scan-btn");
const continuousBtn = document.getElementById("continuous-btn");
const saveDataBtn = document.getElementById("save-data-btn");
const scanStatus = document.getElementById("scan-status");
const settingsSaveBtn = document.getElementById("settings-save-btn");

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
    // 2000ms matches the firmware's own acquisition cadence — polling
    // faster wouldn't surface new data any sooner, since record_sensor_samples
    // only lands a fresh reading about once every 2 seconds.
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

  const isReference =
    scanSettings.isRef && scanSettings.isRef.toString().toLowerCase() === "yes";

  const payload = {
    created_at: new Date().toISOString(),
    name: scanSettings.name,
    category: scanSettings.category,
    baseline_id: null,
    raw_counts: scanState.lastScan,
    saturated: scanState.saturated ? 1 : 0,
    is_reference: isReference ? 1 : 0,
    // A reference sample is always the 0% point of its dilution series.
    // For anything else, known_value stays whatever Settings left it —
    // null if the operator left it blank (an unlabeled quick scan), not 0.
    known_value: isReference ? 0 : scanSettings.known_value,
  };

  console.log("Sending save_scan_data payload", payload);
  socket.emit("save_scan_data", payload);
}

function renderMeasurementsTable(measurements) {
  const tbody = document.getElementById("measures-body");

  // 3. Loop through data and build HTML rows using .map() and .join()
  tbody.innerHTML = measurements
    .map((item) => {
      // Convert the string array "[1,2,3...]" into a real JavaScript array
      const counts = JSON.parse(item.raw_counts);
      return `
        <tr>
            <td>${item.id}</td>
            <td>${item.name}</td>
            ${
              /* Slice indices 1 to 12 and turn them into <td> elements */
              counts
                .slice(0, 13)
                .map((count) => `<td>${count.toFixed(2) ?? ""}</td>`)
                .join("")
            }
        </tr>
    `;
    })
    .join("");
}

function saveSettings() {
  scanSettings.name = document.getElementById("setting-name").value;
  scanSettings.gain = document.getElementById("setting-gain").value;
  scanSettings.isRef = document.getElementById("setting-reference").value;
  scanSettings.category = document.getElementById("setting-category").value;
  const knownValueRaw = document.getElementById("setting-known-value")?.value?.trim();
  const parsedKnownValue = knownValueRaw ? parseFloat(knownValueRaw) : NaN;
  scanSettings.known_value = Number.isNaN(parsedKnownValue) ? null : parsedKnownValue;
  document.getElementById("rd-name").textContent = scanSettings.name;
  document.getElementById("rd-gain").textContent = scanSettings.gain + "x";
  document.getElementById("rd-ref").textContent = scanSettings.isRef
    ? "YES"
    : "NO";
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

socket.on("disconnect", () => {
  console.log("Socket disconnected");
});

function switchSubTab(event, panelId) {
  const container = event.currentTarget.closest(".tab-panel");
  container
    .querySelectorAll(".subtab-panel")
    .forEach((p) => p.classList.remove("active"));
  container
    .querySelectorAll(".subtab-btn")
    .forEach((b) => b.classList.remove("active"));
  container.querySelector("#" + panelId).classList.add("active");
  event.currentTarget.classList.add("active");
}
