#!/usr/bin/env python3
"""
Web-based Classroom Visualization (Digital Twin)
Real-time RFID-QR attendance display with servo positioning
Integrated with Hybrid RFID-QR Attendance System with RFID Reader
"""

from flask import Flask, render_template, jsonify
import json
import csv
import threading
import logging
from pathlib import Path
from datetime import datetime
import sys

# Add reader_capture module functions
import serial
import serial.tools.list_ports
import sqlite3
import time
from typing import Optional, Dict
from flask import request

app = Flask(__name__)

# Configuration
SEAT_MAP_FILE = 'seat_map.json'
TAG_MAP_FILE = 'tag_map.json'
TAGMAP_CSV_FILE = 'tagmap.csv'
RFID_PORT_AUTO = True  # Auto-detect RFID reader port
RFID_BAUD = 19200  # R16-12DB passive mode
ESP32_PORT = '/dev/cu.usbserial-0001'  # ESP32 servo controller
ESP32_BAUD = 115200
RFID_PORT = '/dev/cu.usbserial-210'  # CH9102 RFID Reader (not the ESP32!)

# Seat positions mapping (1-20 numbered seats with servo angles)
SEAT_POSITIONS = {
    # Row 1
    '1': {'x': 90, 'y': 90},
    '2': {'x': 135, 'y': 90},
    '3': {'x': 180, 'y': 90},
    # Row 2
    '4': {'x': 90, 'y': 105},
    '5': {'x': 135, 'y': 105},
    '6': {'x': 180, 'y': 105},
    # Row 3
    '7': {'x': 90, 'y': 120},
    '8': {'x': 135, 'y': 120},
    '9': {'x': 180, 'y': 120},
    # Row 4
    '10': {'x': 90, 'y': 135},
    '11': {'x': 135, 'y': 135},
    '12': {'x': 180, 'y': 135},
    # Row 5
    '13': {'x': 90, 'y': 150},
    '14': {'x': 135, 'y': 150},
    '15': {'x': 180, 'y': 150},
    # Row 6
    '16': {'x': 90, 'y': 165},
    '17': {'x': 135, 'y': 165},
    '18': {'x': 180, 'y': 165},
    # Row 7
    '19': {'x': 105, 'y': 180},
    '20': {'x': 165, 'y': 180}
}

# Global state (shared with main app via file/API)
attendance_records = {}  # {seat_id: {student, timestamp, status}}
scanned_seats = set()  # Track which seats have been scanned
reader_thread = None
reader_running = False
tag_to_seat_map = {}  # TagID -> SeatID mapping
seat_to_tag_map = {}  # SeatID -> TagID mapping (reverse lookup)
current_target_seat = None  # The seat we're currently trying to scan
servo_position = {'x': 135, 'y': 180}  # Current servo position
servo_serial = None  # ESP32 serial connection
inverse_logic_seats = {'1', '2', '3'}  # Seats with inverse logic (tag detected = absent)
def load_seat_map():
    """Load seat map with servo positions"""
    try:
        with open(SEAT_MAP_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def load_tag_map():
    """Load TagID to SeatID mapping from CSV"""
    global tag_to_seat_map, seat_to_tag_map
    try:
        with open(TAGMAP_CSV_FILE, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                tag_id = row['TagID'].strip()
                seat_id = row['SeatID'].strip()
                tag_to_seat_map[tag_id] = seat_id
                seat_to_tag_map[seat_id] = tag_id  # Reverse mapping
        logging.info(f"Loaded {len(tag_to_seat_map)} tag mappings")
    except FileNotFoundError:
        logging.warning(f"TagMap file not found: {TAGMAP_CSV_FILE}")
    except Exception as e:
        logging.error(f"Error loading tag map: {e}")

def detect_rfid_port():
    """Auto-detect RFID reader port (CH9102 USB-to-Serial)"""
    # First try the known RFID port
    if RFID_PORT and Path(RFID_PORT).exists():
        logging.info(f"Using configured RFID port: {RFID_PORT}")
        return RFID_PORT
    
    # Otherwise scan for it (excluding ESP32)
    ports = serial.tools.list_ports.comports()
    for port in ports:
        # Skip the ESP32 servo controller port
        if port.device == ESP32_PORT:
            continue
        if 'usbserial' in port.device.lower() or 'ch9102' in port.description.lower():
            logging.info(f"Auto-detected RFID port: {port.device}")
            return port.device
    return None

def connect_servo():
    """Connect to ESP32 servo controller"""
    global servo_serial
    try:
        servo_serial = serial.Serial(ESP32_PORT, ESP32_BAUD, timeout=1)
        time.sleep(0.5)  # Wait for ESP32 to initialize
        logging.info(f"Servo controller connected on {ESP32_PORT}")
        return True
    except Exception as e:
        logging.error(f"Failed to connect to servo controller: {e}")
        return False

def move_servo(x, y):
    """Move servos to specific position"""
    global servo_position, servo_serial
    if not servo_serial or not servo_serial.is_open:
        logging.warning("Servo not connected")
        return False
    
    try:
        command = f'B{int(x)},{int(y)}\n'
        servo_serial.write(command.encode())
        time.sleep(0.1)  # Small delay for servo movement
        servo_position = {'x': int(x), 'y': int(y)}
        logging.info(f"Servo moved to X={x}°, Y={y}°")
        return True
    except Exception as e:
        logging.error(f"Error moving servo: {e}")
        return False

def servo_monitor_loop():
    """Background thread to monitor servo position from ESP32"""
    global servo_position, servo_serial
    
    while reader_running:
        try:
            # Request status from ESP32
            if servo_serial and servo_serial.is_open:
                servo_serial.write(b'S\n')  # Status command
                time.sleep(0.05)
                
                # Read response if available
                if servo_serial.in_waiting > 0:
                    response = servo_serial.readline().decode().strip()
                    # Parse response like "X:135 Y:180"
                    if 'X:' in response and 'Y:' in response:
                        try:
                            x_part = response.split('X:')[1].split()[0]
                            y_part = response.split('Y:')[1].split()[0]
                            servo_position['x'] = int(x_part)
                            servo_position['y'] = int(y_part)
                        except:
                            pass
        except Exception as e:
            logging.debug(f"Servo monitor error: {e}")
        
        time.sleep(0.5)  # Update every 500ms

def rfid_reader_loop():
    """Background thread that reads RFID tags and updates attendance"""
    global reader_running, scanned_seats, attendance_records, current_target_seat
    
    port = detect_rfid_port()
    if not port:
        logging.error("No RFID reader port detected")
        return
    
    logging.info(f"RFID reader starting on {port} at {RFID_BAUD} baud")
    
    try:
        ser = serial.Serial(port, RFID_BAUD, timeout=1)
        last_tags = {}  # Deduplication: {tag_id: last_time}
        DEDUPE_WINDOW = 0.8  # seconds
        
        while reader_running:
            try:
                if ser.in_waiting > 0:
                    raw_data = ser.read(ser.in_waiting)
                    
                    # R16-12DB in passive mode (19200 baud) outputs continuous hex stream
                    # NOT binary frames with 0xA0 headers!
                    # Parse as continuous hex stream like reader_capture.py does
                    
                    if len(raw_data) >= 16:  # Minimum pattern length
                        # Remove null bytes
                        cleaned_data = bytes(b for b in raw_data if b != 0x00)
                        
                        if len(cleaned_data) >= 12:  # Minimum EPC length
                            # Convert to hex string - this IS the tag ID
                            tag_hex = cleaned_data.hex().upper()
                            
                            # Check deduplication
                            current_time = time.time()
                            if tag_hex in last_tags:
                                if current_time - last_tags[tag_hex] < DEDUPE_WINDOW:
                                    time.sleep(0.1)
                                    continue
                            
                            last_tags[tag_hex] = current_time
                            
                            # Map to seat ID
                            seat_id = tag_to_seat_map.get(tag_hex, "UNKNOWN")
                            
                            # Only process if we have a target seat and this tag matches it
                            if current_target_seat and seat_id != "UNKNOWN":
                                if seat_id == current_target_seat:
                                    scanned_seats.add(seat_id)
                                    attendance_records[seat_id] = {
                                        'tag_id': tag_hex,
                                        'timestamp': datetime.now().isoformat(),
                                        'status': 'present'
                                    }
                                    logging.info(f"✓ Scanned: {seat_id} (Tag: {tag_hex}) - MATCH!")
                                    # Clear target after successful scan
                                    current_target_seat = None
                                else:
                                    logging.debug(f"Ignoring tag for seat {seat_id} (waiting for {current_target_seat})")
                            elif not current_target_seat:
                                logging.debug(f"No target seat set - ignoring all scans")
                
                time.sleep(0.1)
            
            except Exception as e:
                logging.error(f"Error in RFID read loop: {e}")
                time.sleep(1)
    
    except Exception as e:
        logging.error(f"Failed to open RFID reader: {e}")
    finally:
        if 'ser' in locals() and ser.is_open:
            ser.close()
        logging.info("RFID reader stopped")


@app.route('/')
def index():
    """Serve the main page"""
    return render_template('classroom.html')


@app.route('/api/servo/position')
def get_servo_position():
    """Get current servo position"""
    return jsonify({
        'x': servo_position['x'],
        'y': servo_position['y'],
        'target_seat': current_target_seat
    })


@app.route('/api/classroom/state')
def get_classroom_state():
    """API endpoint to get complete classroom state"""
    # Generate simple 1-20 seat map
    seats = {}
    for i in range(1, 21):
        seats[str(i)] = {
            'id': str(i),
            'occupied': str(i) in scanned_seats
        }
    
    return jsonify({
        'seats': seats,
        'attendance': attendance_records,
        'total_present': len(scanned_seats),
        'current_target_seat': current_target_seat,
        'servo_position': servo_position,
        'scanning_seat': current_target_seat,
        'timestamp': datetime.now().isoformat()
    })


@app.route('/api/classroom/attendance')
def get_attendance():
    """Get current attendance records"""
    return jsonify({
        'records': attendance_records,
        'scanned_seats': list(scanned_seats),
        'total_present': len(scanned_seats),
        'current_target_seat': current_target_seat,
        'timestamp': datetime.now().isoformat()
    })


@app.route('/api/seats')
def get_seats():
    """Get all 20 seats with their status"""
    seats = []
    for i in range(1, 21):
        seat_id = str(i)
        seats.append({
            'id': seat_id,
            'occupied': seat_id in scanned_seats,
            'is_target': seat_id == current_target_seat,
            'info': attendance_records.get(seat_id, None)
        })
    
    return jsonify({
        'seats': seats,
        'total': 20,
        'occupied': len(scanned_seats),
        'current_target_seat': current_target_seat
    })


@app.route('/api/set_seat/<seat_id>', methods=['POST'])
def set_target_seat(seat_id):
    """Set the current seat to scan for"""
    global current_target_seat
    
    # Validate seat_id
    if seat_id not in [str(i) for i in range(1, 21)]:
        return jsonify({'error': 'Invalid seat ID', 'valid_range': '1-20'}), 400
    
    # Check if seat has a mapped tag
    if seat_id not in seat_to_tag_map:
        return jsonify({'error': f'Seat {seat_id} has no tag mapping in tagmap.csv'}), 400
    
    # Get servo position for this seat
    if seat_id not in SEAT_POSITIONS:
        return jsonify({'error': f'Seat {seat_id} has no servo position defined'}), 400
    
    pos = SEAT_POSITIONS[seat_id]
    
    # Move servos to seat position
    if not move_servo(pos['x'], pos['y']):
        return jsonify({'error': 'Failed to move servos'}), 500
    
    current_target_seat = seat_id
    expected_tag = seat_to_tag_map[seat_id]
    
    logging.info(f"Target seat set to: {seat_id} at X={pos['x']}°, Y={pos['y']}° (expecting tag: {expected_tag})")
    
    return jsonify({
        'status': 'success',
        'target_seat': current_target_seat,
        'expected_tag': expected_tag,
        'servo_position': pos,
        'message': f'Now scanning for seat {seat_id}'
    })


@app.route('/api/attendance/claim', methods=['POST'])
def claim_seat():
    """Claim a seat - moves servo and waits for RFID scan"""
    data = request.get_json()
    seat_id = data.get('seat_id')
    
    if not seat_id:
        return jsonify({'success': False, 'message': 'Missing seat_id'}), 400
    
    # Validate seat_id
    if seat_id not in [str(i) for i in range(1, 21)]:
        return jsonify({'success': False, 'message': f'Invalid seat ID: {seat_id}'}), 400
    
    # Check if seat has servo position
    if seat_id not in SEAT_POSITIONS:
        return jsonify({'success': False, 'message': f'Seat {seat_id} has no position defined'}), 400
    
    # Check if seat has tag mapping
    if seat_id not in seat_to_tag_map:
        return jsonify({'success': False, 'message': f'Seat {seat_id} has no tag mapping'}), 400
    
    # Move servos
    pos = SEAT_POSITIONS[seat_id]
    if not move_servo(pos['x'], pos['y']):
        return jsonify({'success': False, 'message': 'Servo movement failed'}), 500
    
    # Set as target seat for RFID scanning
    global current_target_seat
    current_target_seat = seat_id
    expected_tag = seat_to_tag_map[seat_id]
    
    # Check if this is an inverse logic seat (1, 2, 3)
    is_inverse = seat_id in inverse_logic_seats
    
    if is_inverse:
        logging.info(f"Checking seat {seat_id} (INVERSE LOGIC) - tag detected = ABSENT, tag not detected = PRESENT")
    else:
        logging.info(f"Claiming seat {seat_id} (NORMAL LOGIC) - waiting for tag {expected_tag}")
    
    # Wait and check for tag
    timeout = 5  # 5 seconds scan period
    start_time = time.time()
    tag_detected = False
    
    while time.time() - start_time < timeout:
        if seat_id in scanned_seats:
            tag_detected = True
            break
        time.sleep(0.2)
    
    # Clear target
    current_target_seat = None
    
    # Apply logic based on seat type
    if is_inverse:
        # INVERSE LOGIC: Tag detected = ABSENT, Tag NOT detected = PRESENT
        if tag_detected:
            # Tag is visible = chair is empty = student is ABSENT
            scanned_seats.discard(seat_id)  # Remove from scanned
            if seat_id in attendance_records:
                del attendance_records[seat_id]
            return jsonify({
                'success': True,
                'seat_id': seat_id,
                'status': 'absent',
                'message': f'Seat {seat_id}: Tag detected - Student ABSENT (chair empty)',
                'inverse_logic': True
            })
        else:
            # Tag NOT visible = blocked by student = student is PRESENT
            scanned_seats.add(seat_id)
            attendance_records[seat_id] = {
                'tag_id': expected_tag,
                'timestamp': datetime.now().isoformat(),
                'status': 'present'
            }
            return jsonify({
                'success': True,
                'seat_id': seat_id,
                'status': 'present',
                'message': f'Seat {seat_id}: Tag blocked - Student PRESENT',
                'inverse_logic': True,
                'attendance': attendance_records[seat_id]
            })
    else:
        # NORMAL LOGIC: Tag detected = PRESENT
        if tag_detected:
            return jsonify({
                'success': True,
                'seat_id': seat_id,
                'status': 'present',
                'message': f'Seat {seat_id} verified!',
                'attendance': attendance_records.get(seat_id)
            })
        else:
            return jsonify({
                'success': False,
                'message': f'Timeout - tag not detected for seat {seat_id}. Please scan again.'
            }), 408


@app.route('/api/clear_target', methods=['POST'])
def clear_target_seat():
    """Clear the target seat (stop scanning)"""
    global current_target_seat
    current_target_seat = None
    logging.info("Target seat cleared - scanner paused")
    return jsonify({'status': 'success', 'message': 'Target seat cleared'})


# These functions would be called by the main app.py
def reset_session():
    """Reset attendance session"""
    global attendance_records, scanned_seats, current_target_seat
    attendance_records = {}
    scanned_seats = set()
    current_target_seat = None


@app.route('/api/reset')
def reset():
    """Reset the attendance session"""
    reset_session()
    return jsonify({'status': 'reset', 'total_present': 0})


if __name__ == '__main__':
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    print("="*60)
    print("🎓 Classroom Attendance System with RFID")
    print("="*60)
    
    # Load tag map
    load_tag_map()
    
    # Check RFID port
    rfid_port = detect_rfid_port()
    if rfid_port:
        print(f"✓ RFID reader port: {rfid_port}")
    else:
        print(f"⚠️  Warning: RFID reader not detected")
    
    # Connect to servo controller
    if not connect_servo():
        print("⚠️  Warning: Servo controller not connected")
        print(f"   Expected at: {ESP32_PORT}")
    else:
        print(f"✓ Servo controller: {ESP32_PORT}")
        # Center servos
        move_servo(135, 180)
    
    # Start RFID reader thread
    reader_running = True
    reader_thread = threading.Thread(target=rfid_reader_loop, daemon=True)
    reader_thread.start()
    
    # Start servo monitor thread
    servo_monitor_thread = threading.Thread(target=servo_monitor_loop, daemon=True)
    servo_monitor_thread.start()
    
    print("✓ RFID reader started")
    print("✓ Servo monitor started")
    print("\nStarting web server...")
    print("\n👉 Open your browser to: http://localhost:8080")
    print("\nFeatures:")
    print("  • Real-time RFID scanning")
    print("  • 20 seats (numbered 1-20)")
    print("  • Automatic tag-to-seat mapping")
    print("  • Servo-controlled positioning")
    print("  • Live attendance tracking")
    print("\nPress Ctrl+C to stop")
    print("="*60)
    print()
    
    try:
        app.run(debug=False, host='0.0.0.0', port=8080)
    except KeyboardInterrupt:
        print("\n\nShutting down...")
        reader_running = False
        if reader_thread:
            reader_thread.join(timeout=2)
        if servo_serial and servo_serial.is_open:
            # Center servos before exit
            move_servo(135, 180)
            servo_serial.close()
        print("✓ Stopped")
