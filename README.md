# 🎓 Hybrid RFID-QR Attendance System

A smart classroom attendance system that combines **UHF RFID tag detection** with **QR code verification** and **motorized positioning** (stepper motors) to verify student seating. Runs on a **laptop (macOS)** with an **R16-12DB UHF RFID Reader** connected via USB, and an **ESP32** driving dual stepper motors.

---

## 📋 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Hardware Requirements](#hardware-requirements)
- [Software Requirements](#software-requirements)
- [Installation](#installation)
- [Project Structure](#project-structure)
- [Usage](#usage)
- [API Endpoints](#api-endpoints)
- [Configuration](#configuration)
- [ESP32 Firmware](#esp32-firmware)
- [Troubleshooting](#troubleshooting)

---

## Overview

The system works as follows:

1. **Teacher** creates an attendance session → system generates a **QR code**
2. **Students** scan the QR code on their phone and select their seat
3. The system **moves servos/steppers** to point at the claimed seat
4. The **RFID reader** scans for the student's tag at that location
5. If the tag matches the seat → ✅ attendance verified

---

## Features

- ✅ Auto-detection of USB serial ports (macOS / Linux)
- ✅ Dual RFID protocol support — ASCII lines and binary frames (0xA0, 0xBB)
- ✅ Multi-tag simultaneous scanning with per-tag cooldown
- ✅ RSSI extraction with debug mode for protocol analysis
- ✅ TagID → SeatID mapping via CSV or JSON
- ✅ Smart deduplication (configurable time window)
- ✅ Dual storage — SQLite database + CSV log
- ✅ Stepper motor position tracking (X/Y in cm)
- ✅ Flask REST API for mobile dashboard access
- ✅ QR code generation with HMAC signature verification
- ✅ Stepper motor control via ESP32 over serial
- ✅ Auto-reconnect on serial disconnection
- ✅ Classroom visualization and digital twin

---

## Hardware Requirements

| Component | Details |
|---|---|
| **Laptop (macOS)** | Runs Python scripts, Flask server, and RFID reader control |
| **R16-12DB UHF RFID Reader** | Connected to laptop via USB-to-RS232 adapter |
| **ESP32 Dev Board** | Controls dual stepper motors, connected to laptop via USB serial |
| **Stepper Motors (×2)** | X/Y axis positioning, driven by ESP32 |
| **USB-RS232 Adapter** | For RFID reader connection |
| **5V 2A Power Supply** | Separate PSU for stepper motors |

---

## Software Requirements

- **macOS** (tested on Apple Silicon MacBook)
- **Python** 3.7+
- **pip** (Python package manager)
- **Arduino IDE** or **PlatformIO** (for flashing ESP32 firmware only)

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/gamoozy/rfid.git
cd rfid
```

### 2. Create a virtual environment (recommended)

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Python dependencies

```bash
pip install -r requirements.txt
```

This installs:

| Package | Purpose |
|---|---|
| `flask` | Web framework for the REST API |
| `flask-cors` | Cross-origin requests for mobile access |
| `qrcode[pil]` + `Pillow` | QR code generation |
| `pyserial` | Serial communication with RFID reader & ESP32 |
| `python-dateutil` | Date/time utilities |

> **Note:** `pigpio` is listed in `requirements.txt` but only needed on Raspberry Pi. On macOS it will install but isn't used — the stepper motors are controlled via the ESP32 over serial instead.

### 4. Connect hardware

1. Connect R16-12DB reader to USB-RS232 adapter → plug into laptop USB
2. Connect ESP32 to laptop via USB cable
3. Verify connections:
   ```bash
   ls /dev/cu.*
   # You should see something like:
   #   /dev/cu.usbserial-210    (RFID reader)
   #   /dev/cu.usbserial-0001   (ESP32)
   ```

---

## Project Structure

```
rfid/
├── app.py                        # Flask REST API (main web server)
├── app_integrated.py             # Integrated app variant
├── reader_capture.py             # Single-tag RFID capture script
├── reader_capture_multi.py       # Multi-tag RFID capture script
├── rfid_reader.py                # RFID reader module
├── servo_controller.py           # Servo motor control (legacy Pi GPIO)
├── servo_controller_esp32.py     # Servo control via ESP32
├── arrow_servo_control.py        # Manual servo control with arrow keys
├── manual_servo_control.py       # Manual servo positioning
├── Stepper_control.py            # Dual stepper motor controller + position tracking
├── attendance_controller.py      # Attendance verification logic
├── qr_service.py                 # QR code generation & validation
├── classroom_visualization.py    # Classroom layout visualization
├── classroom_web.py              # Web-based classroom view
│
├── requirements.txt              # Python dependencies
├── seat_map.json                 # Seat → servo angle mapping
├── tag_map.json                  # RFID tag → seat mapping
├── tagmap.csv                    # Tag mapping (CSV format)
├── room_config.json              # Room dimensions & motor calibration
├── stepper_position.json         # Live stepper motor position (auto-generated)
│
├── esp32_servo_firmware/         # Arduino firmware for ESP32 servo control
│   └── esp32_servo_firmware.ino
├── esp32_servo_firmware_simple/  # Simplified ESP32 servo firmware
├── stepper_test/                 # Arduino firmware for stepper motor testing
│   └── stepper_test.ino
│
├── templates/                    # HTML templates for Flask
├── student_portal_prototype.html # Student portal UI prototype
├── Datasheets/                   # Hardware datasheets (R16-12DB)
│
├── rfid_scans.db                 # SQLite database (auto-created)
├── rfid_scans.csv                # CSV log (auto-created)
│
├── ARCHITECTURE.md               # System architecture diagrams
├── README_SETUP.md               # Setup guide
├── PI_A_PLUS_CONFIG.md           # Pi A+ reference (legacy)
├── ESP32_SETUP.md                # ESP32 setup instructions
├── DIGITAL_TWIN_GUIDE.md         # Digital twin documentation
├── DIGITAL_TWIN_VISUAL.md        # Digital twin visual guide
├── STUDENT_PORTAL_UI.md          # Student portal UI docs
├── SUMMARY.md                    # Project summary
│
└── test_*.py                     # Test scripts
```

---

## Usage

### RFID Reader — Multi-Tag Capture (Recommended)

```bash
python reader_capture_multi.py
```

Auto-detects the serial port and starts scanning all tags in range.

**Options:**

```bash
python reader_capture_multi.py --port /dev/cu.usbserial-210   # Specify port
python reader_capture_multi.py --debug                         # Show raw hex dumps
python reader_capture_multi.py --tagmap tagmap.csv             # Load tag→seat mapping
python reader_capture_multi.py --dedupe-ms 1000                # Adjust dedup window
python reader_capture_multi.py --baud 115200                   # Change baud rate
```

| Option | Default | Description |
|---|---|---|
| `--port` | Auto-detect | Serial port path |
| `--baud` | 115200 | Baud rate |
| `--timeout` | 0.2 | Serial timeout (seconds) |
| `--tagmap` | None | Path to TagMap CSV/JSON file |
| `--dedupe-ms` | 800 | Deduplication window (milliseconds) |
| `--db` | rfid_scans.db | SQLite database path |
| `--csv` | rfid_scans.csv | CSV log file path |
| `--debug` | False | Enable debug mode |

### Flask Web Server

```bash
python app.py
```

Starts the REST API on `http://0.0.0.0:5000`. Access from:
- Local: `http://localhost:5000`
- Network: `http://<your-laptop-ip>:5000`
- Remote (via ngrok): `ngrok http 5000`

### Stepper Motor Control

```bash
python Stepper_control.py
```

Interactive arrow-key control for dual stepper motors (requires ESP32 connected via USB serial). Tracks X/Y position in centimeters and writes to `stepper_position.json`.

| Key | Action |
|---|---|
| ← → | Move X-axis (left/right) |
| ↑ ↓ | Move Y-axis (up/down) |
| H | Home — reset position to (0, 0) |
| P | Print current position |
| S / Space | Stop all motors |
| X | Emergency stop |
| Q | Quit |

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Homepage with API docs |
| `GET` | `/api/status` | System status (servos, RFID, lock state) |
| `POST` | `/api/session/create` | Create attendance session & generate QR |
| `POST` | `/api/attendance/claim` | Student claims a seat (QR + seat selection) |
| `GET` | `/api/session/<session_id>` | Get session stats & verified students |
| `POST` | `/api/servo/test` | Test servo movement |
| `GET` | `/api/servo/center` | Center servos |
| `GET` | `/api/config` | Get seat map & tag map configuration |

### Example — Create a Session

```bash
curl -X POST http://localhost:5000/api/session/create \
  -H "Content-Type: application/json" \
  -d '{"session_id": "CS101-2025-01-15", "classroom_id": "ROOM-A"}'
```

### Example — Claim a Seat

```bash
curl -X POST http://localhost:5000/api/attendance/claim \
  -H "Content-Type: application/json" \
  -d '{"qr_data": "...", "student_id": "STU123", "seat_id": "A1"}'
```

---

## Configuration

### Tag Map (`tagmap.csv` or `tag_map.json`)

Maps RFID tag IDs to seat IDs:

```csv
TagID,SeatID
E28011700000020123456789,A1
E28011700000020123456790,A2
300833B2DDD906C00000270F,C1
```

### Seat Map (`seat_map.json`)

Maps seats to servo angles for the pan-tilt mechanism:

```json
{
  "A1": {"x": 0, "y": 45},
  "A2": {"x": 45, "y": 45},
  "B3": {"x": 90, "y": 75}
}
```

### Room Config (`room_config.json`)

Stepper motor calibration and room dimensions:

```json
{
  "room_width_cm": 800,
  "room_depth_cm": 600,
  "motor1_cm_per_revolution": 8.0,
  "motor2_cm_per_revolution": 8.0,
  "steps_per_revolution": 1600,
  "steps_per_press": 200
}
```

---

## ESP32 Firmware

The ESP32 boards need to be flashed separately using the **Arduino IDE** or **PlatformIO**.

### Servo Firmware

1. Open `esp32_servo_firmware/esp32_servo_firmware.ino` in Arduino IDE
2. Select your ESP32 board and port
3. Upload

### Stepper Firmware

1. Open `stepper_test/stepper_test.ino` in Arduino IDE
2. Select your ESP32 board and port
3. Upload

> See [ESP32_SETUP.md](ESP32_SETUP.md) for detailed flashing instructions.

---

## Database

Scans are stored in SQLite (`rfid_scans.db`) and CSV (`rfid_scans.csv`).

### Useful Queries

```sql
-- Recent scans
SELECT * FROM rfid_scans ORDER BY timestamp_epoch DESC LIMIT 10;

-- Scans per seat
SELECT seat_id, COUNT(*) as count FROM rfid_scans GROUP BY seat_id ORDER BY count DESC;

-- Scans with position data
SELECT tag_id, seat_id, x_cm, y_cm, rssi FROM rfid_scans WHERE x_cm IS NOT NULL;

-- Weak RSSI tags
SELECT * FROM rfid_scans WHERE rssi IS NOT NULL AND rssi < -60 ORDER BY rssi;
```

---

## Troubleshooting

### No serial ports detected

```bash
ls /dev/cu.* /dev/tty.*          # List all serial ports
system_profiler SPUSBDataType    # Check USB devices (macOS)
lsusb                            # Check USB devices (Linux)
```

### Permission denied on serial port

```bash
# Linux
sudo usermod -a -G dialout $USER
# Then log out and log back in
```

### Reader not responding

1. Check physical connections and power LEDs
2. Try different baud rates: `--baud 9600`, `--baud 57600`, `--baud 115200`
3. Enable debug mode: `--debug`
4. Consult the datasheet in `Datasheets/`

### ESP32 not responding

1. Check that the ESP32 is connected via USB and the correct port is set in `Stepper_control.py`
2. Open Arduino IDE Serial Monitor at 115200 baud to verify the ESP32 is sending `READY`
3. Make sure no other program (e.g., Serial Monitor) is holding the port open

---

## License

This project is provided as-is for the Hybrid RFID-QR Attendance System prototype.

---

**Built with ❤️ for reliable RFID attendance tracking**
