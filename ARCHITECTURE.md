# System Architecture Diagram - Raspberry Pi A+

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Hybrid RFID-QR Attendance System                         │
│                    Raspberry Pi A+ (512MB RAM, ARMv6)                       │
└─────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│                           HARDWARE LAYER                                     │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────┐      ┌─────────────┐      ┌─────────────────────────┐     │
│  │   Servo X   │      │   Servo Y   │      │   R16-12DB RFID Reader  │     │
│  │  (0-180°)   │      │  (0-180°)   │      │   (USB-to-RS232)        │     │
│  │  GPIO 23    │      │  GPIO 18    │      │   /dev/ttyUSB0          │     │
│  │  Pin 16     │      │  Pin 12     │      │   19200 baud            │     │
│  └──────┬──────┘      └──────┬──────┘      └────────┬────────────────┘     │
│         │                    │                      │                       │
│         └────────────────────┴──────────────────────┘                       │
│                              │                                              │
│                    ┌─────────▼──────────┐                                   │
│                    │  Raspberry Pi A+   │                                   │
│                    │  40-pin GPIO       │                                   │
│                    └────────────────────┘                                   │
│                                                                              │
│  Power: 2.5A micro-USB (Pi) + 5-6V 2A (Servos, separate PSU)               │
└──────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│                          SOFTWARE LAYER                                      │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │                        app.py (Flask REST API)                     │     │
│  │  Port 5000 | Endpoints: /api/session, /api/attendance, /api/status│     │
│  └────────────────────────────────────────────────────────────────────┘     │
│                 │              │              │              │              │
│        ┌────────▼───┐  ┌───────▼──────┐  ┌───▼────────┐  ┌─▼──────────┐   │
│        │  servo_    │  │ attendance_  │  │  rfid_     │  │  qr_       │   │
│        │ controller │  │ controller   │  │  reader    │  │ service    │   │
│        └────────┬───┘  └───────┬──────┘  └───┬────────┘  └─┬──────────┘   │
│                 │              │              │             │              │
│        ┌────────▼──────────────▼──────────────▼─────────────▼────────┐     │
│        │              pigpio daemon (hardware PWM)                   │     │
│        │              pyserial (USB serial communication)            │     │
│        │              qrcode + Pillow (QR generation)                │     │
│        │              threading (concurrent operations)               │     │
│        └──────────────────────────────────────────────────────────────┘     │
│                                                                              │
│  Configuration Files:                                                       │
│  • seat_map.json  → Maps seats to servo angles (0-180° range)              │
│  • tag_map.json   → Maps RFID tags to seat IDs                             │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│                        DATA FLOW & THREADING                                 │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Main Thread (Flask)          Background Thread (RFID)                      │
│  ┌──────────────┐             ┌──────────────────┐                         │
│  │              │             │                  │                         │
│  │ HTTP Request │────┐        │  Serial Read     │                         │
│  │   Handler    │    │        │  /dev/ttyUSB0    │                         │
│  └──────┬───────┘    │        └────────┬─────────┘                         │
│         │            │                 │                                   │
│         │            │                 │ Tag Detected                      │
│         │            │                 │                                   │
│         │            ▼                 ▼                                   │
│         │    ┌───────────────────────────────────┐                         │
│         │    │   threading.Lock (scan_lock)      │                         │
│         │    │   Prevents concurrent scans        │                         │
│         │    └───────────────┬───────────────────┘                         │
│         │                    │                                             │
│         │                    ▼                                             │
│         │    ┌────────────────────────────────┐                            │
│         │    │ Verification Window (5 seconds)│                            │
│         │    │ 1. Move servos to seat         │                            │
│         │    │ 2. Wait for RFID tag           │                            │
│         │    │ 3. Verify tag matches seat     │                            │
│         │    │ 4. Record attendance           │                            │
│         │    └────────────────────────────────┘                            │
│         │                                                                  │
│         ▼                                                                  │
│  ┌──────────────┐                                                          │
│  │ HTTP Response│                                                          │
│  │ (JSON)       │                                                          │
│  └──────────────┘                                                          │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│                     CLASSROOM PHYSICAL LAYOUT                                │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│                        Teacher's Desk / Projector                            │
│                          (Display QR Code Here)                              │
│                                                                              │
│  ┌─── SERVO POSITIONING (Top View) ───────────────────────────────────┐     │
│  │                                                                     │     │
│  │       X-axis: 0°              90°              180°                │     │
│  │          │                     │                  │                │     │
│  │    ┌─────┬──────────────┬──────────────┬─────────┐                │     │
│  │  A │ A1  │     A2       │     A3       │   A4    │  A5            │     │
│  │ 45°│ 0°  │    45°       │    90°       │  135°   │ 180°           │     │
│  │    ├─────┼──────────────┼──────────────┼─────────┤                │     │
│  │  B │ B1  │     B2       │     B3       │   B4    │  B5            │     │
│  │ 75°│                                                               │     │
│  │    ├─────┼──────────────┼──────────────┼─────────┤                │     │
│  │  C │ C1  │     C2       │     C3       │   C4    │  C5            │     │
│  │105°│                                                               │     │
│  │    ├─────┼──────────────┼──────────────┼─────────┤                │     │
│  │  D │ D1  │     D2       │     D3       │   D4    │  D5            │     │
│  │135°│                                    (Pi + RFID Reader)         │     │
│  │    └─────┴──────────────┴──────────────┴─────────┘                │     │
│  │                                                                     │     │
│  │  Y-axis                                                            │     │
│  │                                                                     │     │
│  └─────────────────────────────────────────────────────────────────────     │
│                                                                              │
│  Setup Notes:                                                               │
│  • Pi A+ and RFID reader positioned centrally (back of room)                │
│  • Servos point toward seating area                                         │
│  • Each seat has assigned RFID tag                                          │
│  • Full 0-180° range covers entire classroom                               │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│                          ATTENDANCE WORKFLOW                                 │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  1. Teacher → POST /api/session/create {"session_id": "CS101"}              │
│                                                                              │
│  2. System → Generates QR code with HMAC signature                           │
│       ┌─────────────┐                                                       │
│       │ ▓▓▓▓▓▓▓▓▓▓ │  QR contains:                                          │
│       │ ▓░░░░░░░░▓ │  • Session ID                                          │
│       │ ▓░▓▓▓▓▓░▓ │  • Timestamp                                            │
│       │ ▓░░░░░░░▓ │  • HMAC signature                                       │
│       │ ▓▓▓▓▓▓▓▓▓▓ │  • Valid for 10 minutes                                │
│       └─────────────┘                                                       │
│                                                                              │
│  3. Student → Scans QR code with mobile device                              │
│                                                                              │
│  4. Mobile App → Opens dashboard, shows available seats                     │
│                                                                              │
│  5. Student → Selects seat "B3", clicks "Claim Seat"                        │
│                                                                              │
│  6. Mobile → POST /api/attendance/claim                                     │
│      Body: {"session_id": "CS101", "seat_id": "B3"}                         │
│                                                                              │
│  7. System Actions (with scan_lock):                                        │
│      a. Lock RFID scanning (no other students can scan)                     │
│      b. Load seat position from seat_map.json: B3 = {x:90, y:75}           │
│      c. Move servos:                                                        │
│         - X-axis → 90° (center column)                                      │
│         - Y-axis → 75° (second row)                                         │
│      d. Wait for RFID tag (5-second window)                                 │
│                                                                              │
│  8. Student → Places RFID tag at reader location                            │
│                                                                              │
│  9. RFID Reader → Detects tag, sends to background thread                   │
│                                                                              │
│ 10. System Verification:                                                    │
│      a. Parse tag ID from serial data                                       │
│      b. Lookup tag in tag_map.json                                          │
│      c. Verify tag matches seat B3                                          │
│      d. Record: {"student": "tag_owner", "seat": "B3", "time": "..."}      │
│      e. Unlock scanning (release scan_lock)                                 │
│                                                                              │
│ 11. Response → {"success": true, "message": "Attendance verified"}          │
│                                                                              │
│ 12. Next student → Repeats process from step 5                              │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│                       RASPBERRY PI A+ RESOURCES                              │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  CPU Usage (single-core ARMv6 @ 700MHz):                                    │
│  ┌────────────────────────────────────────┐                                 │
│  │ ████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ 15% │  Idle                          │
│  │ ████████████████░░░░░░░░░░░░░░░░░░ 45% │  During servo movement         │
│  │ ███████████████████░░░░░░░░░░░░░░░ 55% │  During RFID scan              │
│  └────────────────────────────────────────┘                                 │
│                                                                              │
│  Memory Usage (512MB RAM):                                                  │
│  ┌────────────────────────────────────────┐                                 │
│  │ System:  120MB                         │                                 │
│  │ Python:   80MB                         │                                 │
│  │ Flask:    40MB                         │                                 │
│  │ Cached:  100MB                         │                                 │
│  │ Free:    172MB                         │                                 │
│  └────────────────────────────────────────┘                                 │
│                                                                              │
│  Disk Usage (8GB microSD):                                                  │
│  ┌────────────────────────────────────────┐                                 │
│  │ OS:        2.5GB                       │                                 │
│  │ Python:    500MB                       │                                 │
│  │ App:        50MB                       │                                 │
│  │ Logs:       10MB                       │                                 │
│  │ Free:      5.0GB                       │                                 │
│  └────────────────────────────────────────┘                                 │
│                                                                              │
│  Performance Characteristics:                                               │
│  • Lightweight operation optimized for low resources                        │
│  • Threading model efficient for I/O-bound tasks                            │
│  • Minimal memory footprint (no GUI, headless)                              │
│  • Can handle 20-30 simultaneous API requests                               │
│  • RFID detection latency: <100ms                                           │
│  • Servo movement time: ~2 seconds (0° to 180°)                             │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│                          NETWORK TOPOLOGY                                    │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────┐        │
│  │                        Internet                                 │        │
│  └────────────────────────┬────────────────────────────────────────┘        │
│                           │                                                 │
│                  ┌────────▼────────┐                                        │
│                  │  WiFi Router    │                                        │
│                  │  192.168.1.1    │                                        │
│                  └────────┬────────┘                                        │
│                           │                                                 │
│           ┌───────────────┼───────────────┬──────────────────┐             │
│           │               │               │                  │             │
│  ┌────────▼────────┐ ┌────▼──────────┐ ┌─▼──────────────┐ ┌─▼──────┐      │
│  │ Raspberry Pi A+ │ │  Teacher's    │ │  Student       │ │ Mobile │      │
│  │ 192.168.1.100   │ │  Laptop       │ │  Laptops       │ │ Phones │      │
│  │ Port 5000       │ │               │ │                │ │        │      │
│  └─────────────────┘ └───────────────┘ └────────────────┘ └────────┘      │
│                                                                              │
│  Local Access:                                                              │
│  • http://192.168.1.100:5000  (direct IP)                                   │
│  • http://raspberrypi.local:5000  (hostname)                                │
│                                                                              │
│  Remote Access (via ngrok):                                                 │
│  • https://abc123.ngrok.io  (tunneled to localhost:5000)                    │
│  • Secure HTTPS connection                                                  │
│  • Accessible from anywhere                                                 │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│                    API ENDPOINTS (Flask Server)                              │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  POST /api/session/create                                                   │
│  ├─ Body: {"session_id": "CS101-Lecture-5"}                                 │
│  └─ Response: {"success": true, "qr_code": "base64..."}                     │
│                                                                              │
│  POST /api/attendance/claim                                                 │
│  ├─ Body: {"session_id": "CS101", "seat_id": "B3", "qr_token": "..."}      │
│  └─ Response: {"success": true, "message": "Waiting for RFID..."}           │
│                                                                              │
│  GET /api/session/<session_id>                                              │
│  └─ Response: {"session_id": "CS101", "active": true, "records": [...]}     │
│                                                                              │
│  GET /api/status                                                            │
│  └─ Response: {"servos": "ready", "rfid": "connected", "lock": false}       │
│                                                                              │
│  POST /api/servo/test                                                       │
│  ├─ Body: {"x": 90, "y": 75}                                                │
│  └─ Response: {"success": true}                                             │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘

System Documentation:
• README_SETUP.md        - Main setup guide
• PI_A_PLUS_CONFIG.md    - Pi A+ specific configuration
• ARCHITECTURE.md        - This file (system overview)
```
