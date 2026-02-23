# Raspberry Pi A+ Configuration Guide

Quick reference for deploying on Raspberry Pi A+ with Raspberry Pi OS Lite 32-bit.

## Hardware Specifications

- **CPU**: Single-core ARMv6 700MHz
- **RAM**: 512MB
- **USB Ports**: 1 (use powered hub if needed)
- **GPIO**: 40-pin header (same as Pi 3/4)
- **Power**: Micro-USB, 2.5A recommended

## Servo Configuration

### Full 0-180° Range
Both servos use the complete 0-180° range for maximum classroom coverage:

```
X-axis (GPIO 23): 0° ──────────► 180°
                  Left        Right

Y-axis (GPIO 18): 0° ──────────► 180°
                  Top         Bottom
```

### Default Seat Layout (4 rows × 5 columns)

```
Column:     1      2      3      4      5
X-angle:   0°    45°    90°   135°   180°
        ┌─────┬─────┬─────┬─────┬─────┐
Row A   │ A1  │ A2  │ A3  │ A4  │ A5  │  Y: 45°
(45°)   └─────┴─────┴─────┴─────┴─────┘
        ┌─────┬─────┬─────┬─────┬─────┐
Row B   │ B1  │ B2  │ B3  │ B4  │ B5  │  Y: 75°
(75°)   └─────┴─────┴─────┴─────┴─────┘
        ┌─────┬─────┬─────┬─────┬─────┐
Row C   │ C1  │ C2  │ C3  │ C4  │ C5  │  Y: 105°
(105°)  └─────┴─────┴─────┴─────┴─────┘
        ┌─────┬─────┬─────┬─────┬─────┐
Row D   │ D1  │ D2  │ D3  │ D4  │ D5  │  Y: 135°
(135°)  └─────┴─────┴─────┴─────┴─────┘
```

### Wiring Diagram

```
┌────────────────────────────────────────────┐
│         Raspberry Pi A+                    │
│                                            │
│  GPIO 23 (Pin 16) ──►  Servo X (Signal)   │
│  GPIO 18 (Pin 12) ──►  Servo Y (Signal)   │
│  GND (Pin 14)     ──►  Servo Ground        │
│                                            │
└────────────────────────────────────────────┘

External 5-6V Power Supply
    (+) ──►  Servo VCC (both servos)
    (-) ──►  Common Ground (shared with Pi GND)

⚠️  NEVER connect servo power to Pi 5V pins!
```

## Performance Optimization

### System Requirements
- **Raspberry Pi OS Lite 32-bit** (no desktop environment)
- Headless operation via SSH
- Minimal background services

### Memory Management
```bash
# Check current memory usage
free -h

# Disable unnecessary services
sudo systemctl disable bluetooth
sudo systemctl disable avahi-daemon
sudo systemctl disable triggerhappy

# Monitor system resources
htop  # or: top
```

### CPU Optimization
The system is optimized for single-core operation:
- Threading for I/O-bound tasks (serial, GPIO)
- Non-blocking Flask server
- Efficient servo control with pigpio hardware PWM

### Startup Time
- First boot: ~60 seconds
- System initialization: ~30 seconds
- Servo calibration: ~5 seconds per seat

## Installation Quick Start

```bash
# 1. Update system
sudo apt-get update && sudo apt-get upgrade -y

# 2. Install pigpio
sudo apt-get install pigpio python3-pigpio -y
sudo systemctl enable pigpiod
sudo systemctl start pigpiod

# 3. Add user to dialout group (for USB serial)
sudo usermod -a -G dialout $USER
sudo reboot

# 4. Install Python dependencies
cd ~/vscode_projects/Reader
pip3 install -r requirements.txt

# 5. Test components
python3 servo_controller.py  # Test servos
python3 rfid_reader.py       # Test RFID reader

# 6. Run system
python3 app.py
```

## Calibration Process

### 1. Test Servo Range
```bash
python3 servo_controller.py
```
Watch the servos sweep through 0-180° range.

### 2. Map Physical Positions
Adjust `seat_map.json` based on your classroom:

```json
{
  "A1": {"x": 0, "y": 45},      // Front-left corner
  "A3": {"x": 90, "y": 45},     // Front-center
  "A5": {"x": 180, "y": 45},    // Front-right corner
  "D1": {"x": 0, "y": 135},     // Back-left corner
  "D3": {"x": 90, "y": 135},    // Back-center
  "D5": {"x": 180, "y": 135}    // Back-right corner
}
```

### 3. Fine-tune Individual Seats
```bash
python3 -c "
from servo_controller import ServoController
sc = ServoController()
sc.connect()

# Test specific positions
sc.move_to(0, 45)      # Seat A1
input('Check A1 position...')

sc.move_to(90, 45)     # Seat A3
input('Check A3 position...')

sc.move_to(180, 135)   # Seat D5
input('Check D5 position...')

sc.disconnect()
"
```

## USB Hub Setup (Optional)

If you need to connect multiple USB devices:

```bash
# Pi A+ has 1 USB port
# Use powered USB hub for:
# - RFID reader (USB-to-RS232)
# - WiFi adapter (if not using built-in WiFi)
# - Keyboard (for initial setup)

# Recommended: 4-port powered hub with 2A+ supply
```

## Network Configuration

### WiFi Setup (Headless)
Before first boot, create `wpa_supplicant.conf` on boot partition:

```
country=US
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1

network={
    ssid="YourNetworkName"
    psk="YourPassword"
    key_mgmt=WPA-PSK
}
```

### Enable SSH
Create empty file named `ssh` (no extension) on boot partition.

### Find Pi on Network
```bash
# From another computer
sudo nmap -sn 192.168.1.0/24 | grep -i raspberry

# Or use hostname
ping raspberrypi.local
```

## Monitoring & Logging

### Real-time System Monitor
```bash
# CPU, Memory, Processes
htop

# Disk usage
df -h

# Temperature (Pi A+ has no temp sensor, use SoC)
vcgencmd measure_temp
```

### Application Logs
```bash
# View live logs
python3 app.py

# Or run as service and check logs
sudo journalctl -u attendance -f
```

## Troubleshooting Pi A+ Specific

### Slow Performance
**Normal behavior** - Single-core ARMv6 is slower than modern Pi models.
- Allow 30-60 seconds for startup
- Package installation takes longer
- System is optimized for efficiency

### Memory Issues (512MB RAM)
```bash
# Check memory usage
free -h

# Add/increase swap
sudo dphys-swapfile swapoff
sudo nano /etc/dphys-swapfile  # Set CONF_SWAPSIZE=1024
sudo dphys-swapfile setup
sudo dphys-swapfile swapon
```

### USB Device Not Recognized
```bash
# Check USB devices
lsusb

# Check serial ports
ls -l /dev/ttyUSB*

# Power issues - use powered hub if needed
```

### pigpiod Errors
```bash
# Restart daemon
sudo systemctl restart pigpiod

# Check status
sudo systemctl status pigpiod

# Manual start (debug mode)
sudo killall pigpiod
sudo pigpiod -s 10  # 10μs sample rate
```

## Performance Benchmarks

Typical performance on Pi A+ (OS Lite 32-bit):

| Operation | Time |
|-----------|------|
| System boot | ~60s |
| App startup | ~30s |
| Servo movement (0-180°) | ~2s |
| RFID tag detection | <100ms |
| QR generation | ~500ms |
| API response | <200ms |
| Session creation | ~1s |

## Power Requirements

- **Raspberry Pi A+**: 500mA idle, 1A peak
- **Servos (2×)**: 100-500mA each (load dependent)
- **RFID Reader**: 200-300mA
- **Total**: 2.5A power supply recommended

**Power supply options:**
1. Pi: 2.5A micro-USB + Separate servo PSU (5-6V 2A)
2. Or: Single 5V 4A supply with proper distribution

## Quick Command Reference

```bash
# System info
cat /proc/cpuinfo | grep Model
free -h
df -h

# Service management
sudo systemctl status pigpiod
sudo systemctl status attendance

# Test components
python3 servo_controller.py
python3 rfid_reader.py
python3 qr_service.py

# Run application
python3 app.py

# View logs
tail -f /var/log/syslog | grep attendance
sudo journalctl -u attendance -f

# Network access
hostname -I
curl http://localhost:5000/api/status
```

## Additional Resources

- **Pi A+ Documentation**: https://www.raspberrypi.com/products/raspberry-pi-a-plus/
- **pigpio Library**: http://abyz.me.uk/rpi/pigpio/
- **Servo Tutorial**: https://www.raspberrypi.com/documentation/computers/raspberry-pi.html
- **Main Setup Guide**: See `README_SETUP.md`

---

**Quick Start Summary:**
1. Flash Raspberry Pi OS Lite 32-bit to SD card
2. Enable SSH and configure WiFi
3. Install pigpio and Python dependencies
4. Connect servos (GPIO 23, 18) and RFID reader (USB)
5. Calibrate using full 0-180° range
6. Run `python3 app.py`

✅ System ready for production use on Pi A+!
