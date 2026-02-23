# Hybrid RFID-QR Attendance System

Complete attendance verification system for Raspberry Pi combining RFID tags and QR codes for secure, automated classroom attendance tracking.

**✨ NEW: Real-time Digital Twin Visualization** - Live classroom monitor with servo position tracking!

## 📋 System Overview

**How it works:**
1. Teacher creates an attendance session → System generates unique QR code
2. Student scans QR code on mobile device
3. Student selects their seat from dashboard
4. System locks RFID scanning and moves servos to seat position
5. **Digital Twin shows seat turning yellow, servo moving in real-time** 🎯
6. Student places RFID tag at reader location
7. System verifies tag matches claimed seat
8. **Seat turns green on Digital Twin - attendance verified** ✓

**Features:**
- 🎨 Real-time classroom visualization (A1-D5 layout)
- 📍 Live servo position tracking (0-180° range)
- 🟢 Color-coded seat status (scanning/verified/empty)
- 📊 Live attendance statistics
- 📱 Responsive design (desktop/mobile)
- 🔄 Auto-updates every 300ms

## 🔧 Hardware Requirements

### Raspberry Pi Setup
- **Board**: Raspberry Pi A+ (512MB RAM)
- **OS**: Raspberry Pi OS Lite 32-bit (Bullseye or newer)
  - Headless operation (no desktop environment)
  - Optimized for single-core CPU and limited RAM
- **Storage**: 8GB+ microSD card

### Components
- **RFID Reader**: R16-12DB UHF RFID Reader
  - Connected via USB-to-RS232 adapter
  - Port: `/dev/ttyUSB0`
  - Baud rate: 19200

- **Servo Motors**: 2× Standard servos (SG90 or similar, 0-180° range)
  - Servo X → GPIO 23 (pin 16) - Horizontal positioning
  - Servo Y → GPIO 18 (pin 12) - Vertical positioning
  - Full 0-180° range utilized for maximum coverage
  - External 5-6V power supply with common ground (do NOT power from Pi GPIO)

- **RFID Tags**: UHF RFID tags (compatible with R16-12DB)

## 📦 Installation

### 1. System Dependencies

```bash
# Update system
sudo apt-get update
sudo apt-get upgrade -y

# Install pigpio for servo control
sudo apt-get install pigpio python3-pigpio -y

# Start pigpio daemon (required for servos)
sudo pigpiod

# Enable pigpiod on boot
sudo systemctl enable pigpiod
sudo systemctl start pigpiod

# Add user to dialout group (for serial port access)
sudo usermod -a -G dialout $USER

# Reboot to apply group changes
sudo reboot
```

### 2. Python Dependencies

```bash
cd /path/to/Reader
pip3 install -r requirements.txt
```

**Note for Pi A+ (512MB RAM):** Installation may take longer due to single-core CPU. Be patient during package compilation.

### 3. Configuration

**a. Configure Seat Map** (`seat_map.json`)

Maps seat IDs to servo angles (X and Y in degrees, **full 0-180° range**):

```json
{
  "A1": {"x": 0, "y": 45},
  "A2": {"x": 45, "y": 45},
  "A3": {"x": 90, "y": 45},
  "A4": {"x": 135, "y": 45},
  "A5": {"x": 180, "y": 45}
}
```

- **X axis**: Horizontal position (0° = far left, 180° = far right)
- **Y axis**: Vertical position (0° = top, 180° = bottom)
- Default layout uses 5 columns (0°/45°/90°/135°/180°) and 4 rows (45°/75°/105°/135°)
- Adjust angles based on your physical setup and classroom dimensions

**b. Configure Tag Map** (`tag_map.json`)

Maps seat IDs to RFID tag IDs:

```json
{
  "A1": "186098E018981E66981E181E8698E6981E98801E",
  "A2": "186098E018981E66981E06981E0698F8981E98801E",
  ...
}
```

To find tag IDs, run:
```bash
python3 rfid_reader.py
# Scan each tag and note the ID
```

### 4. Hardware Connections

```
┌──────────────────┐
│  Raspberry Pi    │
│                  │
│  GPIO 23 ────────┼──→ Servo X (Signal)
│  GPIO 18 ────────┼──→ Servo Y (Signal)
│  GND ────────────┼──→ Power Supply GND & Servo GND
│                  │
│  USB ────────────┼──→ USB-RS232 Adapter
└──────────────────┘
                   │
        ┌──────────┴──────────┐
        │                     │
   ┌────▼────┐         ┌──────▼─────┐
   │  5-6V   │         │  R16-12DB  │
   │  Power  │         │  RFID      │
   │  Supply │         │  Reader    │
   └─────────┘         └────────────┘
```

**Critical Notes:**
- Servos must have separate 5-6V power supply (RPi 3.3V is insufficient)
- **Common ground** between RPi and power supply is essential
- RFID reader USB must show as `/dev/ttyUSB0`

## 🚀 Running the System

### Quick Test

Test each component individually:

```bash
# 1. Test servo controller
python3 servo_controller.py
# Should move servos in sweep pattern

# 2. Test RFID reader
python3 rfid_reader.py
# Scan tags to see detection

# 3. Test QR service
python3 qr_service.py
# Generates test QR code (test_qr.png)

# 4. Test attendance controller
python3 attendance_controller.py
# Simulates verification flow
```

### Start Main Application

**Option 1: Integrated System with Digital Twin (Recommended)**
```bash
python3 app_integrated.py
```

**Option 2: API Only (No Visualization)**
```bash
python3 app.py
   with Digital Twin Visualization
============================================================

✅ System initialized successfully!

Starting Flask server...
Access via:
  • Classroom View: http://localhost:5000
  • API Status: http://localhost:5000/api/status
  • Network: http://<raspberry-pi-ip>:5000

For mobile access, run:
  ngrok http 5000

Digital Twin Features:
  ✓ Real-time seat status (A1-D5 layout)
  ✓ Live servo position tracking
  ✓ Color-coded scanning status
  ✓ Attendance statisticsrver...
Access via:
  • Local: http://localhost:5000
  • Network: http://<raspberry-pi-ip>:5000

For mobile access, run:
  ngrok http 5000

Press Ctrl+C to stop
============================================================
```

### Enable Mobile Access with ngrok

```bash
# Install ngrok (first time only)
curl -s https://ngrok-agent.s3.amazonaws.com/ngrok.asc | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null
echo "deb https://ngrok-agent.s3.amazonaws.com buster main" | sudo tee /etc/apt/sources.list.d/ngrok.list
sudo apt update
sudo apt install ngrok

# Sign up at ngrok.com and get auth token
ngrok config add-authtoken <your-token>

# Expose Flask app
ngrok http 5000
```

Students can now access the system from phones using the ngrok URL.

## 📱 API Usage

### Create Session

```bash
curl -X POST http://localhost:5000/api/session/create \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "CS101-2025-01-15",
    "classroom_id": "ROOM-A",
    "validity_minutes": 60
  }'
```

Response:
```json
{
  "success": true,
  "session_id": "CS101-2025-01-15",
  "qr_image": "iVBORw0KGgoAAAANS...",  // base64 PNG
  "qr_data": "{\"session_id\":...}",
  "expiry": 1705334400
}
```

### Student Claims Seat

```bash
curl -X POST http://localhost:5000/api/attendance/claim \
  -H "Content-Type: application/json" \
  -d '{
    "qr_data": "{\"session_id\":\"CS101-2025-01-15\",...}",
    "student_id": "STU12345",
    "seat_id": "A1"
  }'
```

Response (success):
```json
{
  "success": true,
  "status": "success",
  "message": "Attendance verified successfully",
  "student_id": "STU12345",
  "seat_id": "A1",
  "tag_id": "186098E018981E66981E181E8698E6981E98801E",
  "timestamp": 1705330800.123
}
```

### Get System Status

```bash
curl http://localhost:5000/api/status
```

### Get Session Statistics

```bash
curl http://localhost:5000/api/session/CS101-2025-01-15
```

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────┐
│                    app.py                           │
│            (Flask Web Server)                       │
│  Endpoints: /api/session/create                     │
│             /api/attendance/claim                   │
│             /api/status                             │
└─────────────┬───────────────────────────────────────┘
              │
    ┌─────────┼─────────┬─────────────┬──────────────┐
    │         │         │             │              │
┌───▼──┐  ┌──▼───┐  ┌──▼────┐   ┌────▼─────┐  ┌────▼─────┐
│ QR   │  │Attend│  │ Servo │   │   RFID   │  │  Config  │
│Serv  │  │Ctrl  │  │ Ctrl  │   │  Reader  │  │  Files   │
└──────┘  └──┬───┘  └───────┘   └──────────┘  └──────────┘
             │
     ┌───────┴────────┐
     │                │
┌────▼────┐     ┌─────▼─────┐
│  Lock   │     │   Verify  │
│  Mgmt   │     │   Logic   │
└─────────┘     └───────────┘
```

### Component Responsibilities

- **app.py**: REST API, session management, request routing
- **qr_service.py**: QR code generation, HMAC validation
- **attendance_controller.py**: Verification flow, scan locking, session tracking
- **servo_controller.py**: Servo movement, position control
- **rfid_reader.py**: Serial communication, tag parsing, callbacks

## 🔒 Security Features

- **HMAC-signed QR codes**: Prevents tampering
- **Time-limited sessions**: QR codes expire after validity period
- **Scan locking**: Only one verification at a time
- **Duplicate prevention**: Students can't verify twice in same session
- **Tag-seat binding**: Must use correct RFID tag for claimed seat

## 🐛 Troubleshooting

### Raspberry Pi A+ Specific Issues

**Slow performance:**
- Normal for single-core CPU (ARMv6 700MHz)
- System optimized for resource efficiency
- Allow extra time for initial startup (~30 seconds)

**Out of memory errors:**
- Close unnecessary background services: `sudo systemctl stop <service>`
- Use swap if needed: `sudo dphys-swapfile swapoff && sudo dphys-swapfile swapon`
- Monitor memory: `free -h`

**USB connectivity issues:**
- Pi A+ has only 1 USB port - use powered USB hub if needed
- RFID reader USB-to-RS232 adapter must be powered

### Servos not moving

```bash
# Check pigpiod is running
sudo systemctl status pigpiod

# Restart if needed
sudo systemctl restart pigpiod

# Test manually
python3 servo_controller.py
```

### RFID reader not detected

```bash
# Check USB connection
ls /dev/ttyUSB*

# Should show: /dev/ttyUSB0

# Check permissions
groups
# Should include 'dialout'

# If not, add and reboot
sudo usermod -a -G dialout $USER
sudo reboot
```

### No tags detected

```bash
# Test reader directly
python3 rfid_reader.py

# Check baud rate (should be 19200)
# Verify reader is powered and antenna connected
```

### Flask won't start

```bash
# Check port 5000 is free
sudo lsof -i :5000

# Install dependencies
pip3 install -r requirements.txt

# Check configuration files exist
ls seat_map.json tag_map.json
```

## 📊 File Structure

```
Reader/
├── app.py                      # Main Flask application
├── servo_controller.py         # Servo control with pigpio
├── qr_service.py               # QR generation and validation
├── attendance_controller.py    # Verification logic and locking
├── rfid_reader.py             # RFID serial communication
├── seat_map.json              # Seat ID → Servo angles
├── tag_map.json               # Seat ID → Tag ID mapping
├── requirements.txt           # Python dependencies
├── README_SETUP.md            # This file
└── test_qr.png               # Generated by qr_service.py test
```

## 🔄 Auto-Start on Boot (Optional)

Create systemd service:

```bash
sudo nano /etc/systemd/system/attendance.service
```

Add:
```ini
[Unit]
Description=RFID-QR Attendance System
After=network.target pigpiod.service

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/vscode_projects/Reader
ExecStart=/usr/bin/python3 /home/pi/vscode_projects/Reader/app.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

Enable:
```bash
sudo systemctl enable attendance.service
sudo systemctl start attendance.service
```

## 📝 Example Workflow

1. **Teacher**: Creates session
   ```bash
   POST /api/session/create
   {"session_id": "CS101-Lecture-5"}
   ```

2. **Teacher**: Projects QR code on screen

3. **Student**: Scans QR with phone, opens dashboard

4. **Student**: Selects seat "A1", submits

5. **System**: 
   - Locks RFID scanning
   - Moves servos to A1 position
   - Waits for tag...

6. **Student**: Places RFID card at reader

7. **System**: 
   - Detects tag: `186098E018981E66981E181E8698E6981E98801E`
   - Verifies it matches seat A1
   - Records attendance ✓
   - Unlocks scanning

8. **Next student**: Process repeats

## 🎓 Advanced Features

### Custom Verification Timeout

Edit `app.py`:
```python
attendance_controller = AttendanceController(
    servo_controller=servo_controller,
    seat_map=seat_map,
    tag_map=tag_map,
    verification_timeout=10.0  # 10 seconds instead of 5
)
```

### Different QR Validity

```bash
POST /api/session/create
{
  "session_id": "...",
  "validity_minutes": 120  # 2 hours
}
```

### Servo Angle Calibration

The system uses the **full 0-180° servo range**. Calibrate for your physical setup:

```bash
# Run built-in test sweep
python3 servo_controller.py
```

The test will sweep through the full range. Adjust `seat_map.json` based on your classroom layout:

```json
{
  "A1": {"x": 0, "y": 45},      // Front-left (0° horizontal, 45° vertical)
  "A3": {"x": 90, "y": 45},     // Front-center (90° horizontal)
  "A5": {"x": 180, "y": 45},    // Front-right (180° horizontal)
  "D3": {"x": 90, "y": 135}     // Back-center (135° vertical)
}
```

**Angle distribution:**
- X-axis (columns): 0°, 45°, 90°, 135°, 180° for 5 columns
- Y-axis (rows): 45°, 75°, 105°, 135° for 4 rows

## 📞 Support

For issues or questions:
1. Check troubleshooting section above
2. Review logs: System prints detailed logs to console
3. Test components individually before full system

## 🔐 Production Deployment

**Security checklist:**
- [ ] Change QR secret key in `app.py`
- [ ] Set Flask `debug=False`
- [ ] Use HTTPS with ngrok or reverse proxy
- [ ] Implement authentication for teacher endpoints
- [ ] Regular backup of session data
- [ ] Monitor system logs

---

**System Status**: ✅ Ready for deployment on Raspberry Pi 3/4

**Last Updated**: December 2025
