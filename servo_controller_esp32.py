#!/usr/bin/env python3
"""
Servo Controller for ESP32
Controls X and Y servos via serial communication with ESP32
Replacement for Raspberry Pi pigpio implementation
"""

import serial
import serial.tools.list_ports
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
    Controls two servos (X and Y axes) via ESP32 serial communication
    
    Hardware setup:
    - ESP32 connected via USB
    - Servo X: GPIO pin (configured in ESP32)
    - Servo Y: GPIO pin (configured in ESP32)
    - External 5-6V power supply with common ground
    
    Communication Protocol:
    - Send: "X<angle>\n" or "Y<angle>\n" or "B<x_angle>,<y_angle>\n"
    - Example: "X90\n" sets X servo to 90 degrees
    - Example: "B90,135\n" sets both servos (X=90, Y=135)
    """
    
    # Angle limits for 270° servos (FT5835M) limited to 180° range
    MIN_ANGLE = 45
    MAX_ANGLE = 225
    CENTER_ANGLE = 135
    
    def __init__(self, port: Optional[str] = None, baudrate: int = 115200):
        """
        Initialize ESP32 serial connection
        
        Args:
            port: Serial port (auto-detect if None)
            baudrate: Serial baudrate (default 115200)
        """
        self.port = port
        self.baudrate = baudrate
        self.serial: Optional[serial.Serial] = None
        self.current_x = self.CENTER_ANGLE
        self.current_y = self.CENTER_ANGLE
        self._connected = False
        
    def _find_esp32_port(self) -> Optional[str]:
        """
        Auto-detect ESP32 serial port
        
        Returns:
            str: Port name if found, None otherwise
        """
        ports = serial.tools.list_ports.comports()
        
        # Common ESP32 USB chip identifiers
        esp32_identifiers = [
            'CP210',  # Silicon Labs CP2102
            'CH340',  # CH340 USB-Serial
            'FTDI',   # FTDI chips
            'USB',    # Generic USB serial
            'uart',   # UART devices
            'SLAB',   # Silicon Labs
        ]
        
        for port in ports:
            port_str = f"{port.device} - {port.description} - {port.manufacturer}"
            logging.info(f"Found port: {port_str}")
            
            # Check if any identifier matches
            for identifier in esp32_identifiers:
                if identifier.lower() in port_str.lower():
                    logging.info(f"ESP32 detected on {port.device}")
                    return port.device
        
        # Fallback: return first available port
        if ports:
            logging.warning(f"No ESP32 identifier found, using first port: {ports[0].device}")
            return ports[0].device
            
        return None
    
    def connect(self) -> bool:
        """
        Connect to ESP32 via serial
        
        Returns:
            bool: True if connected successfully
        """
        try:
            # Auto-detect port if not specified
            if not self.port:
                self.port = self._find_esp32_port()
                
            if not self.port:
                logging.error("No serial port found for ESP32")
                logging.error("Please check ESP32 connection")
                return False
            
            logging.info(f"Connecting to ESP32 on {self.port} @ {self.baudrate} baud...")
            
            # Open serial connection
            self.serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=1,
                write_timeout=1
            )
            
            # Wait for ESP32 to initialize
            time.sleep(2)
            
            # Flush any startup messages
            if self.serial.in_waiting:
                startup_msg = self.serial.read_all().decode('utf-8', errors='ignore')
                logging.info(f"ESP32 startup: {startup_msg.strip()}")
            
            # Initialize servos to center position
            self._send_command(f"B{self.current_x},{self.current_y}")
            
            self._connected = True
            logging.info(f"✓ ESP32 servo controller connected on {self.port}")
            logging.info(f"✓ Initialized to center position: X={self.current_x}°, Y={self.current_y}°")
            
            return True
            
        except Exception as e:
            logging.error(f"Error connecting to ESP32: {e}")
            return False
    
    def disconnect(self) -> None:
        """Disconnect from ESP32 and stop servos"""
        if self.serial and self._connected:
            try:
                # Send center command before closing
                self._send_command(f"B{self.CENTER_ANGLE},{self.CENTER_ANGLE}")
                time.sleep(0.1)
                
                self.serial.close()
                self._connected = False
                logging.info("ESP32 servo controller disconnected")
                
            except Exception as e:
                logging.error(f"Error disconnecting: {e}")
    
    def _send_command(self, command: str) -> bool:
        """
        Send command to ESP32
        
        Args:
            command: Command string (e.g., "X90" or "B90,135")
            
        Returns:
            bool: True if command sent successfully
        """
        if not self._connected or not self.serial:
            logging.warning("ESP32 not connected")
            return False
        
        try:
            # Add newline if not present
            if not command.endswith('\n'):
                command += '\n'
            
            # Send command
            self.serial.write(command.encode('utf-8'))
            self.serial.flush()
            
            # Read response (if any)
            time.sleep(0.05)  # Small delay for ESP32 to respond
            if self.serial.in_waiting:
                response = self.serial.readline().decode('utf-8', errors='ignore').strip()
                if response:
                    logging.debug(f"ESP32 response: {response}")
            
            return True
            
        except Exception as e:
            logging.error(f"Error sending command '{command}': {e}")
            return False
    
    def _clamp_angle(self, angle: float) -> float:
        """Clamp angle to valid range"""
        return max(self.MIN_ANGLE, min(self.MAX_ANGLE, angle))
    
    def move_to(self, x_angle: float, y_angle: float, smooth: bool = True) -> bool:
        """
        Move both servos to target angles
        
        Args:
            x_angle: Target X angle (45-225°)
            y_angle: Target Y angle (45-225°)
            smooth: If True, move gradually; if False, jump instantly
            
        Returns:
            bool: True if movement completed successfully
        """
        if not self._connected:
            logging.error("Cannot move servos: not connected")
            return False
        
        try:
            # Clamp angles
            x_angle = self._clamp_angle(x_angle)
            y_angle = self._clamp_angle(y_angle)
            
            logging.info(f"Moving servos: X={x_angle}°, Y={y_angle}° (smooth={smooth})")
            
            if smooth:
                # Smooth movement with small steps
                steps = 15
                x_step = (x_angle - self.current_x) / steps
                y_step = (y_angle - self.current_y) / steps
                
                for i in range(steps + 1):
                    new_x = int(self.current_x + (x_step * i))
                    new_y = int(self.current_y + (y_step * i))
                    
                    self._send_command(f"B{new_x},{new_y}")
                    time.sleep(0.03)  # 30ms per step
            else:
                # Instant jump
                self._send_command(f"B{int(x_angle)},{int(y_angle)}")
            
            # Update current position
            self.current_x = x_angle
            self.current_y = y_angle
            
            # Allow servos to settle
            time.sleep(0.15)
            
            logging.info(f"✓ Servos positioned at X={self.current_x}°, Y={self.current_y}°")
            return True
            
        except Exception as e:
            logging.error(f"Error moving servos: {e}")
            return False
    
    def move_to_seat(self, seat_angles: dict) -> bool:
        """
        Move servos to angles defined for a specific seat
        
        Args:
            seat_angles: Dict with 'x' and 'y' angle values
                        Example: {'x': 90, 'y': 120}
        
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
        return self.move_to(self.CENTER_ANGLE, self.CENTER_ANGLE, smooth=True)
    
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
        self.move_to(75, self.CENTER_ANGLE)
        time.sleep(0.5)
        self.move_to(195, self.CENTER_ANGLE)
        time.sleep(0.5)
        
        # Y axis sweep
        logging.info("Testing Y axis...")
        self.move_to(self.CENTER_ANGLE, 75)
        time.sleep(0.5)
        self.move_to(self.CENTER_ANGLE, 195)
        time.sleep(0.5)
        
        # Return to center
        self.center()
        logging.info("Servo test complete")


def main():
    """Test the ESP32 servo controller"""
    print("="*60)
    print("ESP32 Servo Controller Test")
    print("="*60)
    
    controller = ServoController()
    
    if not controller.connect():
        print("\n❌ Failed to connect to ESP32")
        print("\nTroubleshooting:")
        print("  1. Check ESP32 is plugged into USB")
        print("  2. Verify ESP32 firmware is running")
        print("  3. Check servo wiring to ESP32")
        print("  4. Verify external 5-6V power supply")
        return
    
    try:
        print("\n✓ Connected! Starting test...")
        
        # Run test sweep
        controller.test_sweep()
        
        # Test specific positions
        print("\nTesting specific seat positions...")
        
        test_seats = [
            ("A1", {"x": 90, "y": 90}),
            ("A2", {"x": 135, "y": 90}),
            ("B1", {"x": 90, "y": 105}),
            ("C3", {"x": 180, "y": 120}),
        ]
        
        for seat_id, angles in test_seats:
            print(f"\nMoving to seat {seat_id}: {angles}")
            controller.move_to_seat(angles)
            time.sleep(1.5)
        
        # Return to center
        print("\nReturning to center...")
        controller.center()
        
        print("\n✅ Test complete!")
        
    except KeyboardInterrupt:
        print("\n\nTest interrupted")
    finally:
        controller.disconnect()


if __name__ == '__main__':
    main()
