#!/usr/bin/env python3
"""
Attendance Controller
Core logic for RFID-QR hybrid attendance verification with seat locking
"""

import threading
import time
import logging
from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)


class VerificationStatus(Enum):
    """Status codes for attendance verification"""
    SUCCESS = "success"
    TIMEOUT = "timeout"
    WRONG_TAG = "wrong_tag"
    NO_TAG = "no_tag"
    SEAT_NOT_FOUND = "seat_not_found"
    ALREADY_VERIFIED = "already_verified"
    SYSTEM_ERROR = "system_error"


@dataclass
class VerificationRequest:
    """Represents a seat claim verification request"""
    student_id: str
    seat_id: str
    session_id: str
    timestamp: float
    expected_tag_id: Optional[str] = None


@dataclass
class VerificationResult:
    """Result of a verification attempt"""
    status: VerificationStatus
    student_id: str
    seat_id: str
    tag_id_detected: Optional[str]
    timestamp: float
    message: str


class AttendanceController:
    """
    Controls the attendance verification process with RFID scan locking
    
    Flow:
    1. Student scans QR code and claims a seat
    2. Controller locks RFID scanning
    3. Moves servos to seat position
    4. Waits for RFID tag detection (5 second window)
    5. Verifies tag matches the seat
    6. Unlocks RFID scanning
    7. Returns result
    """
    
    def __init__(
        self,
        servo_controller,
        seat_map: Dict[str, Dict[str, float]],
        tag_map: Dict[str, str],
        verification_timeout: float = 5.0
    ):
        """
        Initialize attendance controller
        
        Args:
            servo_controller: ServoController instance
            seat_map: Dict mapping SeatID → {'x': angle, 'y': angle}
            tag_map: Dict mapping SeatID → TagID
            verification_timeout: Seconds to wait for RFID tag (default 5.0)
        """
        self.servo_controller = servo_controller
        self.seat_map = seat_map
        self.tag_map = tag_map
        self.verification_timeout = verification_timeout
        
        # Locking mechanism
        self.scan_lock = threading.Lock()
        self.is_verifying = False
        
        # Current verification state
        self.current_request: Optional[VerificationRequest] = None
        self.detected_tag_id: Optional[str] = None
        self.verification_start_time: float = 0
        
        # Verified students (prevent duplicate verification in same session)
        self.verified_students: Dict[str, set] = {}  # session_id → set of student_ids
        
        # Callback for RFID tag detection
        self.tag_detected_callback: Optional[Callable] = None
        
        logging.info("Attendance controller initialized")
    
    def register_tag_callback(self, callback: Callable[[str], None]) -> None:
        """
        Register callback for RFID tag detection
        
        Args:
            callback: Function that receives tag_id when detected
        """
        self.tag_detected_callback = callback
        logging.info("RFID tag detection callback registered")
    
    def on_tag_detected(self, tag_id: str) -> bool:
        """
        Called when RFID reader detects a tag
        
        Args:
            tag_id: Detected RFID tag ID
            
        Returns:
            bool: True if tag was accepted, False if rejected/ignored
        """
        # Only process if we're currently verifying
        if not self.is_verifying:
            logging.debug(f"Tag detected but not verifying: {tag_id}")
            return False
        
        # Check if we're still within verification window
        if time.time() - self.verification_start_time > self.verification_timeout:
            logging.debug(f"Tag detected but verification window expired: {tag_id}")
            return False
        
        # Store detected tag
        self.detected_tag_id = tag_id
        logging.info(f"Tag detected during verification: {tag_id}")
        
        # Notify callback if registered
        if self.tag_detected_callback:
            try:
                self.tag_detected_callback(tag_id)
            except Exception as e:
                logging.error(f"Error in tag callback: {e}")
        
        return True
    
    def verify_attendance(self, request: VerificationRequest) -> VerificationResult:
        """
        Verify student attendance by moving servos and checking RFID tag
        
        This method:
        1. Locks RFID scanning
        2. Checks seat exists
        3. Moves servos to seat position
        4. Waits for RFID tag detection
        5. Verifies tag matches seat
        6. Unlocks RFID scanning
        
        Args:
            request: VerificationRequest with student/seat info
            
        Returns:
            VerificationResult with status and details
        """
        start_time = time.time()
        
        logging.info(f"Starting verification for student={request.student_id}, seat={request.seat_id}")
        
        # Acquire lock (blocks if another verification is in progress)
        with self.scan_lock:
            self.is_verifying = True
            self.current_request = request
            self.detected_tag_id = None
            self.verification_start_time = start_time
            
            try:
                # Check if student already verified in this session
                if request.session_id in self.verified_students:
                    if request.student_id in self.verified_students[request.session_id]:
                        logging.warning(f"Student {request.student_id} already verified in session {request.session_id}")
                        return VerificationResult(
                            status=VerificationStatus.ALREADY_VERIFIED,
                            student_id=request.student_id,
                            seat_id=request.seat_id,
                            tag_id_detected=None,
                            timestamp=time.time(),
                            message=f"Student already verified in this session"
                        )
                
                # Check if seat exists in seat map
                if request.seat_id not in self.seat_map:
                    logging.error(f"Seat {request.seat_id} not found in seat map")
                    return VerificationResult(
                        status=VerificationStatus.SEAT_NOT_FOUND,
                        student_id=request.student_id,
                        seat_id=request.seat_id,
                        tag_id_detected=None,
                        timestamp=time.time(),
                        message=f"Seat {request.seat_id} not configured"
                    )
                
                # Get expected tag ID for this seat
                expected_tag_id = self.tag_map.get(request.seat_id)
                if not expected_tag_id:
                    logging.warning(f"No tag mapped for seat {request.seat_id}")
                
                # Move servos to seat position
                seat_angles = self.seat_map[request.seat_id]
                logging.info(f"Moving servos to seat {request.seat_id}: {seat_angles}")
                
                if not self.servo_controller.move_to_seat(seat_angles):
                    logging.error("Failed to move servos")
                    return VerificationResult(
                        status=VerificationStatus.SYSTEM_ERROR,
                        student_id=request.student_id,
                        seat_id=request.seat_id,
                        tag_id_detected=None,
                        timestamp=time.time(),
                        message="Servo movement failed"
                    )
                
                # Wait for RFID tag detection (poll every 100ms)
                logging.info(f"Waiting {self.verification_timeout}s for RFID tag detection...")
                
                while (time.time() - start_time) < self.verification_timeout:
                    if self.detected_tag_id:
                        break
                    time.sleep(0.1)
                
                # Check result
                if not self.detected_tag_id:
                    logging.warning(f"No tag detected within {self.verification_timeout}s")
                    return VerificationResult(
                        status=VerificationStatus.TIMEOUT,
                        student_id=request.student_id,
                        seat_id=request.seat_id,
                        tag_id_detected=None,
                        timestamp=time.time(),
                        message=f"No RFID tag detected within {self.verification_timeout}s"
                    )
                
                # Verify tag matches seat
                if expected_tag_id and self.detected_tag_id != expected_tag_id:
                    logging.warning(f"Wrong tag detected: expected={expected_tag_id}, got={self.detected_tag_id}")
                    return VerificationResult(
                        status=VerificationStatus.WRONG_TAG,
                        student_id=request.student_id,
                        seat_id=request.seat_id,
                        tag_id_detected=self.detected_tag_id,
                        timestamp=time.time(),
                        message=f"Wrong RFID tag (expected {expected_tag_id}, got {self.detected_tag_id})"
                    )
                
                # Success!
                logging.info(f"✓ Verification successful: student={request.student_id}, seat={request.seat_id}, tag={self.detected_tag_id}")
                
                # Mark student as verified in this session
                if request.session_id not in self.verified_students:
                    self.verified_students[request.session_id] = set()
                self.verified_students[request.session_id].add(request.student_id)
                
                return VerificationResult(
                    status=VerificationStatus.SUCCESS,
                    student_id=request.student_id,
                    seat_id=request.seat_id,
                    tag_id_detected=self.detected_tag_id,
                    timestamp=time.time(),
                    message=f"Attendance verified successfully"
                )
                
            except Exception as e:
                logging.error(f"Error during verification: {e}", exc_info=True)
                return VerificationResult(
                    status=VerificationStatus.SYSTEM_ERROR,
                    student_id=request.student_id,
                    seat_id=request.seat_id,
                    tag_id_detected=self.detected_tag_id,
                    timestamp=time.time(),
                    message=f"System error: {str(e)}"
                )
            
            finally:
                # Always unlock
                self.is_verifying = False
                self.current_request = None
    
    def is_locked(self) -> bool:
        """Check if RFID scanning is currently locked"""
        return self.is_verifying
    
    def get_verification_status(self) -> Dict[str, Any]:
        """
        Get current verification status
        
        Returns:
            dict: Status information
        """
        if not self.is_verifying:
            return {
                'locked': False,
                'message': 'Ready for verification'
            }
        
        elapsed = time.time() - self.verification_start_time
        remaining = max(0, self.verification_timeout - elapsed)
        
        return {
            'locked': True,
            'student_id': self.current_request.student_id if self.current_request else None,
            'seat_id': self.current_request.seat_id if self.current_request else None,
            'elapsed': round(elapsed, 2),
            'remaining': round(remaining, 2),
            'tag_detected': self.detected_tag_id is not None
        }
    
    def reset_session(self, session_id: str) -> None:
        """
        Reset verified students for a session
        
        Args:
            session_id: Session to reset
        """
        if session_id in self.verified_students:
            count = len(self.verified_students[session_id])
            del self.verified_students[session_id]
            logging.info(f"Reset session {session_id} ({count} students cleared)")
    
    def get_session_stats(self, session_id: str) -> Dict[str, Any]:
        """
        Get statistics for a session
        
        Args:
            session_id: Session to query
            
        Returns:
            dict: Statistics
        """
        verified = self.verified_students.get(session_id, set())
        
        return {
            'session_id': session_id,
            'total_verified': len(verified),
            'verified_students': list(verified)
        }


def main():
    """Test the attendance controller (requires servo controller)"""
    print("="*60)
    print("Attendance Controller Test")
    print("="*60)
    
    # Mock servo controller for testing
    class MockServoController:
        def move_to_seat(self, angles):
            print(f"  [MOCK] Moving servos to {angles}")
            time.sleep(0.5)  # Simulate movement
            return True
    
    # Test configuration
    seat_map = {
        "A1": {"x": 30, "y": 40},
        "A2": {"x": 60, "y": 40},
        "B1": {"x": 30, "y": 70},
        "B2": {"x": 60, "y": 70},
    }
    
    tag_map = {
        "A1": "TAG-001",
        "A2": "TAG-002",
        "B1": "TAG-003",
        "B2": "TAG-004",
    }
    
    # Create controller
    mock_servo = MockServoController()
    controller = AttendanceController(
        servo_controller=mock_servo,
        seat_map=seat_map,
        tag_map=tag_map,
        verification_timeout=3.0
    )
    
    print("\n1. Testing successful verification...")
    
    # Simulate tag detection after 1 second
    def simulate_tag_detection():
        time.sleep(1)
        print("  [SIMULATE] Tag detected: TAG-001")
        controller.on_tag_detected("TAG-001")
    
    thread = threading.Thread(target=simulate_tag_detection, daemon=True)
    thread.start()
    
    request = VerificationRequest(
        student_id="STUDENT-123",
        seat_id="A1",
        session_id="SESSION-001",
        timestamp=time.time()
    )
    
    result = controller.verify_attendance(request)
    
    print(f"  Status: {result.status.value}")
    print(f"  Message: {result.message}")
    print(f"  Tag detected: {result.tag_id_detected}")
    
    print("\n2. Testing timeout (no tag detected)...")
    
    request2 = VerificationRequest(
        student_id="STUDENT-456",
        seat_id="A2",
        session_id="SESSION-001",
        timestamp=time.time()
    )
    
    result2 = controller.verify_attendance(request2)
    
    print(f"  Status: {result2.status.value}")
    print(f"  Message: {result2.message}")
    
    print("\n3. Testing duplicate verification...")
    
    result3 = controller.verify_attendance(request)  # Same student again
    
    print(f"  Status: {result3.status.value}")
    print(f"  Message: {result3.message}")
    
    print("\n4. Session statistics...")
    stats = controller.get_session_stats("SESSION-001")
    print(f"  Total verified: {stats['total_verified']}")
    print(f"  Students: {stats['verified_students']}")
    
    print("\n" + "="*60)
    print("✓ Attendance Controller Test Complete!")
    print("="*60)


if __name__ == '__main__':
    main()
