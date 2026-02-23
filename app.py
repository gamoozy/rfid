#!/usr/bin/env python3
"""
Flask Web API for Hybrid RFID-QR Attendance System
Runs on Raspberry Pi, exposes REST API for mobile dashboard
"""

from flask import Flask, request, jsonify, render_template_string, send_file
from flask_cors import CORS
import json
import time
import logging
from pathlib import Path
from typing import Dict, Any

# Import our modules
from servo_controller import ServoController
from qr_service import QRService
from attendance_controller import AttendanceController, VerificationRequest, VerificationStatus
from rfid_reader import RFIDReader

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)

# Initialize Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for mobile access

# Configuration file paths
CONFIG_DIR = Path(__file__).parent
SEAT_MAP_FILE = CONFIG_DIR / "seat_map.json"
TAG_MAP_FILE = CONFIG_DIR / "tag_map.json"

# Global instances
servo_controller: ServoController = None
qr_service: QRService = None
attendance_controller: AttendanceController = None
rfid_reader: RFIDReader = None

# Active sessions
active_sessions: Dict[str, dict] = {}


def load_config():
    """Load seat map and tag map from JSON files"""
    seat_map = {}
    tag_map = {}
    
    if SEAT_MAP_FILE.exists():
        with open(SEAT_MAP_FILE, 'r') as f:
            seat_map = json.load(f)
        logging.info(f"Loaded seat map: {len(seat_map)} seats")
    else:
        logging.warning(f"Seat map not found: {SEAT_MAP_FILE}")
    
    if TAG_MAP_FILE.exists():
        with open(TAG_MAP_FILE, 'r') as f:
            tag_map = json.load(f)
        logging.info(f"Loaded tag map: {len(tag_map)} tags")
    else:
        logging.warning(f"Tag map not found: {TAG_MAP_FILE}")
    
    return seat_map, tag_map


def initialize_system():
    """Initialize all system components"""
    global servo_controller, qr_service, attendance_controller, rfid_reader
    
    logging.info("Initializing system...")
    
    # Load configuration
    seat_map, tag_map = load_config()
    
    # Initialize servo controller
    servo_controller = ServoController()
    if not servo_controller.connect():
        logging.error("Failed to initialize servo controller")
        logging.error("Run: sudo pigpiod")
        return False
    
    # Initialize QR service
    qr_service = QRService(secret_key="change-this-in-production")
    
    # Initialize RFID reader
    rfid_reader = RFIDReader(port="/dev/ttyUSB0", baud=19200)
    
    # Initialize attendance controller
    attendance_controller = AttendanceController(
        servo_controller=servo_controller,
        seat_map=seat_map,
        tag_map=tag_map,
        verification_timeout=5.0
    )
    
    # Connect RFID reader callback to attendance controller
    rfid_reader.register_callback(attendance_controller.on_tag_detected)
    
    # Start RFID reader
    if not rfid_reader.start():
        logging.error("Failed to start RFID reader")
        return False
    
    logging.info("✓ System initialized successfully")
    return True


# ============================================================================
# REST API ENDPOINTS
# ============================================================================

@app.route('/')
def index():
    """Homepage with API documentation"""
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>RFID-QR Attendance System</title>
        <style>
            body { font-family: Arial; max-width: 800px; margin: 50px auto; padding: 20px; }
            h1 { color: #2c3e50; }
            h2 { color: #34495e; margin-top: 30px; }
            .endpoint { background: #ecf0f1; padding: 15px; margin: 10px 0; border-radius: 5px; }
            .method { color: #27ae60; font-weight: bold; }
            code { background: #34495e; color: white; padding: 2px 6px; border-radius: 3px; }
            .status { padding: 10px; border-radius: 5px; margin: 10px 0; }
            .success { background: #d4edda; color: #155724; }
            .warning { background: #fff3cd; color: #856404; }
        </style>
    </head>
    <body>
        <h1>🎓 Hybrid RFID-QR Attendance System</h1>
        <p>REST API for Raspberry Pi attendance verification</p>
        
        <div class="status success">
            <strong>✓ System Online</strong><br>
            Servos: Connected | RFID Reader: Running
        </div>
        
        <h2>API Endpoints</h2>
        
        <div class="endpoint">
            <span class="method">POST</span> <code>/api/session/create</code>
            <p>Create a new attendance session and generate QR code</p>
            <strong>Body:</strong>
            <pre>{ "session_id": "CS101-2025-01-15", "classroom_id": "ROOM-A" }</pre>
            <strong>Returns:</strong> QR code image (base64) and session details
        </div>
        
        <div class="endpoint">
            <span class="method">POST</span> <code>/api/attendance/claim</code>
            <p>Student claims a seat (scanned QR + selected seat)</p>
            <strong>Body:</strong>
            <pre>{ "qr_data": "...", "student_id": "STU123", "seat_id": "A1" }</pre>
            <strong>Returns:</strong> Verification result
        </div>
        
        <div class="endpoint">
            <span class="method">GET</span> <code>/api/session/&lt;session_id&gt;</code>
            <p>Get session statistics and verified students</p>
        </div>
        
        <div class="endpoint">
            <span class="method">GET</span> <code>/api/status</code>
            <p>Get system status (servos, RFID, lock state)</p>
        </div>
        
        <div class="endpoint">
            <span class="method">POST</span> <code>/api/servo/test</code>
            <p>Test servo movement (admin only)</p>
        </div>
        
        <h2>Setup Instructions</h2>
        <ol>
            <li>Ensure <code>pigpiod</code> is running: <code>sudo pigpiod</code></li>
            <li>Configure seat_map.json and tag_map.json</li>
            <li>Connect RFID reader to /dev/ttyUSB0</li>
            <li>Expose via ngrok: <code>ngrok http 5000</code></li>
            <li>Students scan QR from mobile browser</li>
        </ol>
        
        <h2>Quick Test</h2>
        <p>
            <a href="/api/status">Check System Status</a> |
            <a href="/api/servo/center">Center Servos</a>
        </p>
    </body>
    </html>
    """
    return render_template_string(html)


@app.route('/api/status', methods=['GET'])
def get_status():
    """Get system status"""
    return jsonify({
        'status': 'online',
        'timestamp': time.time(),
        'components': {
            'servos': {
                'connected': servo_controller._connected if servo_controller else False,
                'position': servo_controller.get_position() if servo_controller else None
            },
            'rfid': {
                'running': rfid_reader.running if rfid_reader else False,
                'port': rfid_reader.port if rfid_reader else None
            },
            'attendance': {
                'locked': attendance_controller.is_locked() if attendance_controller else False,
                'verification_status': attendance_controller.get_verification_status() if attendance_controller else {}
            }
        }
    })


@app.route('/api/session/create', methods=['POST'])
def create_session():
    """Create a new attendance session and generate QR code"""
    data = request.get_json()
    
    session_id = data.get('session_id')
    classroom_id = data.get('classroom_id', 'DEFAULT')
    validity_minutes = data.get('validity_minutes', 60)
    
    if not session_id:
        return jsonify({'error': 'session_id required'}), 400
    
    # Generate QR code
    qr_result = qr_service.generate_session_qr(
        session_id=session_id,
        classroom_id=classroom_id,
        validity_minutes=validity_minutes
    )
    
    # Store session
    active_sessions[session_id] = {
        'session_id': session_id,
        'classroom_id': classroom_id,
        'created_at': time.time(),
        'expiry': qr_result['expiry'],
        'verified_students': []
    }
    
    return jsonify({
        'success': True,
        'session_id': session_id,
        'qr_image': qr_result['qr_image'],  # base64 PNG
        'qr_data': qr_result['qr_data_str'],  # For testing
        'expiry': qr_result['expiry'],
        'message': 'Session created successfully'
    })


@app.route('/api/attendance/claim', methods=['POST'])
def claim_seat():
    """
    Student claims a seat after scanning QR code
    
    This endpoint:
    1. Validates QR code
    2. Locks RFID scanning
    3. Moves servos to seat
    4. Waits for RFID tag
    5. Verifies attendance
    """
    data = request.get_json()
    
    qr_data_str = data.get('qr_data')
    student_id = data.get('student_id')
    seat_id = data.get('seat_id')
    
    # Validate inputs
    if not all([qr_data_str, student_id, seat_id]):
        return jsonify({
            'success': False,
            'error': 'Missing required fields: qr_data, student_id, seat_id'
        }), 400
    
    # Validate QR code
    qr_validation = qr_service.validate_qr(qr_data_str)
    
    if not qr_validation['valid']:
        return jsonify({
            'success': False,
            'error': qr_validation['reason']
        }), 400
    
    session_id = qr_validation['session_id']
    
    # Create verification request
    verification_request = VerificationRequest(
        student_id=student_id,
        seat_id=seat_id,
        session_id=session_id,
        timestamp=time.time()
    )
    
    # Perform verification (this blocks for up to 5 seconds)
    logging.info(f"Processing attendance claim: student={student_id}, seat={seat_id}")
    result = attendance_controller.verify_attendance(verification_request)
    
    # Update session stats if successful
    if result.status == VerificationStatus.SUCCESS:
        if session_id in active_sessions:
            active_sessions[session_id]['verified_students'].append({
                'student_id': student_id,
                'seat_id': seat_id,
                'timestamp': result.timestamp
            })
    
    # Return result
    return jsonify({
        'success': result.status == VerificationStatus.SUCCESS,
        'status': result.status.value,
        'message': result.message,
        'student_id': result.student_id,
        'seat_id': result.seat_id,
        'tag_id': result.tag_id_detected,
        'timestamp': result.timestamp
    })


@app.route('/api/session/<session_id>', methods=['GET'])
def get_session(session_id):
    """Get session details and statistics"""
    if session_id not in active_sessions:
        return jsonify({'error': 'Session not found'}), 404
    
    session = active_sessions[session_id]
    stats = attendance_controller.get_session_stats(session_id)
    
    return jsonify({
        'session_id': session_id,
        'classroom_id': session['classroom_id'],
        'created_at': session['created_at'],
        'expiry': session['expiry'],
        'total_verified': stats['total_verified'],
        'verified_students': session['verified_students']
    })


@app.route('/api/servo/test', methods=['POST'])
def test_servos():
    """Test servo movement (admin endpoint)"""
    if not servo_controller:
        return jsonify({'error': 'Servo controller not initialized'}), 500
    
    servo_controller.test_sweep()
    
    return jsonify({
        'success': True,
        'message': 'Servo test completed'
    })


@app.route('/api/servo/center', methods=['GET', 'POST'])
def center_servos():
    """Center servos (utility endpoint)"""
    if not servo_controller:
        return jsonify({'error': 'Servo controller not initialized'}), 500
    
    servo_controller.center()
    
    return jsonify({
        'success': True,
        'message': 'Servos centered',
        'position': servo_controller.get_position()
    })


@app.route('/api/config', methods=['GET'])
def get_config():
    """Get seat map and tag map configuration"""
    seat_map, tag_map = load_config()
    
    return jsonify({
        'seat_map': seat_map,
        'tag_map': tag_map,
        'total_seats': len(seat_map),
        'total_tags': len(tag_map)
    })


def shutdown_system():
    """Clean shutdown of all components"""
    logging.info("Shutting down system...")
    
    if rfid_reader:
        rfid_reader.disconnect()
    
    if servo_controller:
        servo_controller.center()  # Return to center
        time.sleep(0.5)
        servo_controller.disconnect()
    
    logging.info("✓ System shutdown complete")


if __name__ == '__main__':
    print("="*60)
    print("🎓 Hybrid RFID-QR Attendance System")
    print("="*60)
    print()
    
    # Initialize system
    if not initialize_system():
        print("\n❌ System initialization failed!")
        print("\nTroubleshooting:")
        print("  1. Run: sudo pigpiod")
        print("  2. Check RFID reader: ls /dev/ttyUSB*")
        print("  3. Check permissions: sudo usermod -a -G dialout $USER")
        print("  4. Verify seat_map.json and tag_map.json exist")
        exit(1)
    
    print("\n✅ System initialized successfully!")
    print()
    print("Starting Flask server...")
    print("Access via:")
    print("  • Local: http://localhost:5000")
    print("  • Network: http://<raspberry-pi-ip>:5000")
    print()
    print("For mobile access, run:")
    print("  ngrok http 5000")
    print()
    print("Press Ctrl+C to stop")
    print("="*60)
    print()
    
    try:
        # Run Flask app
        app.run(
            host='0.0.0.0',  # Accept connections from any IP
            port=5000,
            debug=False,  # Set to True for development
            threaded=True
        )
    except KeyboardInterrupt:
        print("\n\nShutting down...")
    finally:
        shutdown_system()
