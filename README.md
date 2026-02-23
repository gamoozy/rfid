# RFID Reader Capture System

Production-quality Python script for capturing RFID tag reads from an **R16-12DB UHF RFID Reader** via USB serial connection.

## Features

✅ **Auto-detection** of serial ports (macOS optimized)  
✅ **Dual protocol support**: ASCII lines and binary frames (0xA0, 0xBB)  
✅ **RSSI extraction** with debug mode for protocol analysis  
✅ **TagID → SeatID mapping** via CSV/JSON  
✅ **Smart deduplication** (configurable window)  
✅ **Dual storage**: SQLite database + CSV log  
✅ **Robust error handling** with auto-reconnect  
✅ **Clean console output** with statistics  

---

## Installation

### 1. Install Python Dependencies

```bash
pip install -r requirements.txt
```

Or install manually:

```bash
pip install pyserial
```

### 2. Connect Hardware

1. Connect R16-12DB reader to USB-RS232 adapter
2. Connect adapter to Mac via USB
3. Verify connection: `ls /dev/cu.*`

---

## Quick Start

### Auto-detect and run:

```bash
python reader_capture.py
```

### Specify port manually:

```bash
python reader_capture.py --port /dev/cu.usbserial-14430
```

### Enable debug mode:

```bash
python reader_capture.py --debug
```

### Use custom TagMap:

```bash
python reader_capture.py --tagmap /path/to/tagmap.csv
```

---

## Command-Line Options

| Option | Default | Description |
|--------|---------|-------------|
| `--port` | Auto-detect | Serial port path (e.g., `/dev/cu.usbserial-1234`) |
| `--baud` | 115200 | Baud rate |
| `--timeout` | 0.2 | Serial timeout (seconds) |
| `--tagmap` | None | Path to TagMap CSV/JSON file |
| `--dedupe-ms` | 800 | Deduplication window (milliseconds) |
| `--db` | rfid_scans.db | SQLite database path |
| `--csv` | rfid_scans.csv | CSV log file path |
| `--debug` | False | Enable debug mode (show raw hex dumps) |
| `--log-level` | INFO | Logging level (DEBUG, INFO, WARNING, ERROR) |

---

## TagMap File Format

Create a CSV file mapping TagIDs to SeatIDs:

**tagmap.csv:**
```csv
TagID,SeatID
E28011700000020123456789,A1
E28011700000020123456790,A2
300833B2DDD906C00000270F,C1
```

Or use JSON format:

**tagmap.json:**
```json
{
  "E28011700000020123456789": "A1",
  "E28011700000020123456790": "A2",
  "300833B2DDD906C00000270F": "C1"
}
```

---

## Output Formats

### Console Output

```
[2025-12-15T10:30:45.123456+00:00] SeatID=A1 TagID=E28011700000020123456789 RSSI=-45 Port=/dev/cu.usbserial-14430
[2025-12-15T10:30:47.234567+00:00] SeatID=C1 TagID=300833B2DDD906C00000270F RSSI=-52 Port=/dev/cu.usbserial-14430
```

### SQLite Database Schema

```sql
CREATE TABLE rfid_scans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp_iso TEXT NOT NULL,
    timestamp_epoch REAL NOT NULL,
    tag_id TEXT NOT NULL,
    seat_id TEXT NOT NULL,
    rssi INTEGER,
    raw TEXT,
    source_port TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### CSV Log Format

```csv
timestamp_iso,timestamp_epoch,tag_id,seat_id,rssi,raw,source_port
2025-12-15T10:30:45.123456+00:00,1734261045.123456,E28011700000020123456789,A1,-45,,/dev/cu.usbserial-14430
```

---

## Protocol Support

The script supports multiple RFID reader protocols:

### ASCII Mode
- Plain TagID lines: `300833B2DDD906C00000270F`
- TagID with RSSI: `300833B2DDD906C00000270F,-45`

### Binary Protocols

**Format A (0xA0 header):**
```
[A0] [LEN] [CMD] [STATUS] [EPC_LEN] [EPC...] [RSSI] [CHECKSUM] [A1]
```

**Format B (0xBB header):**
```
[BB] [00] [LEN] [CMD] [DATA...] [CHECKSUM] [7E]
```

### Debug Mode

Enable debug mode to see raw protocol data:

```bash
python reader_capture.py --debug --log-level DEBUG
```

Output:
```
2025-12-15 10:30:45 [DEBUG] Binary frame: A0 1E 89 00 0C E2 80 11 70 00 00 02 01 23 45 67 89 C5 A1
2025-12-15 10:30:45 [DEBUG] Binary frame parsed: TagID=E28011700000020123456789, RSSI=-59
```

---

## Deduplication

The script prevents duplicate reads of the same tag within a configurable time window:

```bash
# 800ms window (default)
python reader_capture.py --dedupe-ms 800

# 2 second window
python reader_capture.py --dedupe-ms 2000
```

---

## Error Handling & Reconnection

The script handles common issues automatically:

- **Port not found**: Auto-detection with fallback
- **Permission denied**: Clear error message with troubleshooting
- **Disconnection**: Auto-reconnect every 2 seconds
- **Buffer overflow**: Automatic buffer clearing
- **Parse errors**: Logged and counted in statistics

---

## Usage Examples

### Basic usage with auto-detection:
```bash
python reader_capture.py
```

### Production setup with custom settings:
```bash
python reader_capture.py \
  --port /dev/cu.usbserial-14430 \
  --tagmap tagmap.csv \
  --dedupe-ms 1000 \
  --db attendance.db \
  --csv attendance.csv
```

### Debug mode to analyze protocol:
```bash
python reader_capture.py --debug --log-level DEBUG
```

### Testing with different baud rates:
```bash
python reader_capture.py --baud 9600
python reader_capture.py --baud 57600
python reader_capture.py --baud 115200
```

---

## Troubleshooting

### No serial ports detected

```bash
# List available ports
ls /dev/cu.* /dev/tty.*

# Check USB devices
system_profiler SPUSBDataType
```

### Permission denied

```bash
# Check port permissions
ls -l /dev/cu.usbserial-*

# On Linux (if needed)
sudo usermod -a -G dialout $USER
```

### Reader not responding

1. Check physical connections
2. Verify reader power (LED indicators)
3. Try different baud rates: `--baud 9600` or `--baud 57600`
4. Enable debug mode to see raw data: `--debug`

### RSSI not showing

RSSI extraction depends on the reader's output mode. If you see `RSSI=N/A`:

1. Enable debug mode: `--debug`
2. Check raw hex output in logs
3. Verify reader is configured for inventory mode with RSSI
4. Some readers require specific commands to enable RSSI output

---

## Statistics

Press `Ctrl+C` to stop and view statistics:

```
============================================================
STATISTICS
============================================================
Total reads:          1547
Accepted scans:       124
Duplicates filtered:  1423
Parse errors:         0
============================================================
```

---

## Database Queries

### Query recent scans:
```sql
SELECT * FROM rfid_scans 
ORDER BY timestamp_epoch DESC 
LIMIT 10;
```

### Count scans per seat:
```sql
SELECT seat_id, COUNT(*) as scan_count 
FROM rfid_scans 
GROUP BY seat_id 
ORDER BY scan_count DESC;
```

### Find tags with weak RSSI:
```sql
SELECT * FROM rfid_scans 
WHERE rssi IS NOT NULL AND rssi < -60 
ORDER BY rssi;
```

---

## Architecture

### Key Components

- **FrameParser**: Handles ASCII and binary protocol parsing
- **TagMap**: Manages TagID → SeatID mapping
- **DedupeManager**: Filters duplicate reads within time window
- **DatabaseManager**: SQLite storage with indexes
- **CSVLogger**: Append-only CSV logging
- **RFIDReader**: Main reader loop with error handling

### Data Flow

```
Serial Port → Buffer → Frame Detection → Parse → Dedupe → Map → Store → Display
```

---

## Requirements

- **OS**: macOS (tested on Apple Silicon), should work on Linux
- **Python**: 3.7+
- **Hardware**: R16-12DB UHF RFID Reader with USB-RS232 adapter
- **Dependencies**: pyserial

---

## File Structure

```
Reader/
├── reader_capture.py      # Main script
├── requirements.txt       # Python dependencies
├── tagmap.csv            # TagID → SeatID mapping (example)
├── rfid_scans.db         # SQLite database (created on first run)
├── rfid_scans.csv        # CSV log (created on first run)
├── README.md             # This file
└── Datasheets/           # Reader documentation
    └── R16-12DB_Product_Datasheet.pdf
```

---

## License

This script is provided as-is for the Hybrid RFID-QR Attendance System prototype.

---

## Support

For issues or questions:
1. Enable debug mode: `--debug --log-level DEBUG`
2. Check raw hex output for protocol analysis
3. Verify hardware connections and reader configuration
4. Consult R16-12DB datasheet in `Datasheets/` folder

---

**Built with ❤️ for reliable RFID attendance tracking**
