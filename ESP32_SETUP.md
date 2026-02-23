# ESP32 Servo Controller Setup Guide

## Overview
Switched from Raspberry Pi (damaged) to ESP32 for servo control.

## Hardware Setup

### Components
- **ESP32 Development Board**
- **2× FT5835M Servos** (270° servos, limited to 180° range)
- **External 5-6V Power Supply** for servos
- **USB Cable** for ESP32

### Wiring
```
ESP32 GPIO Connections:
├── GPIO 18 → Servo X (signal wire)
├── GPIO 23 → Servo Y (signal wire)
└── GND → Common ground with servo power supply

Servo Power:
├── Servo +5V → External 5-6V power supply (+)
├── Servo GND → External power supply (-) AND ESP32 GND
└── Signal wires → ESP32 GPIO pins
```

**IMPORTANT:** 
- Connect external power supply GND to ESP32 GND (common ground)
- Do NOT power servos from ESP32 (not enough current)

## Software Setup

### Step 1: Install Arduino IDE
1. Download from: https://www.arduino.cc/en/software
2. Install for macOS

### Step 2: Install ESP32 Board Support
1. Open Arduino IDE
2. Go to: `Arduino IDE → Settings`
3. Add to "Additional Board Manager URLs":
   ```
   https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json
   ```
4. Go to: `Tools → Board → Boards Manager`
5. Search for "ESP32"
6. Install "esp32 by Espressif Systems"

### Step 3: Install ESP32Servo Library
1. Go to: `Tools → Manage Libraries`
2. Search for "ESP32Servo"
3. Install "ESP32Servo by Kevin Harrington"

### Step 4: Upload Firmware
1. Open `esp32_servo_firmware.ino` in Arduino IDE
2. Select board: `Tools → Board → ESP32 Arduino → ESP32 Dev Module`
3. Select port: `Tools → Port → /dev/cu.usbserial-XXXX` (your ESP32 port)
4. Click Upload button (→)
5. Wait for "Done uploading"

### Step 5: Test Serial Connection
Open Serial Monitor (`Tools → Serial Monitor`):
- Set baud rate: **115200**
- You should see:
  ```
  === ESP32 Servo Controller ===
  Firmware: v1.0
  Model: FT5835M (270° servos)
  Range: 45-225° (180° limited)
  X Servo: GPIO 18
  Y Servo: GPIO 23
  Center: 135°, 135°
  
  Ready! Waiting for commands...
  ```

### Step 6: Test Manual Commands
In Serial Monitor, type these commands:

| Command | Description | Example |
|---------|-------------|---------|
| `C` | Center both servos | `C` |
| `X90` | Move X to 90° | `X90` |
| `Y135` | Move Y to 135° | `Y135` |
| `B90,135` | Move both (X=90, Y=135) | `B90,135` |
| `S` | Show status | `S` |

### Step 7: Test Python Connection
```bash
# Test ESP32 detection and basic movement
python3 test_esp32_servos.py
```

Expected output:
```
🤖 ESP32 Servo Controller - Quick Test
📡 Connecting to ESP32...
✅ Connected successfully!
   Port: /dev/cu.usbserial-XXXX
   Current position: X=135°, Y=135°

🔄 Testing servo movements...
1. Moving to A1 (90, 90)...
2. Moving to A3 (180, 90)...
3. Moving to center (135, 135)...

✅ All tests passed!
```

## Running the Main Application

The app has been updated to use ESP32 instead of Raspberry Pi:

```bash
python3 app_integrated.py
```

The system will:
1. Auto-detect ESP32 port
2. Connect via serial
3. Initialize servos to center (135°, 135°)
4. Start Flask web server
5. Ready to accept attendance requests

## Servo Angle Reference

For 270° FT5835M servos limited to 180° range:

| Position | Angle | Physical Position |
|----------|-------|-------------------|
| Minimum | 45° | Far left/front |
| Center | 135° | Middle |
| Maximum | 225° | Far right/back |

### Classroom Seat Positions
See `seat_map.json` for all 20 seat positions.

Example seats:
- **A1:** X=90°, Y=90° (front left)
- **A2:** X=135°, Y=90° (front center)
- **A3:** X=180°, Y=90° (front right)
- **D2:** X=135°, Y=135° (middle center)
- **G2:** X=165°, Y=180° (back)

## Troubleshooting

### ESP32 Not Detected
```bash
# List all USB devices
ls /dev/cu.*

# Check USB system info
system_profiler SPUSBDataType
```

### Servos Not Moving
1. Check power supply is ON and connected
2. Verify common ground connection
3. Check servo signal wires on GPIO 18 & 23
4. Test in Serial Monitor with manual commands

### Serial Communication Errors
1. Close Arduino Serial Monitor (only one program can use port)
2. Check baud rate is 115200
3. Try unplugging/replugging ESP32
4. Check USB cable (some are power-only)

### Permission Denied Error
```bash
# Give permissions (macOS doesn't usually need this)
sudo chmod 666 /dev/cu.usbserial-*
```

## API Changes

No API changes! The ESP32 controller implements the same interface as the Raspberry Pi version:

```python
controller = ServoController()
controller.connect()
controller.move_to(x, y)
controller.move_to_seat(seat_angles)
controller.center()
controller.disconnect()
```

## Performance Notes

- **Serial latency:** ~50ms per command
- **Smooth movements:** 15 steps over ~450ms
- **Settling time:** 150ms after movement
- **Total scan time:** ~1-2 seconds per seat

This is slightly slower than direct GPIO control but perfectly adequate for attendance scanning.
