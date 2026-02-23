#!/usr/bin/env python3
"""
Integrated Hybrid RFID-QR Attendance System with Digital Twin Visualization
Combines app.py functionality with classroom_web.py for real-time monitoring
"""

import logging
import signal
import sys
import json
import time
from datetime import datetime
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS

# Import system components
# Switch to ESP32 servo controller (Raspberry Pi damaged)
from servo_controller_esp32 import ServoController
from qr_service import QRService
from attendance_controller import AttendanceController, VerificationRequest
from rfid_reader import RFIDReader

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)

# Flask app
app = Flask(__name__)
CORS(app)

# Configuration
SEAT_MAP_FILE = 'seat_map.json'
TAG_MAP_FILE = 'tag_map.json'
QR_SECRET_KEY = 'your-secret-key-change-in-production'

# System components
servo_controller = None
qr_service = None
attendance_controller = None
rfid_reader = None

# Global state for visualization
classroom_state = {
    'attendance': {},  # {seat_id: {student, timestamp, status}}
    'servo_position': {'x': 135, 'y': 135},  # Center for 270° servos (FT5835M) limited to 180° range
    'scanning_seat': None,
    'active_session': None
}


def load_config():
    """Load configuration files"""
    with open(SEAT_MAP_FILE, 'r') as f:
        seat_map = json.load(f)
    with open(TAG_MAP_FILE, 'r') as f:
        tag_map = json.load(f)
    return seat_map, tag_map


def initialize_system():
    """Initialize all system components"""
    global servo_controller, qr_service, attendance_controller, rfid_reader
    
    logging.info("Initializing Hybrid RFID-QR Attendance System...")
    
    # Load configuration
    seat_map, tag_map = load_config()
    
    # Initialize servo controller
    servo_controller = ServoController()
    if not servo_controller.connect():
        logging.error("Failed to connect to servo controller")
        return False
    logging.info("✓ Servo controller initialized")
    
    # Initialize QR service
    qr_service = QRService(secret_key=QR_SECRET_KEY)
    logging.info("✓ QR service initialized")
    
    # Initialize RFID reader
    rfid_reader = RFIDReader()
    if not rfid_reader.connect():
        logging.error("Failed to connect to RFID reader")
        return False
    logging.info("✓ RFID reader connected")
    
    # Initialize attendance controller
    attendance_controller = AttendanceController(
        servo_controller=servo_controller,
        seat_map=seat_map,
        tag_map=tag_map,
        verification_timeout=5.0
    )
    
    # Register RFID callback
    rfid_reader.register_callback(attendance_controller.on_tag_detected)
    rfid_reader.start()
    logging.info("✓ Attendance controller initialized")
    
    return True


def update_visualization_state(seat_id=None, status=None, servo_pos=None):
    """Update the classroom visualization state"""
    global classroom_state
    
    if seat_id and status == 'verified':
        classroom_state['attendance'][seat_id] = {
            'timestamp': datetime.now().isoformat(),
            'status': 'verified'
        }
        classroom_state['scanning_seat'] = None
    
    if seat_id and status == 'scanning':
        classroom_state['scanning_seat'] = seat_id
    
    if servo_pos:
        classroom_state['servo_position'] = servo_pos


# ============= Digital Twin Visualization Routes =============

@app.route('/')
def index():
    """Serve the classroom visualization page"""
    return render_template('classroom.html')


@app.route('/api/classroom/state')
def get_classroom_state():
    """Get complete classroom state for visualization"""
    seat_map, _ = load_config()
    
    return jsonify({
        'seats': seat_map,
        'attendance': classroom_state['attendance'],
        'servo_position': classroom_state['servo_position'],
        'scanning_seat': classroom_state['scanning_seat'],
        'active_session': classroom_state['active_session'],
        'timestamp': datetime.now().isoformat()
    })


# ============= Main API Routes =============

@app.route('/api/session/create', methods=['POST'])
def create_session():
    """Create a new attendance session and generate QR code"""
    try:
        data = request.get_json()
        session_id = data.get('session_id')
        
        if not session_id:
            return jsonify({'success': False, 'error': 'session_id required'}), 400
        
        # Generate QR code
        qr_data = qr_service.generate_session_qr(session_id)
        
        # Update state
        classroom_state['active_session'] = session_id
        classroom_state['attendance'] = {}
        classroom_state['scanning_seat'] = None
        
        logging.info(f"Session created: {session_id}")
        
        return jsonify({
            'success': True,
            'session_id': session_id,
            'qr_code': qr_data['qr_code_base64'],
            'qr_image_path': qr_data['qr_image_path'],
            'expires_at': qr_data['expires_at']
        })
        
    except Exception as e:
        logging.error(f"Error creating session: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/attendance/claim', methods=['POST'])
def claim_seat():
    """Student claims a seat - initiates verification process"""
    try:
        data = request.get_json()
        seat_id = data.get('seat_id')
        
        if not seat_id:
            return jsonify({'success': False, 'error': 'seat_id required'}), 400
        
        # Use active session or create default
        session_id = classroom_state.get('active_session') or 'default-session'
        
        # Create verification request
        verification_request = VerificationRequest(
            student_id=f"student-{seat_id}",  # Simple student ID based on seat
            seat_id=seat_id,
            session_id=session_id,
            timestamp=time.time()
        )
        
        # Update visualization - seat is now scanning
        seat_map, _ = load_config()
        servo_pos = seat_map.get(seat_id)
        
        # Move servos to the seat position (both X and Y axes)
        if servo_pos and 'x' in servo_pos and 'y' in servo_pos:
            servo_controller.move_to_seat(servo_pos)
            logging.info(f"Servos moved to seat {seat_id}: X={servo_pos['x']}°, Y={servo_pos['y']}°")
        
        update_visualization_state(seat_id, 'scanning', servo_pos)
        
        # Start verification process
        result = attendance_controller.verify_attendance(verification_request)
        
        # Convert VerificationResult to dict
        response = {
            'success': result.status.value == 'success',
            'status': result.status.value,
            'seat_id': result.seat_id,
            'message': result.message
        }
        
        if response['success']:
            # Update visualization - seat is now verified
            update_visualization_state(seat_id, 'verified')
            
        return jsonify(response)
        
    except Exception as e:
        logging.error(f"Error claiming seat: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/session/<session_id>', methods=['GET'])
def get_session(session_id):
    """Get session details and attendance records"""
    try:
        # Filter attendance records for this session
        session_records = {
            seat: record for seat, record in classroom_state['attendance'].items()
            if classroom_state['active_session'] == session_id
        }
        
        return jsonify({
            'success': True,
            'session_id': session_id,
            'active': classroom_state['active_session'] == session_id,
            'records': session_records,
            'total_present': len(session_records)
        })
        
    except Exception as e:
        logging.error(f"Error getting session: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/status', methods=['GET'])
def get_status():
    """Get system status"""
    try:
        return jsonify({
            'success': True,
            'servos': {
                'connected': servo_controller and servo_controller._connected,
                'position': classroom_state['servo_position']
            },
            'rfid': {
                'connected': rfid_reader and rfid_reader.connected,
                'port': rfid_reader.port if rfid_reader else None
            },
            'scan_lock': attendance_controller.scan_lock.locked() if attendance_controller else False,
            'active_session': classroom_state['active_session'],
            'scanning_seat': classroom_state['scanning_seat']
        })
        
    except Exception as e:
        logging.error(f"Error getting status: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/servo/test', methods=['POST'])
def test_servo():
    """Test servo movement"""
    try:
        data = request.get_json()
        x = data.get('x', 90)
        y = data.get('y', 90)
        
        servo_controller.move_to(x, y)
        update_visualization_state(servo_pos={'x': x, 'y': y})
        
        return jsonify({'success': True, 'position': {'x': x, 'y': y}})
        
    except Exception as e:
        logging.error(f"Error testing servo: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/reset', methods=['POST', 'GET'])
def reset_session():
    """Reset attendance session"""
    try:
        classroom_state['attendance'] = {}
        classroom_state['scanning_seat'] = None
        classroom_state['active_session'] = None
        
        # Reset servos to center (270° servos limited to 180° range)
        servo_controller.move_to(135, 135)
        update_visualization_state(servo_pos={'x': 135, 'y': 135})
        
        logging.info("Session reset")
        return jsonify({'success': True, 'status': 'reset'})
        
    except Exception as e:
        logging.error(f"Error resetting session: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# Custom callback for attendance verification success
def on_attendance_verified(seat_id):
    """Called when attendance is successfully verified"""
    update_visualization_state(seat_id, 'verified')
    logging.info(f"✓ Attendance verified for seat {seat_id}")


def shutdown_handler(signum, frame):
    """Graceful shutdown"""
    logging.info("\nShutting down system...")
    
    if rfid_reader:
        rfid_reader.stop()
    if servo_controller:
        servo_controller.disconnect()
    
    logging.info("System shutdown complete")
    sys.exit(0)


if __name__ == '__main__':
    # Register signal handlers
    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)
    
    print("=" * 60)
    print("🎓 Hybrid RFID-QR Attendance System")
    print("   with Digital Twin Visualization")
    print("=" * 60)
    
    # Initialize system
    if not initialize_system():
        print("\n❌ Failed to initialize system")
        sys.exit(1)
    
    print("\n✅ System initialized successfully!")
    print("\nStarting Flask server...")
    print("\nAccess via:")
    print("  • Classroom View: http://localhost:5000")
    print("  • API Base: http://localhost:5000/api")
    print("  • Status: http://localhost:5000/api/status")
    print("\nFor mobile access, run:")
    print("  ngrok http 5000")
    print("\nPress Ctrl+C to stop")
    print("=" * 60)
    print()
    
    # Register callback for attendance verification
    def verification_callback(tag_id):
        """Called when tag is detected during verification"""
        logging.info(f"Tag detected: {tag_id}")
    
    attendance_controller.register_tag_callback(verification_callback)
    
    # Run Flask app
    app.run(debug=False, host='0.0.0.0', port=5000, threaded=True)
