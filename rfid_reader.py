#!/usr/bin/env python3
"""
RFID Reader for Raspberry Pi
Reads RFID tags from R16-12DB reader on /dev/ttyUSB0
"""

import serial
import time
import threading
import logging
from typing import Optional, Callable

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)


class RFIDReader:
    """
    Simple RFID reader for R16-12DB on Raspberry Pi
    Reads continuous hex stream at 19200 baud from /dev/ttyUSB0
    """
    
    def __init__(self, port: str = "/dev/ttyUSB0", baud: int = 19200):
        """
        Initialize RFID reader
        
        Args:
            port: Serial port (default /dev/ttyUSB0 on Raspberry Pi)
            baud: Baud rate (default 19200 for R16-12DB passive mode)
        """
        self.port = port
        self.baud = baud
        self.serial_conn: Optional[serial.Serial] = None
        self.running = False
        self.read_thread: Optional[threading.Thread] = None
        
        # Callback for tag detection
        self.on_tag_callback: Optional[Callable[[str], None]] = None
        
        # Tag deduplication
        self.last_tag_id: Optional[str] = None
        self.last_tag_time: float = 0
        self.dedupe_window: float = 1.0  # Ignore same tag within 1 second
        
    def register_callback(self, callback: Callable[[str], None]) -> None:
        """
        Register callback function for tag detection
        
        Args:
            callback: Function that receives tag_id when detected
        """
        self.on_tag_callback = callback
        logging.info("Tag detection callback registered")
    
    def connect(self) -> bool:
        """
        Connect to RFID reader serial port
        
        Returns:
            bool: True if connected successfully
        """
        try:
            self.serial_conn = serial.Serial(
                port=self.port,
                baudrate=self.baud,
                timeout=0.2,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE
            )
            
            # Clear any buffered data
            time.sleep(0.1)
            self.serial_conn.reset_input_buffer()
            
            logging.info(f"Connected to RFID reader: {self.port} at {self.baud} baud")
            return True
            
        except serial.SerialException as e:
            logging.error(f"Failed to connect to {self.port}: {e}")
            logging.error("Make sure:")
            logging.error("  1. Reader is connected via USB")
            logging.error("  2. Port exists: ls /dev/ttyUSB*")
            logging.error("  3. User has permission: sudo usermod -a -G dialout $USER")
            return False
        except Exception as e:
            logging.error(f"Unexpected error: {e}")
            return False
    
    def disconnect(self) -> None:
        """Disconnect from serial port"""
        self.stop()
        
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()
            logging.info("Disconnected from RFID reader")
    
    def _parse_tag_id(self, data: bytes) -> Optional[str]:
        """
        Parse tag ID from continuous hex stream
        
        Args:
            data: Raw bytes from reader
            
        Returns:
            str: Tag ID in hex format, or None if invalid
        """
        if len(data) < 16:
            return None
        
        # Remove null bytes
        cleaned_data = bytes(b for b in data if b != 0x00)
        
        if len(cleaned_data) >= 12:  # Minimum EPC length
            tag_id = cleaned_data.hex().upper()
            return tag_id
        
        return None
    
    def _should_process_tag(self, tag_id: str) -> bool:
        """
        Check if tag should be processed (deduplication)
        
        Args:
            tag_id: Detected tag ID
            
        Returns:
            bool: True if should process, False if duplicate
        """
        current_time = time.time()
        
        # Check if same tag within dedupe window
        if (tag_id == self.last_tag_id and 
            current_time - self.last_tag_time < self.dedupe_window):
            return False
        
        # Update last seen
        self.last_tag_id = tag_id
        self.last_tag_time = current_time
        
        return True
    
    def _read_loop(self) -> None:
        """Main reading loop (runs in separate thread)"""
        buffer = bytearray()
        
        logging.info("RFID reader loop started")
        
        while self.running:
            try:
                if not self.serial_conn or not self.serial_conn.is_open:
                    logging.warning("Serial connection lost, attempting reconnect...")
                    time.sleep(2)
                    if not self.connect():
                        continue
                
                # Read available data
                if self.serial_conn.in_waiting > 0:
                    data = self.serial_conn.read(self.serial_conn.in_waiting)
                    buffer.extend(data)
                    
                    # Process buffer when we have enough data
                    if len(buffer) >= 16:
                        # Take a chunk
                        chunk_size = min(24, len(buffer))
                        chunk = bytes(buffer[:chunk_size])
                        
                        # Try to parse tag ID
                        tag_id = self._parse_tag_id(chunk)
                        
                        if tag_id and self._should_process_tag(tag_id):
                            logging.info(f"Tag detected: {tag_id}")
                            
                            # Call callback if registered
                            if self.on_tag_callback:
                                try:
                                    self.on_tag_callback(tag_id)
                                except Exception as e:
                                    logging.error(f"Error in tag callback: {e}")
                        
                        # Remove processed data from buffer
                        buffer = buffer[chunk_size:]
                    
                    # Prevent buffer overflow
                    if len(buffer) > 512:
                        buffer.clear()
                
                time.sleep(0.05)  # 50ms poll interval
                
            except serial.SerialException as e:
                if "returned no data" not in str(e):  # Ignore transient errors
                    logging.warning(f"Serial error: {e}")
                time.sleep(0.1)
            except Exception as e:
                logging.error(f"Error in read loop: {e}", exc_info=True)
                time.sleep(1)
        
        logging.info("RFID reader loop stopped")
    
    def start(self) -> bool:
        """
        Start reading tags in background thread
        
        Returns:
            bool: True if started successfully
        """
        if self.running:
            logging.warning("Reader already running")
            return True
        
        if not self.serial_conn or not self.serial_conn.is_open:
            if not self.connect():
                return False
        
        self.running = True
        self.read_thread = threading.Thread(target=self._read_loop, daemon=True)
        self.read_thread.start()
        
        logging.info("RFID reader started")
        return True
    
    def stop(self) -> None:
        """Stop reading tags"""
        if not self.running:
            return
        
        self.running = False
        
        if self.read_thread:
            self.read_thread.join(timeout=2.0)
        
        logging.info("RFID reader stopped")


def main():
    """Test the RFID reader"""
    print("="*60)
    print("RFID Reader Test")
    print("="*60)
    
    # Tag detection callback
    def on_tag_detected(tag_id: str):
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] Tag detected: {tag_id}")
    
    # Create reader
    reader = RFIDReader(port="/dev/ttyUSB0", baud=19200)
    reader.register_callback(on_tag_detected)
    
    # Connect
    if not reader.connect():
        print("\nERROR: Failed to connect to RFID reader")
        print("\nTroubleshooting:")
        print("  1. Check connection: ls /dev/ttyUSB*")
        print("  2. Check permissions: sudo usermod -a -G dialout $USER")
        print("  3. Reconnect USB cable")
        print("  4. Try: sudo chmod 666 /dev/ttyUSB0")
        return
    
    # Start reading
    if not reader.start():
        print("\nERROR: Failed to start reader")
        return
    
    print("\n✓ RFID reader running")
    print("\nScan tags now... (Press Ctrl+C to stop)\n")
    
    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n\nStopping...")
    finally:
        reader.disconnect()
        print("✓ Reader stopped")


if __name__ == '__main__':
    main()
