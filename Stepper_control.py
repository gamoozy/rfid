#!/usr/bin/env python3
"""
Dual Stepper Motor Controller — with Position Tracking
=========================================================
Two motors controlled independently via arrow keys.
Tracks real-world X/Y position in centimeters and writes to
stepper_position.json so the RFID reader knows where tags are detected.

Motor 1 (GPIO 18/19) = X-axis:
  Right Arrow  = Move CW  (+X)
  Left Arrow   = Move CCW (-X)

Motor 2 (GPIO 16/17) = Y-axis:
  Up Arrow     = Move CW  (+Y)
  Down Arrow   = Move CCW (-Y)

Other:
  S / Space    = Stop all motors
  X            = Emergency stop
  H            = Home (reset position to 0,0)
  P            = Print current position
  Q / Ctrl+C   = Quit

Run from macOS Terminal (not VS Code terminal):
  source .venv\\ stepper/bin/activate && python3 Stepper_control.py

Configuration:
  Edit room_config.json to set room dimensions and motor calibration.
"""

import sys
import tty
import termios
import serial
import time
import threading
import json
from pathlib import Path
from datetime import datetime


# ============================================================================
# CONFIGURATION
# ============================================================================

PORT = "/dev/cu.usbserial-0001"
BAUD = 115200

CONFIG_FILE = Path(__file__).parent / "room_config.json"
POSITION_FILE = Path(__file__).parent / "stepper_position.json"


def load_room_config() -> dict:
    """Load room configuration from room_config.json"""
    defaults = {
        "room_width_cm": 800,
        "room_depth_cm": 600,
        "motor1_cm_per_revolution": 8.0,
        "motor2_cm_per_revolution": 8.0,
        "steps_per_revolution": 1600,
        "steps_per_press": 200,
        "origin_offset_x_cm": 0.0,
        "origin_offset_y_cm": 0.0,
    }

    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r") as f:
                loaded = json.load(f)
            # Merge with defaults (loaded values override)
            defaults.update({k: v for k, v in loaded.items() if not k.startswith("_")})
            print(f"  Loaded config from {CONFIG_FILE.name}")
        except Exception as e:
            print(f"  Warning: Could not load {CONFIG_FILE.name}: {e}")
            print(f"  Using defaults")
    else:
        print(f"  No {CONFIG_FILE.name} found — using defaults")
        # Write defaults so user can edit
        try:
            with open(CONFIG_FILE, "w") as f:
                json.dump(defaults, f, indent=2)
        except Exception:
            pass

    return defaults


# ============================================================================
# POSITION TRACKER
# ============================================================================

class PositionTracker:
    """Tracks stepper motor position in steps and converts to cm."""

    def __init__(self, config: dict):
        self.config = config
        self.motor1_steps = 0  # X-axis (Left/Right)
        self.motor2_steps = 0  # Y-axis (Up/Down)
        self.steps_per_press = config["steps_per_press"]
        self._lock = threading.Lock()

    @property
    def cm_per_step_x(self) -> float:
        """Centimeters per single step for Motor 1 (X-axis)"""
        return self.config["motor1_cm_per_revolution"] / self.config["steps_per_revolution"]

    @property
    def cm_per_step_y(self) -> float:
        """Centimeters per single step for Motor 2 (Y-axis)"""
        return self.config["motor2_cm_per_revolution"] / self.config["steps_per_revolution"]

    @property
    def cm_per_press_x(self) -> float:
        """Centimeters per arrow key press for X-axis"""
        return self.steps_per_press * self.cm_per_step_x

    @property
    def cm_per_press_y(self) -> float:
        """Centimeters per arrow key press for Y-axis"""
        return self.steps_per_press * self.cm_per_step_y

    @property
    def x_cm(self) -> float:
        """Current X position in centimeters"""
        return (self.motor1_steps * self.cm_per_step_x) + self.config["origin_offset_x_cm"]

    @property
    def y_cm(self) -> float:
        """Current Y position in centimeters"""
        return (self.motor2_steps * self.cm_per_step_y) + self.config["origin_offset_y_cm"]

    def move_x(self, direction: str) -> None:
        """Move Motor 1 (X-axis). direction: 'CW' or 'CCW'"""
        with self._lock:
            if direction == "CW":
                self.motor1_steps += self.steps_per_press
            else:
                self.motor1_steps -= self.steps_per_press
            self._write_position(f"M1 {direction}")

    def move_y(self, direction: str) -> None:
        """Move Motor 2 (Y-axis). direction: 'CW' or 'CCW'"""
        with self._lock:
            if direction == "CW":
                self.motor2_steps += self.steps_per_press
            else:
                self.motor2_steps -= self.steps_per_press
            self._write_position(f"M2 {direction}")

    def home(self) -> None:
        """Reset position to origin (0, 0)"""
        with self._lock:
            self.motor1_steps = 0
            self.motor2_steps = 0
            self._write_position("HOME")

    def _write_position(self, last_direction: str) -> None:
        """Write current position to shared state file for RFID reader"""
        state = {
            "motor1_steps": self.motor1_steps,
            "motor2_steps": self.motor2_steps,
            "x_cm": round(self.x_cm, 2),
            "y_cm": round(self.y_cm, 2),
            "last_updated": datetime.now().astimezone().isoformat(),
            "last_direction": last_direction,
        }
        try:
            # Write atomically to prevent partial reads by the RFID reader
            tmp_file = POSITION_FILE.with_suffix(".tmp")
            with open(tmp_file, "w") as f:
                json.dump(state, f, indent=2)
            tmp_file.replace(POSITION_FILE)
        except Exception as e:
            sys.stdout.write(f"\r  ⚠ Position write error: {e}\n")
            sys.stdout.flush()

    def format_position(self) -> str:
        """Return formatted position string"""
        return (
            f"X={self.x_cm:+.2f}cm ({self.motor1_steps:+d} steps)  "
            f"Y={self.y_cm:+.2f}cm ({self.motor2_steps:+d} steps)"
        )


# ============================================================================
# INPUT HANDLING
# ============================================================================

def get_key():
    """Read a single keypress (blocking), handling arrow key escape sequences."""
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        if ch == '\x1b':  # Escape — could be arrow key
            ch2 = sys.stdin.read(1)
            if ch2 == '[':
                ch3 = sys.stdin.read(1)
                return {'C': 'RIGHT', 'D': 'LEFT', 'A': 'UP', 'B': 'DOWN'}.get(ch3)
            return None  # Bare ESC — ignore
        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


# ============================================================================
# SERIAL READER THREAD
# ============================================================================

def serial_reader(ser, stop_event):
    """Background thread to read and display ESP32 messages."""
    while not stop_event.is_set():
        try:
            if ser.in_waiting:
                line = ser.readline().decode('utf-8', errors='ignore').strip()
                if line:
                    if 'DONE' in line:
                        sys.stdout.write(f'\r  ✓ {line}                    \n')
                        sys.stdout.flush()
                    elif 'HALT' in line or 'EMERGENCY' in line:
                        sys.stdout.write(f'\r  ⛔ {line}                   \n')
                        sys.stdout.flush()
                    elif line.startswith('M1') or line.startswith('M2'):
                        sys.stdout.write(f'\r  ⚙ {line}                   \n')
                        sys.stdout.flush()
                    elif 'READY' in line:
                        sys.stdout.write(f'\r  ✅ {line}                   \n')
                        sys.stdout.flush()
                    else:
                        # Boot messages, etc.
                        sys.stdout.write(f'\r  {line}                      \n')
                        sys.stdout.flush()
            else:
                time.sleep(0.02)
        except Exception:
            break


# ============================================================================
# MAIN
# ============================================================================

def main():
    print()
    print("=" * 56)
    print("  DUAL STEPPER MOTOR CONTROLLER + POSITION TRACKING")
    print("=" * 56)
    print()

    # Load room config
    config = load_room_config()
    tracker = PositionTracker(config)

    # Print calibration info
    print()
    print(f"  Room:  {config['room_width_cm']}cm x {config['room_depth_cm']}cm")
    print(f"  Motor: {config['steps_per_revolution']} steps/rev, "
          f"{config['steps_per_press']} steps/press")
    print(f"  X-axis: {tracker.cm_per_press_x:.2f} cm per press "
          f"({config['motor1_cm_per_revolution']} cm/rev)")
    print(f"  Y-axis: {tracker.cm_per_press_y:.2f} cm per press "
          f"({config['motor2_cm_per_revolution']} cm/rev)")
    print(f"  Position file: {POSITION_FILE.name}")
    print()

    print("Opening serial port (ESP32 will reset)...")

    try:
        ser = serial.Serial(PORT, BAUD, timeout=0.1)
    except serial.SerialException as e:
        print(f"Error: {e}")
        sys.exit(1)

    print("Waiting for ESP32 boot...")
    time.sleep(3)

    # Flush boot messages
    if ser.in_waiting:
        ser.read(ser.in_waiting)

    # Initialize position file
    tracker.home()

    print()
    print("  Motor 1 (X-axis, GPIO 18/19):")
    print("    → Right Arrow  = CW  (+X)")
    print("    ← Left Arrow   = CCW (-X)")
    print()
    print("  Motor 2 (Y-axis, GPIO 16/17):")
    print("    ↑ Up Arrow     = CW  (+Y)")
    print("    ↓ Down Arrow   = CCW (-Y)")
    print()
    print("  H          = Home (reset to 0,0)")
    print("  P          = Print position")
    print("  S / Space  = Stop all")
    print("  X          = Emergency stop")
    print("  Q / Ctrl+C = Quit")
    print("=" * 56)
    print()
    print(f"  📍 Position: {tracker.format_position()}")
    print()
    print("Motors locked. Press arrow keys to move...")
    print()

    # Start background serial reader
    stop_event = threading.Event()
    reader = threading.Thread(target=serial_reader, args=(ser, stop_event), daemon=True)
    reader.start()

    try:
        while True:
            key = get_key()
            if key is None:
                continue

            cmd = None

            if key == 'RIGHT':
                cmd = 'R'
                tracker.move_x("CW")
                sys.stdout.write(f'\r  📍 {tracker.format_position()}                \n')
                sys.stdout.flush()
            elif key == 'LEFT':
                cmd = 'L'
                tracker.move_x("CCW")
                sys.stdout.write(f'\r  📍 {tracker.format_position()}                \n')
                sys.stdout.flush()
            elif key == 'UP':
                cmd = 'U'
                tracker.move_y("CW")
                sys.stdout.write(f'\r  📍 {tracker.format_position()}                \n')
                sys.stdout.flush()
            elif key == 'DOWN':
                cmd = 'D'
                tracker.move_y("CCW")
                sys.stdout.write(f'\r  📍 {tracker.format_position()}                \n')
                sys.stdout.flush()
            elif key in ('h', 'H'):
                tracker.home()
                sys.stdout.write(f'\r  🏠 Position reset to origin (0, 0)              \n')
                sys.stdout.flush()
                continue  # No motor command needed
            elif key in ('p', 'P'):
                sys.stdout.write(f'\r  📍 {tracker.format_position()}                \n')
                sys.stdout.flush()
                continue  # No motor command needed
            elif key in ('s', 'S', ' ', '0'):
                cmd = '0'
            elif key in ('x', 'X'):
                cmd = 'X'
            elif key in ('q', 'Q', '\x03'):
                # Stop motors before quitting
                ser.write(b'0')
                ser.flush()
                print("\n\nStopping motors and quitting...")
                print(f"  Final position: {tracker.format_position()}")
                time.sleep(0.5)
                break
            else:
                continue

            if cmd:
                ser.write(cmd.encode())
                ser.flush()

    except KeyboardInterrupt:
        ser.write(b'X')
        ser.flush()
        print("\n\nEmergency stop - quitting...")
        print(f"  Final position: {tracker.format_position()}")
        time.sleep(0.3)
    finally:
        stop_event.set()
        reader.join(timeout=1)
        ser.close()
        print("Port closed.")


if __name__ == "__main__":
    main()
