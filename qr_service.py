#!/usr/bin/env python3
"""
QR Code Service
Generates and validates QR codes for attendance sessions
"""

import qrcode
import io
import base64
import json
import time
import hmac
import hashlib
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)


class QRService:
    """
    Handles QR code generation and validation for attendance sessions
    
    QR Payload format:
    {
        "session_id": "unique_session_identifier",
        "classroom_id": "room_identifier",
        "expiry": timestamp (unix epoch),
        "signature": "HMAC signature for validation"
    }
    """
    
    def __init__(self, secret_key: str = "your-secret-key-here"):
        """
        Initialize QR service
        
        Args:
            secret_key: Secret key for HMAC signing (change in production!)
        """
        self.secret_key = secret_key.encode('utf-8')
        self.qr_cache = {}  # Cache QR images to avoid regeneration
        
    def generate_session_qr(
        self,
        session_id: str,
        classroom_id: str,
        validity_minutes: int = 60
    ) -> Dict[str, Any]:
        """
        Generate a QR code for an attendance session
        
        Args:
            session_id: Unique identifier for this session
            classroom_id: Identifier for the classroom
            validity_minutes: How long the QR code is valid (default 60 min)
            
        Returns:
            dict: {
                'qr_image': base64 encoded PNG image,
                'qr_data': payload dict,
                'expiry': expiry timestamp
            }
        """
        # Calculate expiry timestamp
        expiry_time = time.time() + (validity_minutes * 60)
        
        # Create payload
        payload = {
            "session_id": session_id,
            "classroom_id": classroom_id,
            "expiry": int(expiry_time)
        }
        
        # Add HMAC signature for validation
        payload['signature'] = self._sign_payload(payload)
        
        # Convert to JSON
        qr_data_str = json.dumps(payload)
        
        # Generate QR code image
        qr = qrcode.QRCode(
            version=1,  # Auto size
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(qr_data_str)
        qr.make(fit=True)
        
        # Create PIL image
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Convert to base64 PNG
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        img_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        
        # Cache the QR
        self.qr_cache[session_id] = {
            'payload': payload,
            'image': img_base64,
            'generated_at': time.time()
        }
        
        logging.info(f"Generated QR for session {session_id}, valid until {datetime.fromtimestamp(expiry_time).isoformat()}")
        
        return {
            'qr_image': img_base64,
            'qr_data': payload,
            'expiry': expiry_time,
            'qr_data_str': qr_data_str  # For testing/debugging
        }
    
    def _sign_payload(self, payload: dict) -> str:
        """
        Create HMAC signature for payload validation
        
        Args:
            payload: Dict to sign (without 'signature' key)
            
        Returns:
            str: Hex-encoded HMAC signature
        """
        # Create canonical string from payload (without signature)
        data_to_sign = {k: v for k, v in payload.items() if k != 'signature'}
        canonical = json.dumps(data_to_sign, sort_keys=True)
        
        # Generate HMAC-SHA256 signature
        signature = hmac.new(
            self.secret_key,
            canonical.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return signature
    
    def validate_qr(self, qr_data_str: str) -> Dict[str, Any]:
        """
        Validate a scanned QR code
        
        Args:
            qr_data_str: JSON string from scanned QR code
            
        Returns:
            dict: {
                'valid': bool,
                'reason': str (if invalid),
                'session_id': str (if valid),
                'classroom_id': str (if valid),
                'expiry': int (if valid)
            }
        """
        try:
            # Parse JSON
            payload = json.loads(qr_data_str)
            
            # Check required fields
            required_fields = ['session_id', 'classroom_id', 'expiry', 'signature']
            for field in required_fields:
                if field not in payload:
                    return {
                        'valid': False,
                        'reason': f'Missing required field: {field}'
                    }
            
            # Verify signature
            expected_sig = self._sign_payload(payload)
            if not hmac.compare_digest(expected_sig, payload['signature']):
                logging.warning(f"Invalid signature for session {payload.get('session_id')}")
                return {
                    'valid': False,
                    'reason': 'Invalid signature - QR code may be tampered'
                }
            
            # Check expiry
            current_time = time.time()
            if current_time > payload['expiry']:
                logging.warning(f"Expired QR code for session {payload['session_id']}")
                return {
                    'valid': False,
                    'reason': 'QR code has expired'
                }
            
            # Valid!
            logging.info(f"Valid QR code for session {payload['session_id']}")
            return {
                'valid': True,
                'session_id': payload['session_id'],
                'classroom_id': payload['classroom_id'],
                'expiry': payload['expiry'],
                'time_remaining': int(payload['expiry'] - current_time)
            }
            
        except json.JSONDecodeError:
            return {
                'valid': False,
                'reason': 'Invalid JSON format'
            }
        except Exception as e:
            logging.error(f"Error validating QR code: {e}")
            return {
                'valid': False,
                'reason': f'Validation error: {str(e)}'
            }
    
    def get_cached_qr(self, session_id: str) -> Optional[str]:
        """
        Get cached QR image for a session
        
        Args:
            session_id: Session identifier
            
        Returns:
            str: Base64 encoded PNG image, or None if not cached
        """
        cached = self.qr_cache.get(session_id)
        if cached:
            return cached['image']
        return None
    
    def invalidate_session(self, session_id: str) -> bool:
        """
        Invalidate a session QR (remove from cache)
        
        Args:
            session_id: Session to invalidate
            
        Returns:
            bool: True if session was found and invalidated
        """
        if session_id in self.qr_cache:
            del self.qr_cache[session_id]
            logging.info(f"Invalidated session {session_id}")
            return True
        return False
    
    def cleanup_expired(self) -> int:
        """
        Remove expired sessions from cache
        
        Returns:
            int: Number of sessions cleaned up
        """
        current_time = time.time()
        expired = []
        
        for session_id, cached in self.qr_cache.items():
            if cached['payload']['expiry'] < current_time:
                expired.append(session_id)
        
        for session_id in expired:
            del self.qr_cache[session_id]
        
        if expired:
            logging.info(f"Cleaned up {len(expired)} expired sessions")
        
        return len(expired)


def main():
    """Test the QR service"""
    print("="*60)
    print("QR Code Service Test")
    print("="*60)
    
    # Create service
    qr_service = QRService(secret_key="test-secret-key")
    
    # Generate a test QR code
    print("\n1. Generating QR code for test session...")
    result = qr_service.generate_session_qr(
        session_id="TEST-SESSION-001",
        classroom_id="CS-101",
        validity_minutes=60
    )
    
    print(f"   Session ID: {result['qr_data']['session_id']}")
    print(f"   Classroom: {result['qr_data']['classroom_id']}")
    print(f"   Expires: {datetime.fromtimestamp(result['expiry']).strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   QR Image: {len(result['qr_image'])} bytes (base64)")
    
    # Save QR image to file for testing
    qr_image_data = base64.b64decode(result['qr_image'])
    with open('test_qr.png', 'wb') as f:
        f.write(qr_image_data)
    print(f"   Saved to: test_qr.png")
    
    # Test validation with valid QR
    print("\n2. Validating QR code...")
    qr_data_str = result['qr_data_str']
    validation = qr_service.validate_qr(qr_data_str)
    
    if validation['valid']:
        print("   ✓ QR code is VALID")
        print(f"   Session ID: {validation['session_id']}")
        print(f"   Classroom: {validation['classroom_id']}")
        print(f"   Time remaining: {validation['time_remaining']} seconds")
    else:
        print(f"   ✗ QR code is INVALID: {validation['reason']}")
    
    # Test validation with tampered data
    print("\n3. Testing tampered QR code...")
    tampered_data = json.loads(qr_data_str)
    tampered_data['session_id'] = "TAMPERED-SESSION"
    tampered_str = json.dumps(tampered_data)
    
    validation = qr_service.validate_qr(tampered_str)
    if not validation['valid']:
        print(f"   ✓ Tampered QR correctly rejected: {validation['reason']}")
    else:
        print("   ✗ WARNING: Tampered QR was accepted!")
    
    # Test validation with expired QR
    print("\n4. Testing expired QR code...")
    expired_result = qr_service.generate_session_qr(
        session_id="EXPIRED-SESSION",
        classroom_id="CS-101",
        validity_minutes=-1  # Already expired
    )
    
    validation = qr_service.validate_qr(expired_result['qr_data_str'])
    if not validation['valid']:
        print(f"   ✓ Expired QR correctly rejected: {validation['reason']}")
    else:
        print("   ✗ WARNING: Expired QR was accepted!")
    
    print("\n" + "="*60)
    print("✓ QR Service Test Complete!")
    print("="*60)


if __name__ == '__main__':
    main()
