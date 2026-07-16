// SPDX-FileCopyrightText: Copyright (C) Arduino s.r.l. and/or its affiliated companies
//
// SPDX-License-Identifier: MPL-2.0

TESTER = document.getElementById('tester');

Plotly.newPlot( TESTER, [{
x: [1, 2, 3, 4, 5],
y: [1, 2, 4, 8, 16] }], {
 margin: { t: 20, l: 20, r: 20, b: 20 },
 title: 'Spectrophotometer Scan Preview',
 xaxis: { title: 'Wavelength' },
 yaxis: { title: 'Intensity' }
 } );

const baselineBtn = document.getElementById('baseline-btn');
const singleScanBtn = document.getElementById('single-scan-btn');
const continuousBtn = document.getElementById('continuous-btn');
let continuousInterval = null;

baselineBtn?.addEventListener('click', startBaseline);
singleScanBtn?.addEventListener('click', startSingleScan);
continuousBtn?.addEventListener('click', toggleContinuousScan);

function startBaseline() {
  console.log('Baseline scan started');
  Plotly.react(TESTER, [{
    x: [1, 2, 3, 4, 5],
    y: [2, 2, 2, 2, 2],
    type: 'scatter',
    mode: 'lines+markers',
    name: 'Baseline'
  }], {
    margin: { t: 20, l: 20, r: 20, b: 20 },
    title: 'Baseline Scan',
    xaxis: { title: 'Wavelength' },
    yaxis: { title: 'Intensity' }
  });
}

function startSingleScan() {
  console.log('Single scan started');
  Plotly.react(TESTER, [{
    x: [1, 2, 3, 4, 5],
    y: [1, 3, 5, 4, 6],
    type: 'scatter',
    mode: 'lines+markers',
    name: 'Single Scan'
  }], {
    margin: { t: 20, l: 20, r: 20, b: 20 },
    title: 'Single Scan',
    xaxis: { title: 'Wavelength' },
    yaxis: { title: 'Intensity' }
  });
}

function toggleContinuousScan() {
  if (continuousInterval) {
    stopContinuousScan();
    return;
  }

  console.log('Continuous scan started');
  continuousBtn.textContent = 'STOP CONTINUOUS';
  continuousInterval = setInterval(() => {
    const nextY = Array.from({ length: 5 }, () => Math.round(Math.random() * 10) + 1);
    Plotly.react(TESTER, [{
      x: [1, 2, 3, 4, 5],
      y: nextY,
      type: 'scatter',
      mode: 'lines+markers',
      name: 'Continuous Scan'
    }], {
      margin: { t: 20, l: 20, r: 20, b: 20 },
      title: 'Continuous Scan',
      xaxis: { title: 'Wavelength' },
      yaxis: { title: 'Intensity' }
    });
  }, 1000);
}

function stopContinuousScan() {
  console.log('Continuous scan stopped');
  clearInterval(continuousInterval);
  continuousInterval = null;
  continuousBtn.textContent = 'CONTINUOUS SCAN';
}
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

