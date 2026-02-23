#!/usr/bin/env python3
"""
Capture raw data from reader to analyze RSSI encoding
"""

import serial
import time

port = '/dev/cu.usbserial-110'
baud = 19200

print("Capturing raw data from reader...")
print("Scan a tag and we'll analyze the output\n")
print("="*60)

try:
    ser = serial.Serial(port, baud, timeout=0.5)
    time.sleep(0.2)
    ser.reset_input_buffer()
    
    print("Ready! Scan a tag now...")
    print("Press Ctrl+C to stop\n")
    
    last_data = None
    scan_count = 0
    
    while True:
        if ser.in_waiting > 0:
            data = ser.read(ser.in_waiting)
            
            # Only show unique patterns
            if data != last_data:
                scan_count += 1
                print(f"\n--- Scan #{scan_count} ({len(data)} bytes) ---")
                
                # Show as hex
                hex_str = data.hex().upper()
                print(f"HEX: {hex_str}")
                
                # Show as hex with spaces
                hex_spaced = ' '.join(f'{b:02X}' for b in data)
                print(f"HEX: {hex_spaced}")
                
                # Show byte values
                print(f"DEC: {list(data)}")
                
                # Try to show ASCII
                try:
                    ascii_str = data.decode('ascii', errors='replace')
                    if any(c.isprintable() and c not in [' ', '\r', '\n'] for c in ascii_str):
                        print(f"ASCII: {ascii_str}")
                except:
                    pass
                
                # Look for potential RSSI values (typically -30 to -90 dBm)
                print("\nPotential RSSI bytes (if signed -90 to -30):")
                for i, b in enumerate(data):
                    # Convert to signed
                    signed = b if b < 128 else b - 256
                    if -90 <= signed <= -30:
                        print(f"  Byte[{i}] = {b:02X} ({b:3d}) → {signed:3d} dBm")
                
                last_data = data
        
        time.sleep(0.05)
        
except KeyboardInterrupt:
    print("\n\nStopped.")
except Exception as e:
    print(f"Error: {e}")
