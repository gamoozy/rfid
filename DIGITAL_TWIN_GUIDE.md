# Digital Twin Integration Guide

Your classroom visualization (classroom_web.py) is now fully integrated with the Hybrid RFID-QR Attendance System!

## Quick Start

### Option 1: Run Integrated System (Recommended)
```bash
python3 app_integrated.py
```

This runs everything in one process:
- **Port 5000** - Complete system with Digital Twin visualization
- Real-time servo position display
- Live attendance tracking with A1-D5 seat layout
- All API endpoints + visualization

### Option 2: Run Separate Services
```bash
# Terminal 1 - Main API
python3 app.py

# Terminal 2 - Visualization Only
python3 classroom_web.py
```

## Accessing the Digital Twin

Open your browser to:
```
http://localhost:5000              (integrated system)
http://raspberrypi.local:5000     (from other devices on network)
```

## What You'll See

### Classroom Layout
```
     Col1   Col2   Col3   Col4   Col5
     0°     45°    90°    135°   180°
   ┌─────┬─────┬─────┬─────┬─────┐
A  │ A1  │ A2  │ A3  │ A4  │ A5  │  Y: 45°
   ├─────┼─────┼─────┼─────┼─────┤
B  │ B1  │ B2  │ B3  │ B4  │ B5  │  Y: 75°
   ├─────┼─────┼─────┼─────┼─────┤
C  │ C1  │ C2  │ C3  │ C4  │ C5  │  Y: 105°
   ├─────┼─────┼─────┼─────┼─────┤
D  │ D1  │ D2  │ D3  │ D4  │ D5  │  Y: 135°
   └─────┴─────┴─────┴─────┴─────┘
```

### Visual States

**Empty Seat** (Gray)
- No student assigned
- Status: "Empty"

**Scanning** (Yellow/Amber - Pulsing)
- Servo moving to position
- Waiting for RFID tag
- Status: "⏳ Scanning..."

**Verified** (Green - Glowing)
- Attendance confirmed
- RFID tag matched
- Status: "✓ Verified"

### Real-Time Data

**Servo Position Panel** (Top)
- Current X angle (0-180°)
- Current Y angle (0-180°)
- Target seat being scanned

**Statistics** (Below servo panel)
- Present: Number of verified students
- Total Seats: 20
- Attendance: Percentage

## Complete Workflow Demo

### 1. Create Session
```bash
curl -X POST http://localhost:5000/api/session/create \
  -H "Content-Type: application/json" \
  -d '{"session_id": "CS101-Demo"}'
```

**Digital Twin shows:**
- Status: "Session created: CS101-Demo"
- All seats gray (empty)
- Servo at center (90°, 90°)

### 2. Student Claims Seat B3
```bash
curl -X POST http://localhost:5000/api/attendance/claim \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "CS101-Demo",
    "seat_id": "B3",
    "qr_token": "..."
  }'
```

**Digital Twin shows:**
- Seat B3 turns **YELLOW** (scanning)
- Servo position: X: 90°, Y: 75°
- Target: "B3"
- Status: "Scanning seat B3 - Waiting for RFID tag..."

### 3. Student Scans RFID Tag
*(Automatic when tag is detected)*

**Digital Twin shows:**
- Seat B3 turns **GREEN** with glow effect
- Status changes to "✓ Verified"
- Present count increases: 1
- Attendance: 5%
- Servo returns to center

### 4. Multiple Students
As more students scan, the classroom fills with green seats in real-time!

## API Endpoints for Visualization

### Get Complete Classroom State
```bash
GET /api/classroom/state
```

Response:
```json
{
  "seats": {
    "A1": {"x": 0, "y": 45},
    "A2": {"x": 45, "y": 45},
    ...
  },
  "attendance": {
    "B3": {"timestamp": "2025-12-17T...", "status": "verified"}
  },
  "servo_position": {"x": 90, "y": 75},
  "scanning_seat": "B3",
  "active_session": "CS101-Demo"
}
```

### Reset Session
```bash
POST /api/reset
```

**Digital Twin shows:**
- All seats turn gray
- Present count: 0
- Servo returns to 90°, 90°
- Status: "Session reset - System ready"

## Features

### Live Updates
- Polls every 300ms for ultra-responsive display
- Smooth animations and transitions
- No page refresh needed

### Servo Tracking
- Real-time X/Y angle display
- Shows target seat being scanned
- Visual indication on classroom grid

### Color-Coded Status
- 🔵 Blue glow: Target seat (servo aimed)
- 🟡 Yellow pulsing: Currently scanning
- 🟢 Green glow: Verified attendance
- ⚫ Gray: Empty seat

### Responsive Design
- Works on desktop, tablet, mobile
- Adapts to screen size
- Touch-friendly interface

## Troubleshooting

### Can't see visualization
```bash
# Check if Flask is running
curl http://localhost:5000/api/status

# Check firewall (Pi)
sudo ufw allow 5000

# Access from other device
http://192.168.1.xxx:5000  # Use Pi's IP
```

### Seats not updating
- Check browser console (F12) for errors
- Verify seat_map.json exists
- Ensure tag_map.json has correct mappings

### Servo position not showing
- Verify pigpiod is running: `sudo systemctl status pigpiod`
- Check servo connections (GPIO 23, 18)
- Test manually: `python3 servo_controller.py`

## Mobile Access

### Using ngrok
```bash
ngrok http 5000
```

Access from anywhere:
```
https://abc123.ngrok.io
```

The Digital Twin works perfectly on mobile browsers!

## Customization

### Change Update Rate
Edit `templates/classroom.html`:
```javascript
// Poll every 300ms (default)
setInterval(updateClassroomState, 300);

// Slower (500ms) - saves bandwidth
setInterval(updateClassroomState, 500);

// Faster (100ms) - more responsive
setInterval(updateClassroomState, 100);
```

### Change Colors
Edit CSS in `templates/classroom.html`:
```css
.desk.verified {
    background: linear-gradient(135deg, #4CAF50 0%, #66BB6A 100%);
    /* Change to blue: */
    background: linear-gradient(135deg, #2196F3 0%, #64B5F6 100%);
}
```

## Production Tips

1. **Large displays**: Project on screen/TV for whole classroom
2. **Multiple monitors**: Show on instructor station + projector
3. **Mobile dashboard**: Students can see their own status
4. **Logging**: All attendance data saved to database
5. **Analytics**: Export to CSV for attendance reports

## Files Modified

- ✅ `classroom_web.py` - Updated to use A1-D5 layout, servo tracking
- ✅ `templates/classroom.html` - Complete redesign with 4×5 grid, real-time updates
- ✅ `app_integrated.py` - NEW: All-in-one integrated system

## Next Steps

1. **Start the system**: `python3 app_integrated.py`
2. **Open browser**: http://localhost:5000
3. **Create a session**: Use API or curl
4. **Test with one student**: Watch the visualization!
5. **Add more students**: See the classroom fill up in real-time

---

**Your Digital Twin is ready! 🎓✨**

The classroom visualization now shows:
- Real 0-180° servo positions
- A1-D5 seat layout (4 rows × 5 columns)
- Live scanning status with colors
- Attendance statistics
- Beautiful, responsive design

Perfect for demonstrations, live monitoring, and impressing stakeholders! 🚀
