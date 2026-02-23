#!/usr/bin/env python3
"""
Servo Controller for Raspberry Pi
Controls X and Y servos using pigpio for precise PWM control
"""

import pigpio
import time
import logging
from typing import Tuple, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)


class ServoController:
    """
    Controls two servos (X and Y axes) using pigpio daemon
    
    Hardware setup:
    - Servo X: GPIO 23
    - Servo Y: GPIO 18
    - External 5-6V power supply with common ground
    """
    
    # GPIO pin assignments
    SERVO_X_PIN = 23
    SERVO_Y_PIN = 18
    
    # Servo pulse width range (microseconds)
    # Standard servo: 500-2500 μs for 0-180°
    MIN_PULSE_WIDTH = 500
    MAX_PULSE_WIDTH = 2500
    
    # Angle limits
    MIN_ANGLE = 0
    MAX_ANGLE = 180
    
    def __init__(self):
        """Initialize pigpio connection and servo pins"""
        self.pi: Optional[pigpio.pi] = None
        self.current_x = 135  # Center position for 270° servos (FT5835M) limited to 180° range
        self.current_y = 135  # Center position for 270° servos (FT5835M) limited to 180° range
        self._connected = False
        
    def connect(self) -> bool:
        """
        Connect to pigpio daemon
        
        Returns:
            bool: True if connected successfully
        """
        try:
            self.pi = pigpio.pi()
            
            if not self.pi.connected:
                logging.error("Failed to connect to pigpio daemon")
                logging.error("Make sure pigpiod is running: sudo pigpiod")
                return False
            
            # Initialize servos to center position
            self._set_servo_angle(self.SERVO_X_PIN, self.current_x)
            self._set_servo_angle(self.SERVO_Y_PIN, self.current_y)
            
            self._connected = True
            logging.info(f"Servo controller connected (X: GPIO{self.SERVO_X_PIN}, Y: GPIO{self.SERVO_Y_PIN})")
            logging.info(f"Initialized to center position: X={self.current_x}°, Y={self.current_y}°")
            
            return True
            
        except Exception as e:
            logging.error(f"Error connecting to pigpio: {e}")
            return False
    
    def disconnect(self) -> None:
        """Disconnect from pigpio and stop servos"""
        if self.pi and self._connected:
            # Turn off servo PWM signals
            self.pi.set_servo_pulsewidth(self.SERVO_X_PIN, 0)
            self.pi.set_servo_pulsewidth(self.SERVO_Y_PIN, 0)
            
            self.pi.stop()
            self._connected = False
            logging.info("Servo controller disconnected")
    
    def _angle_to_pulse_width(self, angle: float) -> int:
        """
        Convert angle (0-180°) to pulse width (500-2500 μs)
        
        Args:
            angle: Servo angle in degrees
            
        Returns:
            int: Pulse width in microseconds
        """
        # Clamp angle to valid range
        angle = max(self.MIN_ANGLE, min(self.MAX_ANGLE, angle))
        
        # Linear mapping: 0° → 500μs, 180° → 2500μs
        pulse_width = self.MIN_PULSE_WIDTH + (
            (angle - self.MIN_ANGLE) * (self.MAX_PULSE_WIDTH - self.MIN_PULSE_WIDTH)
            / (self.MAX_ANGLE - self.MIN_ANGLE)
        )
        
        return int(pulse_width)
    
    def _set_servo_angle(self, pin: int, angle: float) -> None:
        """
        Set servo to specific angle
        
        Args:
            pin: GPIO pin number
            angle: Target angle in degrees (0-180)
        """
        if not self._connected or not self.pi:
            logging.warning("Servo controller not connected")
            return
        
        pulse_width = self._angle_to_pulse_width(angle)
        self.pi.set_servo_pulsewidth(pin, pulse_width)
    
    def move_to(self, x_angle: float, y_angle: float, smooth: bool = True) -> bool:
        """
        Move both servos to target angles
        
        Args:
            x_angle: Target X angle (0-180°)
            y_angle: Target Y angle (0-180°)
            smooth: If True, move gradually; if False, jump instantly
            
        Returns:
            bool: True if movement completed successfully
        """
        if not self._connected:
            logging.error("Cannot move servos: not connected")
            return False
        
        try:
            # Clamp angles
            x_angle = max(self.MIN_ANGLE, min(self.MAX_ANGLE, x_angle))
            y_angle = max(self.MIN_ANGLE, min(self.MAX_ANGLE, y_angle))
            
            logging.info(f"Moving servos: X={x_angle}°, Y={y_angle}° (smooth={smooth})")
            
            if smooth:
                # Smooth movement with small steps
                steps = 20
                x_step = (x_angle - self.current_x) / steps
                y_step = (y_angle - self.current_y) / steps
                
                for i in range(steps + 1):
                    new_x = self.current_x + (x_step * i)
                    new_y = self.current_y + (y_step * i)
                    
                    self._set_servo_angle(self.SERVO_X_PIN, new_x)
                    self._set_servo_angle(self.SERVO_Y_PIN, new_y)
                    
                    time.sleep(0.02)  # 20ms per step
            else:
                # Instant jump
                self._set_servo_angle(self.SERVO_X_PIN, x_angle)
                self._set_servo_angle(self.SERVO_Y_PIN, y_angle)
            
            # Update current position
            self.current_x = x_angle
            self.current_y = y_angle
            
            # Allow servos to settle
            time.sleep(0.1)
            
            logging.info(f"Servos positioned at X={self.current_x}°, Y={self.current_y}°")
            return True
            
        except Exception as e:
            logging.error(f"Error moving servos: {e}")
            return False
    
    def move_to_seat(self, seat_angles: dict) -> bool:
        """
        Move servos to angles defined for a specific seat
        
        Args:
            seat_angles: Dict with 'x' and 'y' angle values
                        Example: {'x': 45, 'y': 60}
        
        Returns:
            bool: True if movement successful
        """
        if 'x' not in seat_angles or 'y' not in seat_angles:
            logging.error(f"Invalid seat angles: {seat_angles}")
            return False
        
        return self.move_to(seat_angles['x'], seat_angles['y'], smooth=True)
    
    def center(self) -> bool:
        """Move both servos to center position (135° for 270° FT5835M servos)"""
        logging.info("Centering servos...")
        return self.move_to(135, 135, smooth=True)
    
    def get_position(self) -> Tuple[float, float]:
        """
        Get current servo positions
        
        Returns:
            Tuple[float, float]: (x_angle, y_angle)
        """
        return (self.current_x, self.current_y)
    
    def test_sweep(self) -> None:
        """Test servos by sweeping through their range"""
        if not self._connected:
            logging.error("Cannot test: not connected")
            return
        
        logging.info("Starting servo test sweep...")
        
        # Center
        self.center()
        time.sleep(1)
        
        # X axis sweep
        logging.info("Testing X axis...")
        self.move_to(75, 135)
        time.sleep(0.5)
        self.move_to(195, 135)
        time.sleep(0.5)
        
        # Y axis sweep
        logging.info("Testing Y axis...")
        self.move_to(135, 75)
        time.sleep(0.5)
        self.move_to(135, 195)
        time.sleep(0.5)
        
        # Return to center
        self.center()
        logging.info("Servo test complete")


def main():
    """Test the servo controller"""
    print("="*60)
    print("Servo Controller Test")
    print("="*60)
    
    controller = ServoController()
    
    if not controller.connect():
        print("\nERROR: Failed to connect to pigpio daemon")
        print("\nTroubleshooting:")
        print("  1. Start pigpio daemon: sudo pigpiod")
        print("  2. Check servo wiring:")
        print("     - Servo X → GPIO 23")
        print("     - Servo Y → GPIO 18")
        print("  3. Verify external 5-6V power supply")
        return
    
    try:
        # Run test sweep
        controller.test_sweep()
        
        # Test specific positions
        print("\nTesting specific seat positions...")
        
        test_seats = [
            ("A1", {"x": 30, "y": 40}),
            ("A2", {"x": 60, "y": 40}),
            ("B1", {"x": 30, "y": 70}),
            ("B2", {"x": 60, "y": 70}),
        ]
        
        for seat_id, angles in test_seats:
            print(f"\nMoving to seat {seat_id}: {angles}")
            controller.move_to_seat(angles)
            time.sleep(1)
        
        # Return to center
        print("\nReturning to center...")
        controller.center()
        
        print("\n✓ Test complete!")
        
    except KeyboardInterrupt:
        print("\n\nTest interrupted")
    finally:
        controller.disconnect()


if __name__ == '__main__':
    main()
