#!/usr/bin/env python3
"""
Test 57600 baud specifically - it showed data in the command test
"""

import serial
import time

port = '/dev/cu.usbserial-110'
baud = 57600

print("="*60)
print(f"Testing 57600 baud with active tag scanning")
print("="*60)

try:
    ser = serial.Serial(port, baud, timeout=0.5)
    time.sleep(0.2)
    ser.reset_input_buffer()
    
    print("\nPlease scan a tag and hold it near the reader...")
    print("Monitoring for 10 seconds...\n")
    
    start = time.time()
    scan_count = 0
    last_data = None
    
    while time.time() - start < 10:
        if ser.in_waiting > 0:
            data = ser.read(ser.in_waiting)
            
            # Only show unique patterns
            if data != last_data:
                scan_count += 1
                print(f"--- Scan #{scan_count} ({len(data)} bytes) ---")
                
                # Show as hex
                hex_spaced = ' '.join(f'{b:02X}' for b in data)
                print(f"HEX: {hex_spaced}")
                
                # Show byte values
                print(f"DEC: {list(data[:30])}")  # First 30 bytes
                
                # Check for potential RSSI bytes
                if len(data) >= 4:
                    for i in range(min(10, len(data))):
                        b = data[i]
                        signed = b if b < 128 else b - 256
                        if -90 <= signed <= -20:
                            print(f"  Byte[{i}] = 0x{b:02X} → {signed:+4d} dBm (potential RSSI)")
                
                print()
                last_data = data
        
        time.sleep(0.05)
    
    if scan_count == 0:
        print("✗ No data received")
    else:
        print(f"✓ Received {scan_count} unique data patterns")
    
    ser.close()
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*60)
