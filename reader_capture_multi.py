#!/usr/bin/env python3
"""
RFID Reader Multi-Tag Capture Script for R16-12DB UHF RFID Reader

Multi-tag version: scans ALL tags in range simultaneously without restricting
to a single tag. Each tag has its own independent cooldown timer.
Supports auto-detection, frame parsing, RSSI extraction,
TagID-to-SeatID mapping, deduplication, and storage to SQLite + CSV.

INSTALLATION:
    pip install pyserial

USAGE:
    # Auto-detect port and start reading
    python reader_capture.py
    
    # Specify port manually
    python reader_capture.py --port /dev/cu.usbserial-1234
    
    # Enable debug mode to see raw hex dumps
    python reader_capture.py --debug
    
    # Use custom TagMap file
    python reader_capture.py --tagmap /path/to/tagmap.csv
    
    # Adjust deduplication window
    python reader_capture.py --dedupe-ms 1000
    
    # Custom baud rate and timeout
    python reader_capture.py --baud 115200 --timeout 0.5

AUTHOR: Generated for Hybrid RFID-QR Attendance System
DATE: December 2025
"""

import argparse
import csv
import json
import logging
import sqlite3
import struct
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from enum import Enum

try:
    import serial
    import serial.tools.list_ports
except ImportError:
    print("ERROR: pyserial not installed. Run: pip install pyserial")
    sys.exit(1)


# ============================================================================
# DATA STRUCTURES
# ============================================================================

class FrameType(Enum):
    """Types of frames we can parse"""
    ASCII_LINE = "ASCII"
    BINARY_A0 = "BINARY_A0"  # Common frame header 0xA0
    BINARY_BB = "BINARY_BB"  # Alternative frame header 0xBB
    UNKNOWN = "UNKNOWN"


@dataclass
class RFIDScan:
    """Represents a single RFID tag scan"""
    timestamp_iso: str
    timestamp_epoch: float
    tag_id: str
    seat_id: str
    rssi: Optional[int]
    raw: Optional[str]
    source_port: str
    x_cm: Optional[float] = None
    y_cm: Optional[float] = None
    motor1_steps: Optional[int] = None
    motor2_steps: Optional[int] = None


# ============================================================================
# STEPPER POSITION READER
# ============================================================================

class StepperPositionReader:
    """Reads the current stepper motor position from shared state file"""
    
    DEFAULT_POSITION_FILE = Path(__file__).parent / "stepper_position.json"
    
    def __init__(self, position_file: Optional[Path] = None):
        self.position_file = position_file or self.DEFAULT_POSITION_FILE
        self._last_position = {'x_cm': None, 'y_cm': None, 'motor1_steps': None, 'motor2_steps': None}
    
    def read_position(self) -> dict:
        """Read current position from stepper_position.json
        
        Returns dict with keys: x_cm, y_cm, motor1_steps, motor2_steps
        Returns last known position if file cannot be read.
        """
        if not self.position_file.exists():
            return self._last_position
        
        try:
            with open(self.position_file, 'r') as f:
                data = json.load(f)
            self._last_position = {
                'x_cm': data.get('x_cm'),
                'y_cm': data.get('y_cm'),
                'motor1_steps': data.get('motor1_steps'),
                'motor2_steps': data.get('motor2_steps'),
            }
            return self._last_position
        except (json.JSONDecodeError, IOError, KeyError):
            # File might be mid-write, use last known
            return self._last_position


# ============================================================================
# TAG MAP MANAGER
# ============================================================================

class TagMap:
    """Manages TagID to SeatID mapping"""
    
    def __init__(self, filepath: Optional[Path] = None):
        self.mapping: Dict[str, str] = {}
        self.filepath = filepath
        if filepath:
            self.load(filepath)
    
    def load(self, filepath: Path) -> None:
        """Load TagMap from CSV or JSON file"""
        if not filepath.exists():
            logging.warning(f"TagMap file not found: {filepath}")
            return
        
        try:
            if filepath.suffix.lower() == '.json':
                with open(filepath, 'r') as f:
                    self.mapping = json.load(f)
            elif filepath.suffix.lower() == '.csv':
                with open(filepath, 'r') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        tag_id = row['TagID'].strip()
                        seat_id = row['SeatID'].strip()
                        self.mapping[tag_id] = seat_id
            else:
                logging.error(f"Unsupported TagMap format: {filepath.suffix}")
                return
            
            logging.info(f"Loaded {len(self.mapping)} entries from TagMap: {filepath}")
        except Exception as e:
            logging.error(f"Failed to load TagMap: {e}")
    
    def get_seat_id(self, tag_id: str) -> str:
        """Get SeatID for a TagID, returns 'UNKNOWN' if not found"""
        return self.mapping.get(tag_id, "UNKNOWN")


# ============================================================================
# DEDUPLICATION MANAGER
# ============================================================================

class DedupeManager:
    """Manages deduplication of repeated tag reads"""
    
    def __init__(self, dedupe_window_ms: int = 800):
        self.dedupe_window_ms = dedupe_window_ms
        self.last_seen: Dict[str, float] = {}
    
    def should_accept(self, tag_id: str, timestamp_epoch: float) -> bool:
        """Check if a tag scan should be accepted (not a duplicate)"""
        if tag_id not in self.last_seen:
            self.last_seen[tag_id] = timestamp_epoch
            return True
        
        time_diff_ms = (timestamp_epoch - self.last_seen[tag_id]) * 1000
        
        if time_diff_ms >= self.dedupe_window_ms:
            self.last_seen[tag_id] = timestamp_epoch
            return True
        
        return False
    
    def clear_old_entries(self, current_time: float, max_age_seconds: float = 3600):
        """Clear entries older than max_age_seconds to prevent memory bloat"""
        cutoff = current_time - max_age_seconds
        self.last_seen = {k: v for k, v in self.last_seen.items() if v >= cutoff}


# ============================================================================
# DATABASE MANAGER
# ============================================================================

class DatabaseManager:
    """Manages SQLite database operations"""
    
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None
        self._initialize_db()
    
    def _initialize_db(self) -> None:
        """Create database and tables if they don't exist"""
        try:
            self.conn = sqlite3.connect(str(self.db_path))
            cursor = self.conn.cursor()
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS rfid_scans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp_iso TEXT NOT NULL,
                    timestamp_epoch REAL NOT NULL,
                    tag_id TEXT NOT NULL,
                    seat_id TEXT NOT NULL,
                    rssi INTEGER,
                    raw TEXT,
                    source_port TEXT NOT NULL,
                    x_cm REAL,
                    y_cm REAL,
                    motor1_steps INTEGER,
                    motor2_steps INTEGER,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Add position columns to existing tables (migration)
            for col, col_type in [('x_cm', 'REAL'), ('y_cm', 'REAL'),
                                   ('motor1_steps', 'INTEGER'), ('motor2_steps', 'INTEGER')]:
                try:
                    cursor.execute(f"ALTER TABLE rfid_scans ADD COLUMN {col} {col_type}")
                except sqlite3.OperationalError:
                    pass  # Column already exists
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp_epoch 
                ON rfid_scans(timestamp_epoch)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_tag_id 
                ON rfid_scans(tag_id)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_seat_id 
                ON rfid_scans(seat_id)
            """)
            
            self.conn.commit()
            logging.info(f"Database initialized: {self.db_path}")
        except Exception as e:
            logging.error(f"Failed to initialize database: {e}")
            raise
    
    def insert_scan(self, scan: RFIDScan) -> None:
        """Insert a scan record into the database"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO rfid_scans 
                (timestamp_iso, timestamp_epoch, tag_id, seat_id, rssi, raw, source_port,
                 x_cm, y_cm, motor1_steps, motor2_steps)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                scan.timestamp_iso,
                scan.timestamp_epoch,
                scan.tag_id,
                scan.seat_id,
                scan.rssi,
                scan.raw,
                scan.source_port,
                scan.x_cm,
                scan.y_cm,
                scan.motor1_steps,
                scan.motor2_steps
            ))
            self.conn.commit()
        except Exception as e:
            logging.error(f"Failed to insert scan into database: {e}")
    
    def close(self) -> None:
        """Close database connection"""
        if self.conn:
            self.conn.close()


# ============================================================================
# CSV LOGGER
# ============================================================================

class CSVLogger:
    """Manages CSV log file operations"""
    
    def __init__(self, csv_path: Path):
        self.csv_path = csv_path
        self._initialize_csv()
    
    def _initialize_csv(self) -> None:
        """Create CSV file with headers if it doesn't exist"""
        if not self.csv_path.exists():
            try:
                with open(self.csv_path, 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        'timestamp_iso', 'timestamp_epoch', 'tag_id', 
                        'seat_id', 'rssi', 'raw', 'source_port',
                        'x_cm', 'y_cm', 'motor1_steps', 'motor2_steps'
                    ])
                logging.info(f"CSV log initialized: {self.csv_path}")
            except Exception as e:
                logging.error(f"Failed to initialize CSV log: {e}")
    
    def append_scan(self, scan: RFIDScan) -> None:
        """Append a scan record to the CSV log"""
        try:
            with open(self.csv_path, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    scan.timestamp_iso,
                    scan.timestamp_epoch,
                    scan.tag_id,
                    scan.seat_id,
                    scan.rssi if scan.rssi is not None else '',
                    scan.raw if scan.raw else '',
                    scan.source_port,
                    scan.x_cm if scan.x_cm is not None else '',
                    scan.y_cm if scan.y_cm is not None else '',
                    scan.motor1_steps if scan.motor1_steps is not None else '',
                    scan.motor2_steps if scan.motor2_steps is not None else ''
                ])
        except Exception as e:
            logging.error(f"Failed to append to CSV log: {e}")


# ============================================================================
# SERIAL PORT DETECTION
# ============================================================================

def detect_serial_ports() -> List[str]:
    """
    Auto-detect potential RFID reader serial ports on macOS
    Prefer /dev/cu.* over /dev/tty.* to avoid blocking issues
    """
    ports = []
    
    # Use pyserial's port listing
    available_ports = serial.tools.list_ports.comports()
    
    for port in available_ports:
        device = port.device
        # Prefer cu.* ports on macOS
        if device.startswith('/dev/cu.'):
            ports.append(device)
    
    # Fallback: also check tty.* if no cu.* found
    if not ports:
        for port in available_ports:
            device = port.device
            if device.startswith('/dev/tty.'):
                ports.append(device)
    
    return ports


def select_port(preferred_port: Optional[str] = None) -> Optional[str]:
    """Select the serial port to use"""
    if preferred_port:
        if Path(preferred_port).exists():
            logging.info(f"Using specified port: {preferred_port}")
            return preferred_port
        else:
            logging.error(f"Specified port does not exist: {preferred_port}")
            return None
    
    # Auto-detect
    ports = detect_serial_ports()
    
    if not ports:
        logging.error("No serial ports detected. Ensure USB adapter is connected.")
        return None
    
    if len(ports) == 1:
        logging.info(f"Auto-detected port: {ports[0]}")
        return ports[0]
    
    # Multiple ports found
    logging.info("Multiple serial ports detected:")
    for i, port in enumerate(ports, 1):
        logging.info(f"  [{i}] {port}")
    
    # Prioritize usbserial-210 (CH9102 RFID reader) over usbserial-0001 (ESP32)
    # This prevents accidentally reading from the servo controller
    for port in ports:
        if 'usbserial-210' in port or 'usbserial-2' in port:
            logging.info(f"Auto-selected RFID reader: {port}")
            return port
    
    # Use any cu.usbserial* or cu.usbmodem* port except usbserial-0001
    for port in ports:
        if ('usbserial' in port or 'usbmodem' in port) and 'usbserial-0001' not in port:
            logging.info(f"Auto-selected: {port}")
            return port
    
    # Fallback to first usbserial port (even if it's 0001)
    for port in ports:
        if 'usbserial' in port or 'usbmodem' in port:
            logging.warning(f"Auto-selected (may be servo controller): {port}")
            return port
    
    # Otherwise use first port
    logging.info(f"Selected first port: {ports[0]}")
    return ports[0]


# ============================================================================
# FRAME PARSING
# ============================================================================

class FrameParser:
    """Parses RFID reader output (ASCII and binary protocols)"""
    
    def __init__(self, debug: bool = False):
        self.debug = debug
        self.buffer = bytearray()
    
    def parse_ascii_line(self, line: str) -> Optional[Tuple[str, Optional[int]]]:
        """
        Parse ASCII line format
        Common formats:
        - Simple TagID: "300833B2DDD906C00000270F"
        - TagID with RSSI: "300833B2DDD906C00000270F,-45"
        - Decimal format: "12345678901234567890"
        
        Returns: (tag_id, rssi) or None
        """
        line = line.strip()
        
        if not line:
            return None
        
        # Check for comma-separated format (TagID,RSSI)
        if ',' in line:
            parts = line.split(',')
            tag_id = parts[0].strip()
            try:
                rssi = int(parts[1].strip())
                return (tag_id, rssi)
            except (ValueError, IndexError):
                return (tag_id, None)
        
        # Plain TagID
        if line:
            # Validate it looks like a tag (hex or decimal)
            if len(line) >= 8:  # Minimum reasonable tag length
                return (line, None)
        
        return None
    
    def parse_continuous_hex_stream(self, data: bytes) -> Optional[Tuple[str, Optional[int]]]:
        """
        Parse continuous hex stream format (common in simpler readers)
        R16-12DB at 19200 baud outputs repeating hex patterns
        Pattern length typically 20-24 bytes
        
        Note: RSSI is NOT available in this passive streaming mode.
        The reader only transmits the tag ID in a continuous cycle.
        
        Returns: (tag_id, rssi) or None
        """
        if len(data) < 16:
            return None
        
        # Convert to hex string (this IS the tag ID)
        # Remove null bytes and common padding
        cleaned_data = bytes(b for b in data if b != 0x00)
        
        if len(cleaned_data) >= 12:  # Minimum EPC length
            tag_id = cleaned_data.hex().upper()
            # RSSI not available in continuous streaming mode
            return (tag_id, None)
        
        return None
    
    def parse_binary_frame(self, data: bytes) -> Optional[Tuple[str, Optional[int]]]:
        """
        Parse binary frame format
        
        Common UHF RFID reader protocols:
        
        Format A (0xA0 header):
        [A0] [LEN] [CMD] [STATUS] [DATA...] [CHECKSUM] [A1]
        
        Format B (0xBB header):
        [BB] [00] [LEN] [CMD] [DATA...] [CHECKSUM] [7E]
        
        EPC data format:
        - EPC is typically 12 bytes (96-bit) or 16 bytes (128-bit)
        - RSSI is usually 1 byte signed integer (-128 to 0 dBm)
        
        Returns: (tag_id, rssi) or None
        """
        if len(data) < 8:
            return None
        
        if self.debug:
            hex_dump = ' '.join(f'{b:02X}' for b in data)
            logging.debug(f"Binary frame: {hex_dump}")
        
        # Format A: 0xA0 header
        if data[0] == 0xA0 and len(data) >= 2:
            return self._parse_a0_frame(data)
        
        # Format B: 0xBB header
        if data[0] == 0xBB and len(data) >= 3:
            return self._parse_bb_frame(data)
        
        return None
    
    def _parse_a0_frame(self, data: bytes) -> Optional[Tuple[str, Optional[int]]]:
        """
        Parse 0xA0 format frame
        
        Typical structure:
        [A0] [LEN] [CMD] [STATUS] [EPC_LEN] [EPC...] [RSSI] [CHECKSUM] [A1]
        
        Example for inventory response (CMD=0x89):
        A0 1E 89 00 0C E2801170000002012345678 9 C5 A1
        └─ header
           └─ length (30 bytes total)
              └─ cmd (inventory response)
                 └─ status (0=OK)
                    └─ EPC len (12 bytes)
                       └─────── EPC data ─────────┘
                                                  └─ RSSI
                                                     └─ checksum
                                                        └─ end marker
        """
        if len(data) < 8:
            return None
        
        # Check end marker
        if data[-1] != 0xA1:
            if self.debug:
                logging.debug("A0 frame: missing end marker 0xA1")
            return None
        
        length = data[1]
        cmd = data[2]
        status = data[3]
        
        # Inventory response command
        if cmd == 0x89 and status == 0x00:
            if len(data) < 9:
                return None
            
            epc_len = data[4]
            
            if len(data) < 5 + epc_len + 2:  # +2 for RSSI and checksum
                return None
            
            epc_bytes = data[5:5+epc_len]
            epc_hex = ''.join(f'{b:02X}' for b in epc_bytes)
            
            # RSSI is typically right after EPC
            rssi_index = 5 + epc_len
            if rssi_index < len(data) - 2:  # Before checksum and end marker
                rssi_raw = data[rssi_index]
                # Convert unsigned to signed
                rssi = rssi_raw if rssi_raw < 128 else rssi_raw - 256
            else:
                rssi = None
            
            return (epc_hex, rssi)
        
        return None
    
    def _parse_bb_frame(self, data: bytes) -> Optional[Tuple[str, Optional[int]]]:
        """
        Parse 0xBB format frame
        
        Typical structure:
        [BB] [00] [LEN] [CMD] [DATA...] [CHECKSUM] [7E]
        
        This is used by some Chinese UHF readers
        """
        if len(data) < 7:
            return None
        
        # Check end marker
        if data[-1] != 0x7E:
            if self.debug:
                logging.debug("BB frame: missing end marker 0x7E")
            return None
        
        length = data[2]
        cmd = data[3]
        
        # Tag inventory response (common CMD values: 0x22, 0x89)
        if cmd in [0x22, 0x89]:
            # Look for EPC pattern in data section
            data_start = 4
            data_end = len(data) - 2  # Exclude checksum and end marker
            
            if data_end - data_start >= 12:  # Minimum EPC length
                # Try to extract EPC (usually 12 or 16 bytes)
                epc_len = min(16, data_end - data_start - 1)
                epc_bytes = data[data_start:data_start+epc_len]
                epc_hex = ''.join(f'{b:02X}' for b in epc_bytes)
                
                # RSSI might be at the end of data section
                rssi_index = data_end - 1
                rssi_raw = data[rssi_index]
                rssi = rssi_raw if rssi_raw < 128 else rssi_raw - 256
                
                return (epc_hex, rssi)
        
        return None
    
    def detect_frame_type(self, data: bytes) -> FrameType:
        """Detect the type of frame"""
        if not data:
            return FrameType.UNKNOWN
        
        if data[0] == 0xA0:
            return FrameType.BINARY_A0
        elif data[0] == 0xBB:
            return FrameType.BINARY_BB
        else:
            # Assume ASCII if printable
            try:
                data.decode('ascii')
                return FrameType.ASCII_LINE
            except UnicodeDecodeError:
                return FrameType.UNKNOWN


# ============================================================================
# RFID READER
# ============================================================================

class RFIDReader:
    """Main RFID reader class"""
    
    def __init__(
        self,
        port: str,
        baud: int = 19200,
        timeout: float = 0.2,
        debug: bool = False,
        tagmap: Optional[TagMap] = None,
        dedupe_manager: Optional[DedupeManager] = None,
        db_manager: Optional[DatabaseManager] = None,
        csv_logger: Optional[CSVLogger] = None,
        use_commands: bool = True,  # Use command mode to get RSSI
        position_reader: Optional['StepperPositionReader'] = None
    ):
        self.port = port
        self.baud = baud
        self.timeout = timeout
        self.debug = debug
        self.serial_conn: Optional[serial.Serial] = None
        self.running = False
        self.use_commands = use_commands
        
        self.tagmap = tagmap or TagMap()
        self.dedupe_manager = dedupe_manager or DedupeManager()
        self.db_manager = db_manager
        self.csv_logger = csv_logger
        self.parser = FrameParser(debug=debug)
        self.position_reader = position_reader
        
        self.stats = {
            'total_reads': 0,
            'accepted_scans': 0,
            'duplicates_filtered': 0,
            'parse_errors': 0,
            'stale_data_filtered': 0,
            'already_scanned_filtered': 0
        }
        
        # Track all scanned seats (for stats only, does NOT block re-scanning)
        self.scanned_seats = set()
        
        # Per-tag tracking for multi-tag support
        # Maps normalized_tag_id -> {read_count, first_seen, last_seen, is_stale}
        self.tag_tracker: Dict[str, dict] = {}
        self.stale_tag_threshold = 1  # After 1 read, apply cooldown
        self.stale_clear_timeout = 5.0  # 5 second cooldown per tag before accepting again
        self.startup_time = time.time()  # Track startup to ignore initial burst
        self.startup_grace_period = 2.0  # Ignore everything for first 2 seconds
        
        # Command-based inventory
        self.last_inventory_command = 0
        self.inventory_interval = 0.5  # Send inventory command every 500ms
    
    def send_inventory_command(self) -> bool:
        """Send inventory command to reader to get tags with RSSI"""
        if not self.serial_conn or not self.serial_conn.is_open:
            return False
        
        try:
            # Single inventory command: A0 04 89 00 8D A1
            cmd = bytes([0xA0, 0x04, 0x89, 0x00, 0x8D, 0xA1])
            self.serial_conn.write(cmd)
            self.last_inventory_command = time.time()
            logging.debug(f"Sent inventory command: {cmd.hex().upper()}")
            return True
        except Exception as e:
            logging.error(f"Error sending inventory command: {e}")
            return False
    
    def connect(self) -> bool:
        """Connect to the serial port"""
        try:
            self.serial_conn = serial.Serial(
                port=self.port,
                baudrate=self.baud,
                timeout=self.timeout,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE
            )
            logging.info(f"Connected to {self.port} at {self.baud} baud")
            
            # Clear any buffered data
            time.sleep(0.1)
            self.serial_conn.reset_input_buffer()
            
            # If using command mode, send initial inventory
            if self.use_commands:
                time.sleep(0.2)
                self.send_inventory_command()
                logging.info("Command mode enabled - will actively query for tags with RSSI")
            else:
                logging.info("Passive mode - listening for continuous stream (no RSSI)")
            
            return True
        except serial.SerialException as e:
            logging.error(f"Failed to connect to {self.port}: {e}")
            return False
        except Exception as e:
            logging.error(f"Unexpected error connecting to {self.port}: {e}")
            return False
    
    def disconnect(self) -> None:
        """Disconnect from the serial port"""
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()
            logging.info(f"Disconnected from {self.port}")
        # Reset per-tag tracking
        self.tag_tracker.clear()
    
    def read_data(self) -> Optional[bytes]:
        """Read data from serial port"""
        if not self.serial_conn or not self.serial_conn.is_open:
            return None
        
        try:
            # Try to read available bytes
            if self.serial_conn.in_waiting > 0:
                data = self.serial_conn.read(self.serial_conn.in_waiting)
                if self.debug and data:
                    logging.debug(f"Received {len(data)} bytes: {data[:50]}")
                return data
        except serial.SerialException as e:
            # Suppress common transient errors that don't affect functionality
            error_msg = str(e).lower()
            if "device reports readiness" not in error_msg and "returned no data" not in error_msg:
                logging.error(f"Serial read error: {e}")
            elif self.debug:
                logging.debug(f"Transient serial error (ignored): {e}")
            return None
        except Exception as e:
            logging.error(f"Unexpected read error: {e}")
            return None
        
        return None
    
    def is_stale_tag(self, tag_id: str, current_time: float) -> bool:
        """Check if tag is in cooldown (per-tag independent tracking for multi-tag support)"""
        if not tag_id:
            return False
        
        # Ignore everything during startup grace period (reader memory burst)
        if current_time - self.startup_time < self.startup_grace_period:
            if self.debug and int(current_time * 10) % 20 == 0:
                logging.debug(f"Startup grace period - ignoring data")
            return True
        
        # Normalize tag ID by finding the most common pattern
        normalized_tag = self._normalize_tag_id(tag_id)
        
        # Clean up old entries periodically (tags not seen for 60s)
        if len(self.tag_tracker) > 100:
            self.tag_tracker = {
                k: v for k, v in self.tag_tracker.items()
                if current_time - v['last_seen'] < 60.0
            }
        
        if normalized_tag in self.tag_tracker:
            info = self.tag_tracker[normalized_tag]
            time_since_last = current_time - info['last_seen']
            
            # If cooldown has expired, reset and accept
            if info['is_stale'] and time_since_last >= self.stale_clear_timeout:
                if self.debug:
                    logging.debug(f"Tag cooldown expired after {time_since_last:.1f}s - accepting again")
                info['read_count'] = 1
                info['is_stale'] = False
                info['last_seen'] = current_time
                info['first_seen'] = current_time
                return False
            
            # If currently in cooldown, reject
            if info['is_stale']:
                if self.debug and info['read_count'] % 500 == 0:
                    logging.debug(f"Tag {normalized_tag[:20]}... in cooldown ({info['read_count']} reads filtered)")
                info['read_count'] += 1
                info['last_seen'] = current_time
                return True
            
            # Not yet stale - increment and check threshold
            info['read_count'] += 1
            info['last_seen'] = current_time
            if info['read_count'] > self.stale_tag_threshold:
                if self.debug:
                    logging.debug(f"Tag {normalized_tag[:20]}... entering cooldown after {info['read_count']} reads")
                info['is_stale'] = True
                return True
            
            return False
        else:
            # Brand new tag - accept it
            if self.debug:
                logging.debug(f"New tag detected: {normalized_tag[:20]}...")
            self.tag_tracker[normalized_tag] = {
                'read_count': 1,
                'first_seen': current_time,
                'last_seen': current_time,
                'is_stale': False
            }
            return False
    
    def _normalize_tag_id(self, tag_id: str) -> str:
        """Normalize tag ID to detect rotating patterns as same tag"""
        # The reader outputs a repeating pattern due to continuous streaming
        # We need to find the actual unique tag pattern
        
        tag_len = len(tag_id)
        if tag_len < 20:
            return tag_id
        
        # Look for repeating patterns in the tag
        # Try different pattern lengths (20, 24, 32, 40 chars)
        for pattern_len in [20, 24, 32, 40]:
            if tag_len >= pattern_len * 2:
                # Check if tag contains a repeating pattern
                pattern = tag_id[:pattern_len]
                remaining = tag_id[pattern_len:]
                if remaining.startswith(pattern[:len(remaining)]):
                    # Found repeating pattern, use first occurrence
                    return pattern
        
        # Try to detect if this is a rotation of a known pattern
        # by looking for the most common subsequence
        if tag_len >= 40:
            # Use a stable 40-char window from the middle
            start = (tag_len - 40) // 2
            return tag_id[start:start+40]
        
        # For shorter tags, use the whole thing
        return tag_id
    
    def process_data(self, data: bytes) -> None:
        """Process received data"""
        if not data:
            return
        
        self.stats['total_reads'] += 1
        
        # Try to detect frame type
        frame_type = self.parser.detect_frame_type(data)
        
        tag_id = None
        rssi = None
        raw_hex = ' '.join(f'{b:02X}' for b in data)
        
        if frame_type == FrameType.ASCII_LINE:
            try:
                line = data.decode('ascii', errors='ignore').strip()
                result = self.parser.parse_ascii_line(line)
                if result:
                    tag_id, rssi = result
                    if self.debug:
                        logging.debug(f"ASCII line parsed: TagID={tag_id}, RSSI={rssi}")
            except Exception as e:
                logging.error(f"Failed to parse ASCII line: {e}")
                self.stats['parse_errors'] += 1
        
        elif frame_type in [FrameType.BINARY_A0, FrameType.BINARY_BB]:
            logging.debug(f"Detected binary frame: {raw_hex}")
            result = self.parser.parse_binary_frame(data)
            if result:
                tag_id, rssi = result
                logging.debug(f"Binary frame parsed: TagID={tag_id}, RSSI={rssi}")
            else:
                logging.debug(f"Failed to parse binary frame: {raw_hex}")
                self.stats['parse_errors'] += 1
        
        else:
            # Try continuous hex stream format (for 19200 baud mode)
            result = self.parser.parse_continuous_hex_stream(data)
            if result:
                tag_id, rssi = result
                if self.debug:
                    logging.debug(f"Continuous hex stream parsed: TagID={tag_id}")
            else:
                if self.debug:
                    logging.debug(f"Unknown format: {raw_hex[:100]}")
                self.stats['parse_errors'] += 1
        
        # If we got a TagID, check if it's stale before processing
        if tag_id:
            current_time = time.time()
            if self.is_stale_tag(tag_id, current_time):
                self.stats['stale_data_filtered'] += 1
                return
            
            self._process_tag(tag_id, rssi, raw_hex)
        else:
            # Show raw data if parsing failed
            if self.debug:
                logging.debug(f"Could not extract TagID")
                logging.debug(f"Raw data: {raw_hex[:100]}")
    
    def _process_tag(self, tag_id: str, rssi: Optional[int], raw_hex: str) -> None:
        """Process a detected tag"""
        # Get timestamp (local time with timezone info)
        now = datetime.now().astimezone()
        timestamp_iso = now.isoformat()
        timestamp_epoch = now.timestamp()
        
        # Check deduplication
        if not self.dedupe_manager.should_accept(tag_id, timestamp_epoch):
            self.stats['duplicates_filtered'] += 1
            if self.debug:
                logging.debug(f"Duplicate filtered: {tag_id}")
            return
        
        # Map to SeatID
        seat_id = self.tagmap.get_seat_id(tag_id)
        
        # Track seat (but do NOT block re-scanning in multi-tag mode)
        self.scanned_seats.add(seat_id)
        
        # Read stepper motor position
        x_cm = None
        y_cm = None
        motor1_steps = None
        motor2_steps = None
        if self.position_reader:
            pos = self.position_reader.read_position()
            x_cm = pos.get('x_cm')
            y_cm = pos.get('y_cm')
            motor1_steps = pos.get('motor1_steps')
            motor2_steps = pos.get('motor2_steps')
        
        # Create scan record
        scan = RFIDScan(
            timestamp_iso=timestamp_iso,
            timestamp_epoch=timestamp_epoch,
            tag_id=tag_id,
            seat_id=seat_id,
            rssi=rssi,
            raw=raw_hex if self.debug else None,
            source_port=self.port,
            x_cm=x_cm,
            y_cm=y_cm,
            motor1_steps=motor1_steps,
            motor2_steps=motor2_steps
        )
        
        # Store to database
        if self.db_manager:
            self.db_manager.insert_scan(scan)
        
        # Append to CSV
        if self.csv_logger:
            self.csv_logger.append_scan(scan)
        
        # Print to console with position
        rssi_str = f"{rssi}" if rssi is not None else "N/A"
        if x_cm is not None and y_cm is not None:
            pos_str = f"Pos=({x_cm:.1f}cm, {y_cm:.1f}cm)"
        else:
            pos_str = "Pos=N/A"
        print(f"[{timestamp_iso}] SeatID={seat_id} TagID={tag_id} {pos_str} RSSI={rssi_str} Port={self.port}")
        
        self.stats['accepted_scans'] += 1
    
    def read_loop(self) -> None:
        """Main reading loop"""
        self.running = True
        buffer = bytearray()
        last_cleanup = time.time()
        last_data_time = time.time()
        
        logging.info("Starting read loop... Press Ctrl+C to stop")
        
        while self.running:
            try:
                # Reconnect if disconnected
                if not self.serial_conn or not self.serial_conn.is_open:
                    logging.warning("Serial connection lost. Attempting to reconnect...")
                    time.sleep(2)
                    if not self.connect():
                        continue
                
                # Send periodic inventory commands if in command mode
                if self.use_commands:
                    current_time = time.time()
                    if current_time - self.last_inventory_command >= self.inventory_interval:
                        self.send_inventory_command()
                
                # Read data
                data = self.read_data()
                
                if data:
                    buffer.extend(data)
                    last_data_time = time.time()
                    
                    # Process buffer
                    # Look for line endings (ASCII mode) or frame delimiters (binary mode)
                    while buffer:
                        processed = False
                        
                        # Check for ASCII line (newline delimited)
                        if b'\n' in buffer or b'\r' in buffer:
                            # Find line ending
                            for delim in [b'\r\n', b'\n', b'\r']:
                                if delim in buffer:
                                    idx = buffer.find(delim)
                                    line = bytes(buffer[:idx])
                                    buffer = buffer[idx + len(delim):]
                                    if line:
                                        self.process_data(line)
                                    processed = True
                                    break
                        
                        # Check for binary frame (0xA0 ... 0xA1 or 0xBB ... 0x7E)
                        elif len(buffer) > 0 and buffer[0] in [0xA0, 0xBB]:
                            # Look for end marker
                            end_marker = 0xA1 if buffer[0] == 0xA0 else 0x7E
                            
                            if end_marker in buffer:
                                idx = buffer.find(end_marker)
                                frame = bytes(buffer[:idx+1])
                                buffer = buffer[idx+1:]
                                self.process_data(frame)
                                processed = True
                            else:
                                # Wait for more data if frame is incomplete
                                if len(buffer) > 512:  # Prevent buffer overflow
                                    logging.warning("Buffer overflow, clearing")
                                    buffer.clear()
                                break
                        
                        # Try to process as continuous hex stream (R16-12DB at 19200 baud)
                        elif len(buffer) >= 16:  # Minimum pattern length
                            # Look for repeating pattern (tag data repeats)
                            # Take a chunk and check if it repeats
                            chunk_size = min(24, len(buffer))
                            chunk = bytes(buffer[:chunk_size])
                            
                            # Try to parse as continuous hex stream
                            result = self.parser.parse_continuous_hex_stream(chunk)
                            if result:
                                self.process_data(chunk)
                                buffer = buffer[chunk_size:]
                                processed = True
                            else:
                                # Try as ASCII data
                                try:
                                    decoded = chunk.decode('ascii', errors='ignore').strip()
                                    
                                    # If we have printable data, try to extract tag
                                    if decoded and all(c.isprintable() for c in decoded[:16]):
                                        # Extract contiguous alphanumeric string (likely a TagID)
                                        tag_match = ''
                                        for char in decoded:
                                            if char.isalnum():
                                                tag_match += char
                                            elif tag_match and len(tag_match) >= 12:
                                                break
                                            elif tag_match:
                                                break
                                        
                                        if len(tag_match) >= 12:  # Valid tag length
                                            self.process_data(tag_match.encode('ascii'))
                                            # Clear buffer up to end of processed data
                                            bytes_to_clear = min(len(tag_match), len(buffer))
                                            buffer = buffer[bytes_to_clear:]
                                            processed = True
                                        else:
                                            # Skip this byte and try next
                                            if self.debug:
                                                logging.debug(f"Skipping byte: {buffer[0]:02X}")
                                            buffer = buffer[1:]
                                            processed = True
                                    else:
                                        # Non-printable, skip first byte
                                        if self.debug:
                                            logging.debug(f"Skipping non-printable byte: {buffer[0]:02X}")
                                        buffer = buffer[1:]
                                        processed = True
                                except Exception as e:
                                    if self.debug:
                                        logging.debug(f"Error processing chunk: {e}")
                                    buffer = buffer[1:]
                                    processed = True
                        
                        else:
                            # Not enough data or unknown, wait or skip
                            if time.time() - last_data_time > 0.5:  # No new data for 500ms
                                if buffer and self.debug:
                                    logging.debug(f"Clearing stale buffer: {buffer[:20].hex()}")
                                buffer.clear()
                            break
                        
                        if not processed:
                            break
                
                # Periodic cleanup
                current_time = time.time()
                if current_time - last_cleanup > 300:  # Every 5 minutes
                    self.dedupe_manager.clear_old_entries(current_time)
                    last_cleanup = current_time
                
                # Small sleep to prevent CPU spinning
                time.sleep(0.01)
            
            except KeyboardInterrupt:
                logging.info("\nShutdown requested by user")
                self.running = False
                break
            
            except Exception as e:
                logging.error(f"Error in read loop: {e}", exc_info=True)
                time.sleep(1)
    
    def print_stats(self) -> None:
        """Print statistics"""
        print("\n" + "="*60)
        print("STATISTICS")
        print("="*60)
        print(f"Total reads:          {self.stats['total_reads']}")
        print(f"Accepted scans:       {self.stats['accepted_scans']}")
        print(f"Duplicates filtered:  {self.stats['duplicates_filtered']}")
        print(f"Stale data filtered:  {self.stats['stale_data_filtered']}")
        print(f"Already scanned:      {self.stats['already_scanned_filtered']}")
        print(f"Parse errors:         {self.stats['parse_errors']}")
        print(f"\nUnique seats scanned: {len(self.scanned_seats)}")
        if self.scanned_seats:
            print(f"Seats: {', '.join(sorted(self.scanned_seats))}")
        print("="*60)


# ============================================================================
# MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="RFID Reader Capture for R16-12DB UHF RFID Reader",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s
  %(prog)s --port /dev/cu.usbserial-1234
  %(prog)s --debug --tagmap tagmap.csv
  %(prog)s --dedupe-ms 1000 --baud 9600
        """
    )
    
    parser.add_argument(
        '--port',
        type=str,
        help='Serial port (auto-detect if not specified)'
    )
    
    parser.add_argument(
        '--baud',
        type=int,
        default=None,
        help='Baud rate (default: auto - 115200 for command mode, 19200 for passive)'
    )
    
    parser.add_argument(
        '--timeout',
        type=float,
        default=0.2,
        help='Serial timeout in seconds (default: 0.2)'
    )
    
    parser.add_argument(
        '--tagmap',
        type=Path,
        help='Path to TagMap CSV/JSON file'
    )
    
    parser.add_argument(
        '--dedupe-ms',
        type=int,
        default=800,
        help='Deduplication window in milliseconds (default: 800)'
    )
    
    parser.add_argument(
        '--db',
        type=Path,
        default=Path('rfid_scans.db'),
        help='SQLite database path (default: rfid_scans.db)'
    )
    
    parser.add_argument(
        '--csv',
        type=Path,
        default=Path('rfid_scans.csv'),
        help='CSV log file path (default: rfid_scans.csv)'
    )
    
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug mode (show raw hex dumps)'
    )
    
    parser.add_argument(
        '--log-level',
        type=str,
        default='INFO',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        help='Logging level (default: INFO)'
    )
    
    parser.add_argument(
        '--no-commands',
        action='store_true',
        help='Disable command mode (passive stream mode, RSSI at byte 3)'
    )
    
    parser.add_argument(
        '--position-file',
        type=str,
        default=None,
        help='Path to stepper_position.json (default: auto-detect in script directory)'
    )
    
    args = parser.parse_args()
    
    # Configure logging
    log_level = getattr(logging, args.log_level)
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Banner
    print("="*60)
    print("RFID Multi-Tag Capture - R16-12DB UHF RFID Reader")
    print("(Scans ALL tags simultaneously)")
    print("="*60)
    
    # Select port
    port = select_port(args.port)
    if not port:
        print("\nERROR: No serial port available")
        print("\nTroubleshooting:")
        print("  1. Ensure USB-RS232 adapter is connected")
        print("  2. Check cable connections")
        print("  3. Try specifying port manually with --port")
        print("  4. List ports: ls /dev/cu.* /dev/tty.*")
        sys.exit(1)
    
    # Initialize components
    tagmap = TagMap(args.tagmap) if args.tagmap else TagMap()
    dedupe_manager = DedupeManager(args.dedupe_ms)
    db_manager = DatabaseManager(args.db)
    csv_logger = CSVLogger(args.csv)
    
    # Initialize stepper position reader
    position_file = Path(args.position_file) if args.position_file else None
    position_reader = StepperPositionReader(position_file)
    if position_reader.position_file.exists():
        pos = position_reader.read_position()
        print(f"Stepper position file: {position_reader.position_file}")
        if pos.get('x_cm') is not None:
            print(f"Current stepper position: ({pos['x_cm']:.1f}cm, {pos['y_cm']:.1f}cm)")
    else:
        print(f"No stepper position file found — position will be N/A")
        print(f"  (Run Stepper_control.py to enable position tracking)")
    
    # Determine baud rate based on mode
    use_commands = not args.no_commands
    if args.baud is None:
        # R16-12DB only works in passive mode at 19200 baud
        baud = 19200
        print(f"Auto-selected baud rate: {baud} (passive stream mode with RSSI at byte 3)")
    else:
        baud = args.baud
    
    # Create reader
    reader = RFIDReader(
        port=port,
        baud=baud,
        timeout=args.timeout,
        debug=args.debug,
        tagmap=tagmap,
        dedupe_manager=dedupe_manager,
        db_manager=db_manager,
        csv_logger=csv_logger,
        use_commands=False,  # R16-12DB doesn't respond to commands
        position_reader=position_reader
    )
    
    # Connect
    if not reader.connect():
        print("\nERROR: Failed to connect to serial port")
        print("\nTroubleshooting:")
        print("  1. Check port permissions: ls -l", port)
        print("  2. Add user to dialout group (Linux)")
        print("  3. Try running with sudo (not recommended)")
        print("  4. Check if another program is using the port")
        sys.exit(1)
    
    # Start reading
    try:
        reader.read_loop()
    finally:
        reader.disconnect()
        reader.print_stats()
        db_manager.close()
        print("\nShutdown complete")


if __name__ == '__main__':
    main()
