# Edge-AI Spectrophotometer

> An open-source, edge-powered optical measurement and quality-control platform built around the Arduino UNO Q.

The **Edge-AI Spectrophotometer** is a compact optical measurement system designed to explore decentralized quality-control workflows using affordable hardware.

The system combines an **AS7343 spectral sensor**, controlled illumination, local spectral processing, **Ordinary Least Squares (OLS) regression**, statistical anomaly detection, reporting, and a touchscreen interface.

Everything runs locally on the **Arduino UNO Q**. The STM32U585 handles deterministic sensor acquisition and hardware control, while the Qualcomm Dragonwing QRB2210 Linux processor handles higher-level processing, storage, machine-learning inference, reporting, and the local web interface.

**No cloud connection is required for measurement or inference.**

---

## Features

- 12-channel spectral acquisition using the AS7343
- Useful optical range of approximately 430–700 nm with the current illumination system
- White-reference baseline calibration
- Real-time absorbance calculation
- Local Ordinary Least Squares (OLS) regression
- Reference-based anomaly detection
- PASS / ATTENTION / REJECT quality-control status
- On-device model training and inference
- SQLite measurement storage
- Measurement and batch analysis
- Local report generation
- 7-inch touchscreen interface
- Local AI assistant for interpreting stored measurement results
- Wi-Fi access to the dashboard
- Fully local operation without cloud processing
- 3D-printed optical chamber and enclosure
- Open-source hardware and software
- Approximately $200 prototype hardware cost

---

## System Architecture

The Arduino UNO Q provides two computing environments with different responsibilities.

### STM32U585 MCU

Responsible for deterministic hardware operations:

- AS7343 initialization
- I²C communication
- Spectral acquisition
- Channel extraction
- Hardware control
- Communication with the Linux subsystem through Arduino RouterBridge

### Qualcomm Dragonwing QRB2210

Runs the Linux application responsible for:

- Spectral preprocessing
- Baseline correction
- Absorbance calculation
- SQLite persistence
- Reference-profile generation
- Statistical deviation scoring
- OLS model training
- OLS inference
- Batch analysis
- Report generation
- Web interface
- Local AI assistant

### Measurement Pipeline

```text
White LED
   │
   ▼
 Sample
   │
   ▼
 AS7343
   │
   │ I²C
   ▼
STM32U585
   │
   │ Arduino Bridge / RPC
   ▼
QRB2210 Linux
   │
   ├── Spectral Processing
   ├── SQLite Database
   ├── Reference Analysis
   ├── OLS Regression
   ├── Rule Layer
   ├── Reports
   └── Local AI Assistant
   │
   ▼
Web Dashboard / Touchscreen
```

---

## Optical System

The optical chamber uses a transmission-based configuration:

```text
White LED → Sample Cuvette → AS7343
```

A constant-current-driven white LED illuminates the sample through a **10 mL glass cuvette**.

The AS7343 measures the transmitted light across 12 spectral channels.

The chamber is 3D printed in black PLA to reduce internal reflections and stray light.

Although the selected sensor channels extend from approximately **405 to 855 nm**, the current white LED configuration provides a practical useful measurement range of approximately **430–700 nm**.

---

## Machine Learning

The current implementation uses **Ordinary Least Squares (OLS) regression** for quantitative prediction.

Training data consists of spectral measurements associated with known target values.

Conceptually:

```text
12 Spectral Channels
        │
        ▼
 Spectral Dataset
        │
        ▼
 OLS Regression
        │
        ▼
 Predicted Value
```

Models are trained independently for each measurement category and stored locally.

The system also uses a separate statistical reference model for anomaly detection.

Reference replicates are used to calculate the mean and standard deviation of each spectral channel. New measurements are compared against this reference profile to produce a deviation score and quality-control status.

```text
Reference Samples
       │
       ▼
Mean + Standard Deviation
       │
       ▼
New Measurement
       │
       ▼
Deviation Score
       │
       ├── PASS
       ├── ATTENTION
       └── REJECT
```

The statistical status layer and OLS prediction remain deterministic and separate from the local AI assistant.

---

## User Interface

The local dashboard is divided into seven modules.

### Home

Main measurement interface.

- Baseline
- Single Scan
- Continuous acquisition
- Save measurement
- Live spectral visualization
- Sample metadata
- Measurement statistics

### Measures

Historical database containing saved spectral measurements.

### Analysis

Statistical and machine-learning tools:

- Build Reference
- Deviation scoring
- Sanity Plot
- OLS model training
- Quantitative prediction
- Batch analysis

### Maintenance

Tracks calibration state and maintenance-related information.

### Reports

Generates self-contained measurement and analysis reports.

### Chat

Local AI assistant for interacting with stored measurement information.

The assistant **does not generate analytical measurements or predictions**. Those values are produced by the deterministic analysis pipeline.

### Help

Integrated operating instructions covering:

1. Quick Measurement
2. Build Reference
3. Dilution Series & Training
4. Unknown Sample Analysis

---

## Hardware

| Component | Purpose |
|---|---|
| Arduino UNO Q | Edge computing and hardware control |
| AS7343 Spectral Sensor | Spectral acquisition |
| 3W 6000–6500K White LED | Illumination |
| PT4115 | Constant-current LED driver |
| 10 mL Glass Cuvettes | Sample containers |
| 7-inch Touchscreen | Local interface |
| USB-C Hub | Peripheral connectivity |
| PLA/PETG | Enclosure fabrication |
| M3 Heat-Set Inserts | Mechanical assembly |

Approximate prototype hardware cost: **$200 USD**.

---

## Software Stack

### Embedded

- Arduino / C++
- Arduino RouterBridge
- I²C

### Linux / Data

- Python 3
- NumPy
- pandas
- scikit-learn
- SQLite

### Interface

- Arduino App Lab
- App Lab WebUI
- Plotly

### Design

- Fusion 360
- OrcaSlicer
- EasyEDA

---

## Mechanical Design

The complete enclosure and optical chamber were designed in **Fusion 360** and fabricated using FDM 3D printing.

The optical chamber aligns three primary elements:

- White LED
- 10 mL cuvette
- AS7343 sensor

The enclosure was designed to remain serviceable so the optical chamber and electronics can be accessed independently for maintenance and upgrades.

STL/CAD files are available in this repository.

---

## Getting Started

### 1. Prepare the Arduino UNO Q

Complete the initial UNO Q setup and configure network access.

Remote access using SSH, VNC, or RDP is recommended before installing the board inside the enclosure.

### 2. Assemble the optical system

Position the components in the following order:

```text
LED → Cuvette → AS7343
```

Make sure the LED and sensor remain aligned.

### 3. Connect the AS7343

```text
UNO Q       AS7343
------------------
3.3V   →    VCC
GND    →    GND
SDA    →    SDA
SCL    →    SCL
```

### 4. Connect the illumination system

Connect the white LED through the PT4115 constant-current driver.

Do not power the LED directly without appropriate current regulation.

### 5. Install the firmware

Upload the STM32 firmware responsible for:

- Sensor initialization
- Spectral acquisition
- Channel extraction
- RouterBridge communication

### 6. Start the Linux application

The Linux application receives measurements from the STM32 and provides:

- Processing
- Storage
- Analysis
- Model training
- Inference
- Reporting
- WebUI

### 7. Capture a baseline

Insert a cuvette containing distilled water and run **Baseline**.

### 8. Measure a sample

Replace the baseline cuvette with the sample and run **Single Scan**.

The resulting absorbance spectrum will appear on the dashboard.

---

## Validation Workflow

The system includes four validation workflows.

### A — Quick Measurement

Verify basic optical acquisition and spectral repeatability.

### B — Build Reference

Capture multiple known-good samples and build a statistical reference profile for anomaly detection.

### C — Dilution Series & Training

Create a labelled physical dilution series, evaluate linearity, and train the OLS regression model.

### D — Held-Out Sample

Measure a sample that was not included in model training and compare its prediction against independently known ground truth.

---

## Current Limitations

This is a research prototype, not a certified laboratory instrument.

Current limitations include:

- Useful spectral range currently limited primarily to approximately 430–700 nm
- 12 discrete spectral channels rather than a continuous spectrum
- Single-beam optical architecture
- Non-uniform spectral output from the white LED
- Limited training datasets
- No formal measurement uncertainty characterization
- No electrical safety or EMC certification
- No validation for regulated diagnostic or laboratory use

The instrument should **not** be used as a replacement for certified analytical equipment where regulated measurements are required.

---

## Future Work

Planned improvements include:

- Dedicated 850 nm illumination for improved near-infrared measurements
- Improved illumination stability
- Dual-beam optical architecture
- Environmental and sensor-health telemetry
- Larger calibration datasets
- Independent model validation
- Additional domain-specific calibration models
- Distributed multi-instrument monitoring

---

## Project Goals

This project explores how **optical sensing, edge computing, machine learning, and Industrial IoT** can be combined into an affordable and open quality-control platform.

The goal is not to replace certified laboratory instrumentation, but to create an accessible platform for experimentation, distributed optical measurement, and the development of application-specific quality-control workflows.

---

## Documentation

Full build documentation includes:

- System architecture
- Bill of materials
- CAD and enclosure fabrication
- Electronics and wiring
- STM32 firmware
- Linux backend
- Web interface
- Machine-learning pipeline
- Validation experiments
- Engineering limitations

See the Hackster project page in the about section of this repository for the complete step-by-step build guide.

Check out the video for a step by step: [Edge-AI Spectrophotometer: Industrial Quality Control
 Youtube Video](https://www.youtube.com/watch?v=SfvVCilvs7o)

---

## Author

**Jorge Eldis González**

Electrical/Electronics Engineering • Software • Networking • Embedded Systems

Project developed for the **Arduino UNO Q** platform.

---

## Acknowledgments

Built using the Arduino UNO Q, Arduino App Lab, and the open-source Python scientific computing ecosystem.

Special thanks to the Arduino and maker communities for making open hardware development accessible.
