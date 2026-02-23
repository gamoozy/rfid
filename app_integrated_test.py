#!/usr/bin/env python3
"""
Integrated Hybrid RFID-QR Attendance System with Digital Twin Visualization - TEST MODE
Testing version that works without RFID reader hardware
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
from attendance_controller import AttendanceController, VerificationRequest

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

# System components
servo_controller = None
attendance_controller = None
rfid_reader = None

# Global state for visualization
classroom_state = {
    'attendance': {},  # {seat_id: {student, timestamp, status}}
    'servo_position': {'x': 90, 'y': 90},
    'scanning_seat': None,
    'active_session': None
}


# ============= Mock Classes for Testing =============

class MockServoController:
    """Mock servo controller for testing without hardware"""
    
    def __init__(self):
        self._connected = False
        self.current_x = 90
        self.current_y = 90
    
    def connect(self):
        """Simulate successful connection"""
        self._connected = True
        logging.info("Mock servo controller connected (no hardware)")
        return True
    
    def disconnect(self):
        """Simulate disconnect"""
        self._connected = False
        logging.info("Mock servo controller disconnected")
    
    def move_to(self, x, y):
        """Simulate servo movement"""
        self.current_x = x
        self.current_y = y
        logging.info(f"Mock servo moved to ({x}, {y})")
        time.sleep(0.1)  # Simulate movement delay
        return True
    
    def get_position(self):
        """Get current position"""
        return (self.current_x, self.current_y)


class MockRFIDReader:
    """Mock RFID reader for testing without hardware"""
    
    def __init__(self):
        self.connected = False
        self.port = "MOCK_PORT"
        self._callback = None
        self._running = False
    
    def connect(self):
        """Simulate successful connection"""
        self.connected = True
        logging.info("Mock RFID reader connected (no hardware)")
        return True
    
    def disconnect(self):
        """Simulate disconnect"""
        self.connected = False
        self._running = False
        logging.info("Mock RFID reader disconnected")
    
    def register_callback(self, callback):
        """Register callback for tag detection"""
        self._callback = callback
    
    def start(self):
        """Start reading (mock)"""
        self._running = True
        logging.info("Mock RFID reader started")
    
    def stop(self):
        """Stop reading"""
        self._running = False
        logging.info("Mock RFID reader stopped")
    
    def simulate_tag_detection(self, tag_id):
        """Manually trigger a tag detection (for testing)"""
        if self._callback and self._running:
            logging.info(f"Simulating tag detection: {tag_id}")
            self._callback(tag_id)
            return True
        return False


def load_config():
    """Load configuration files"""
    with open(SEAT_MAP_FILE, 'r') as f:
        seat_map = json.load(f)
    with open(TAG_MAP_FILE, 'r') as f:
        tag_map = json.load(f)
    return seat_map, tag_map


def initialize_system():
    """Initialize all system components (with mock hardware)"""
    global servo_controller, attendance_controller, rfid_reader
    
    logging.info("Initializing Hybrid RFID-QR Attendance System (TEST MODE)...")
    
    # Load configuration
    seat_map, tag_map = load_config()
    
    # Initialize MOCK servo controller
    servo_controller = MockServoController()
    if not servo_controller.connect():
        logging.error("Failed to connect to mock servo controller")
        return False
    logging.info("✓ Mock servo controller initialized")
    
    # Initialize MOCK RFID reader
    rfid_reader = MockRFIDReader()
    if not rfid_reader.connect():
        logging.error("Failed to connect to mock RFID reader")
        return False
    logging.info("✓ Mock RFID reader connected")
    
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
    """Create a new attendance session (TEST MODE - no QR code)"""
    try:
        data = request.get_json()
        session_id = data.get('session_id')
        
        if not session_id:
            return jsonify({'success': False, 'error': 'session_id required'}), 400
        
        # Update state
        classroom_state['active_session'] = session_id
        classroom_state['attendance'] = {}
        classroom_state['scanning_seat'] = None
        
        logging.info(f"Session created: {session_id}")
        
        return jsonify({
            'success': True,
            'session_id': session_id,
            'test_mode': True,
            'message': 'Session created in test mode (no QR code)'
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
            'test_mode': True,
            'servos': {
                'connected': servo_controller and servo_controller._connected,
                'position': classroom_state['servo_position'],
                'mock': True
            },
            'rfid': {
                'connected': rfid_reader and rfid_reader.connected,
                'port': rfid_reader.port if rfid_reader else None,
                'mock': True
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
        
        # Reset servos to center
        servo_controller.move_to(90, 90)
        update_visualization_state(servo_pos={'x': 90, 'y': 90})
        
        logging.info("Session reset")
        return jsonify({'success': True, 'status': 'reset'})
        
    except Exception as e:
        logging.error(f"Error resetting session: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ============= Testing Routes =============

@app.route('/api/test/simulate_tag', methods=['POST'])
def simulate_tag():
    """Simulate RFID tag detection for testing"""
    try:
        data = request.get_json()
        tag_id = data.get('tag_id')
        
        if not tag_id:
            return jsonify({'success': False, 'error': 'tag_id required'}), 400
        
        # Simulate tag detection
        success = rfid_reader.simulate_tag_detection(tag_id)
        
        return jsonify({
            'success': success,
            'tag_id': tag_id,
            'message': f"Simulated tag detection: {tag_id}" if success else "Failed to simulate tag"
        })
        
    except Exception as e:
        logging.error(f"Error simulating tag: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/test/verify_seat', methods=['POST'])
def test_verify_seat():
    """Test: Automatically verify a seat without RFID scan"""
    try:
        data = request.get_json()
        seat_id = data.get('seat_id')
        
        if not seat_id:
            return jsonify({'success': False, 'error': 'seat_id required'}), 400
        
        # Get the tag ID for this seat
        _, tag_map = load_config()
        tag_id = None
        for tid, sid in tag_map.items():
            if sid == seat_id:
                tag_id = tid
                break
        
        if not tag_id:
            return jsonify({'success': False, 'error': f'No tag mapped to seat {seat_id}'}), 400
        
        # Mark as scanning
        seat_map, _ = load_config()
        servo_pos = seat_map.get(seat_id)
        update_visualization_state(seat_id, 'scanning', servo_pos)
        
        # Wait briefly
        time.sleep(0.5)
        
        # Simulate tag detection
        rfid_reader.simulate_tag_detection(tag_id)
        
        # Wait for verification
        time.sleep(0.5)
        
        # Update to verified
        update_visualization_state(seat_id, 'verified')
        
        return jsonify({
            'success': True,
            'seat_id': seat_id,
            'tag_id': tag_id,
            'message': f"Auto-verified seat {seat_id}"
        })
        
    except Exception as e:
        logging.error(f"Error in test verify: {e}")
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
    print("🎓 Hybrid RFID-QR Attendance System - TEST MODE")
    print("   with Digital Twin Visualization")
    print("   (No Hardware Required)")
    print("=" * 60)
    
    # Initialize system
    if not initialize_system():
        print("\n❌ Failed to initialize system")
        sys.exit(1)
    
    print("\n✅ System initialized successfully (TEST MODE)!")
    print("\n⚠️  Running with MOCK hardware - No real servos or RFID reader")
    print("\nStarting Flask server...")
    print("\nAccess via:")
    print("  • Classroom View: http://localhost:5000")
    print("  • API Base: http://localhost:5000/api")
    print("  • Status: http://localhost:5000/api/status")
    print("\nTest Endpoints:")
    print("  • Simulate Tag: POST /api/test/simulate_tag")
    print("  • Auto-Verify Seat: POST /api/test/verify_seat")
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
