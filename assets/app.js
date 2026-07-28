// SPDX-FileCopyrightText: Copyright (C) Arduino s.r.l. and/or its affiliated companies
//
// SPDX-License-Identifier: MPL-2.0
const RETRO_LAYOUT = {
  paper_bgcolor: 'rgba(0,0,0,0)',
  plot_bgcolor:  'rgba(0,0,0,0)',
  margin: { t: 14, l: 52, r: 16, b: 42 },
  autosize: true,
  height: 330,
  font: { family: 'ui-monospace, Menlo, Consolas, monospace', size: 14, color: '#8FA98B' },
  xaxis: {
    title: { text: 'WAVELENGTH (nm)', font: { size: 14 } },
    gridcolor: 'rgba(143,169,139,.16)',
    zerolinecolor: 'rgba(143,169,139,.3)',
    linecolor: 'rgba(143,169,139,.4)',
    tickfont: { size: 14 }
  },
  yaxis: {
    title: { text: 'ABSORBANCE (dB)', font: { size: 14 } },
    gridcolor: 'rgba(143,169,139,.16)',
    zerolinecolor: 'rgba(143,169,139,.3)',
    linecolor: 'rgba(143,169,139,.4)',
    tickfont: { size: 14 }
  },
  showlegend: false
};

const RETRO_CONFIG = { displayModeBar: false, responsive: true };

TESTER = document.getElementById('tester');

// Mock wavelengths (nm) - 14 channels from AS7343
const wavelengths = [380, 395, 410, 435, 460, 485, 510, 535, 560, 585, 610, 645, 680, 705];

const scanState = {
  baseline: null, // dark-reference reading, per channel
  lastScan: null, // { raw, absorbance, timestamp }
  continuousInterval: null,
};

const scanSettings = {
  integrationTimeMs: 100,
  gain: 1,
  averaging: 1,
};

Plotly.newPlot(TESTER, [{
  x: wavelengths,
  y: wavelengths.map(() => 0),
  type: 'scatter',
  mode: 'lines+markers',
  name: 'Absorbance',
  line: { color: '#FFB347', width: 2, shape: 'spline' },
  marker: { color: '#FFD08A', size: 5 },
}], RETRO_LAYOUT, RETRO_CONFIG);

const baselineBtn = document.getElementById('baseline-btn');
const singleScanBtn = document.getElementById('single-scan-btn');
const continuousBtn = document.getElementById('continuous-btn');
const saveDataBtn = document.getElementById('save-data-btn');
const settingsBtn = document.getElementById('settings-btn');
const scanStatus = document.getElementById('scan-status');

const settingsModal = document.getElementById('settings-modal');
const settingsCancelBtn = document.getElementById('settings-cancel-btn');
const settingsSaveBtn = document.getElementById('settings-save-btn');
const integrationTimeInput = document.getElementById('setting-integration-time');
const gainSelect = document.getElementById('setting-gain');
const averagingInput = document.getElementById('setting-averaging');

saveDataBtn.disabled = true;

baselineBtn?.addEventListener('click', captureBaseline);
singleScanBtn?.addEventListener('click', runSingleScan);
continuousBtn?.addEventListener('click', toggleContinuousScan);
saveDataBtn?.addEventListener('click', saveDataAsCsv);
settingsBtn?.addEventListener('click', openSettingsModal);
settingsCancelBtn?.addEventListener('click', closeSettingsModal);
settingsSaveBtn?.addEventListener('click', saveSettings);
settingsModal?.addEventListener('click', e => {
  if (e.target === settingsModal) closeSettingsModal();
});

function plotLayout(title) {
  return {
    margin: { t: 20, l: 30, r: 20, b: 20 },
    title,
    xaxis: { title: 'Wavelength (nm)' },
    yaxis: { title: 'Absorbance (dB)' },
  };
}

function setScanStatus(text) {
  if (scanStatus) scanStatus.textContent = text;
}

// Simulates one raw sensor reading across all 14 AS7343 channels,
// shaped by the current gain/integration-time/averaging settings.
function readSensorChannels() {
  const noiseScale = 0.08 / Math.sqrt(scanSettings.integrationTimeMs / 100);
  const sums = wavelengths.map(() => 0);
  for (let s = 0; s < scanSettings.averaging; s++) {
    wavelengths.forEach((_, i) => {
      const peak = 0.5 - Math.abs(i - wavelengths.length / 2) * 0.02;
      const noise = (Math.random() - 0.5) * noiseScale;
      sums[i] += Math.max(0, (peak + noise) * scanSettings.gain);
    });
  }
  return sums.map(v => v / scanSettings.averaging);
}

function computeAbsorbance(raw) {
  if (!scanState.baseline) return raw;
  return raw.map((v, i) => v - scanState.baseline[i]);
}

function captureBaseline() {
  scanState.baseline = readSensorChannels();
  setScanStatus('Baseline (dark reference) captured');
  Plotly.react(TESTER, [{
    x: wavelengths,
    y: scanState.baseline,
    type: 'scatter',
    mode: 'lines+markers',
    name: 'Baseline',
  }], plotLayout('Baseline Scan'));
}

function runSingleScan() {
  const raw = readSensorChannels();
  const absorbance = computeAbsorbance(raw);
  scanState.lastScan = { raw, absorbance, timestamp: new Date() };
  saveDataBtn.disabled = false;
  setScanStatus(
    scanState.baseline
      ? 'Single scan complete (baseline-corrected)'
      : 'Single scan complete (no baseline captured)'
  );
  Plotly.react(TESTER, [{
    x: wavelengths,
    y: absorbance,
    type: 'scatter',
    mode: 'lines+markers',
    name: 'Single Scan',
  }], plotLayout('Single Scan'));
}

function toggleContinuousScan() {
  if (scanState.continuousInterval) {
    stopContinuousScan();
    return;
  }

  setScanStatus('Continuous scan running...');
  continuousBtn.textContent = 'STOP CONTINUOUS';
  scanState.continuousInterval = setInterval(() => {
    const raw = readSensorChannels();
    const absorbance = computeAbsorbance(raw);
    scanState.lastScan = { raw, absorbance, timestamp: new Date() };
    saveDataBtn.disabled = false;
    Plotly.react(TESTER, [{
      x: wavelengths,
      y: absorbance,
      type: 'scatter',
      mode: 'lines+markers',
      name: 'Continuous Scan',
    }], plotLayout('Continuous Scan'));
  }, 500);
}

function stopContinuousScan() {
  clearInterval(scanState.continuousInterval);
  scanState.continuousInterval = null;
  continuousBtn.textContent = 'CONTINUOUS SCAN';
  setScanStatus('Continuous scan stopped');
}

function saveDataAsCsv() {
  if (!scanState.lastScan) return;

  const { raw, absorbance, timestamp } = scanState.lastScan;
  const rows = ['Wavelength (nm),Raw Signal,Absorbance (dB)'];
  wavelengths.forEach((w, i) => {
    rows.push(`${w},${raw[i].toFixed(4)},${absorbance[i].toFixed(4)}`);
  });

  const blob = new Blob([rows.join('\n')], { type: 'text/csv' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `scan-${timestamp.toISOString().replace(/[:.]/g, '-')}.csv`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
  setScanStatus('Scan data saved to CSV');
}

function openSettingsModal() {
  console.log("hi")
  integrationTimeInput.value = scanSettings.integrationTimeMs;
  gainSelect.value = scanSettings.gain;
  averagingInput.value = scanSettings.averaging;
  settingsModal.classList.remove('hidden');
}

function closeSettingsModal() {
  settingsModal.classList.add('hidden');
}

function saveSettings() {
  scanSettings.integrationTimeMs = Number(integrationTimeInput.value) || scanSettings.integrationTimeMs;
  scanSettings.gain = Number(gainSelect.value) || scanSettings.gain;
  scanSettings.averaging = Math.max(1, Number(averagingInput.value) || scanSettings.averaging);
  closeSettingsModal();
  setScanStatus('Settings updated');
}
const ui = new WebUI();
ui.on_connect(onUIConnected);
ui.on_disconnect(onUIDisconnected);

const OFF_COLOR = '#DAE3E3';
const ledState = {
  1: { color: '#FFFFFF', isOn: true },
  2: { color: '#FFFFFF', isOn: true },
  3: { color: '#FFFFFF', isOn: true },
  4: { color: '#FFFFFF', isOn: true },
};

setupPaletteLED(1);
setupPaletteLED(2);
setupColorPickerLED(3);
setupPaletteLED(4);

function onUIConnected() {
  const errorContainer = document.getElementById('error-container');
  if (errorContainer) {
    errorContainer.style.display = 'none';
  }
  // Re-sync all LEDs with the current UI state on every (re)connect,
  // so the physical LEDs always match the UI after an app restart.
  for (const ledNumber in ledState) {
    const state = ledState[ledNumber];
    if (state.isOn) {
      const rgb = hexToRgb(state.color);
      ui.send_message('set_color', { led: parseInt(ledNumber), color: rgb });
    } else {
      ui.send_message('set_color', {
        led: parseInt(ledNumber),
        color: { r: 0, g: 0, b: 0 },
      });
    }
  }
}

function onUIDisconnected() {
  const errorContainer = document.getElementById('error-container');
  if (errorContainer) {
    errorContainer.textContent = 'Connection to the board lost. Please check the connection.';
    errorContainer.style.display = 'block';
  }
}

function setupPaletteLED(ledNumber) {
  const switchEl = document.getElementById(`led${ledNumber}-switch`);
  const palette = document.getElementById(`led${ledNumber}-palette`);
  const circle = document.getElementById(`led${ledNumber}-circle`);
  if (!switchEl || !palette || !circle) return;

  switchEl.addEventListener('change', e => {
    ledState[ledNumber].isOn = e.target.checked;
    if (ledState[ledNumber].isOn) {
      updateColor(ledNumber, ledState[ledNumber].color);
    } else {
      ui.send_message('set_color', {
        led: ledNumber,
        color: { r: 0, g: 0, b: 0 },
      });
      circle.style.backgroundColor = OFF_COLOR;
    }
  });

  palette.addEventListener('click', e => {
    if (e.target.classList.contains('color-square')) {
      if (ledState[ledNumber].isOn) {
        const newColor = e.target.dataset.color;
        updateColor(ledNumber, newColor);
      }
    }
  });

  // Set initial color
  updateColor(ledNumber, ledState[ledNumber].color);
}

function setupColorPickerLED(ledNumber) {
  const switchEl = document.getElementById(`led${ledNumber}-switch`);
  const trigger = document.getElementById(`led${ledNumber}-color-trigger`);
  const picker = document.getElementById(`led${ledNumber}-color`);
  const hexInput = document.getElementById(`led${ledNumber}-hex`);
  const circle = document.getElementById(`led${ledNumber}-circle`);
  if (!switchEl || !trigger || !picker || !hexInput || !circle) return;

  switchEl.addEventListener('change', e => {
    ledState[ledNumber].isOn = e.target.checked;
    if (ledState[ledNumber].isOn) {
      updateColor(ledNumber, ledState[ledNumber].color);
    } else {
      ui.send_message('set_color', {
        led: ledNumber,
        color: { r: 0, g: 0, b: 0 },
      });
      circle.style.backgroundColor = OFF_COLOR;
    }
  });

  trigger.addEventListener('click', () => {
    if (ledState[ledNumber].isOn) {
      picker.click();
    }
  });

  picker.addEventListener('input', e => {
    if (ledState[ledNumber].isOn) {
      updateColor(ledNumber, e.target.value);
    }
  });

  hexInput.addEventListener('change', e => {
    const newColor = e.target.value;
    if (ledState[ledNumber].isOn) {
      if (/^#[0-9A-F]{6}$/i.test(newColor)) {
        updateColor(ledNumber, newColor);
      }
    }
  });
  // Set initial color
  updateColor(ledNumber, ledState[ledNumber].color);
}

function updateColor(ledNumber, newColor, updateStateColor = true) {
  if (updateStateColor) {
    ledState[ledNumber].color = newColor;
  }

  const circle = document.getElementById(`led${ledNumber}-circle`);
  circle.style.backgroundColor = newColor;

  if (ledNumber === 3) {
    const hexInput = document.getElementById(`led3-hex`);
    const trigger = document.getElementById(`led3-color-trigger`);
    hexInput.value = newColor;
    trigger.style.backgroundColor = newColor;
  }

  if (ledState[ledNumber].isOn) {
    const rgb = hexToRgb(newColor);
    ui.send_message('set_color', { led: ledNumber, color: rgb });
    console.log(`LED ${ledNumber} - R: ${rgb.r}, G: ${rgb.g}, B: ${rgb.b}`);
  } else if (newColor === '#000000') {
    // Specifically for turning off
    const rgb = hexToRgb(newColor);
    ui.send_message('set_color', { led: ledNumber, color: rgb });
    console.log(`LED ${ledNumber} turned OFF`);
  }
}

function hexToRgb(hex) {
  const r = parseInt(hex.slice(1, 3), 16) || 0;
  const g = parseInt(hex.slice(3, 5), 16) || 0;
  const b = parseInt(hex.slice(5, 7), 16) || 0;
  return { r, g, b };
}

function switchTab(event, tabId) {
  // Hide all content panels
  const panels = document.querySelectorAll('.tab-panel');
  panels.forEach(panel => panel.classList.remove('active'));

  // Remove the active class from all buttons
  const buttons = document.querySelectorAll('.tab-btn');
  buttons.forEach(btn => btn.classList.remove('active'));

  // Show the specific clicked panel and mark button as active
  document.getElementById(tabId).classList.add('active');
  event.currentTarget.classList.add('active');
}

