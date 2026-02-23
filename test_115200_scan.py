#!/usr/bin/env python3
"""
Test 115200 baud with active tag scanning
"""

import serial
import time

port = '/dev/cu.usbserial-110'

print("Testing 115200 baud with tag scanning")
print("="*60)

for baud in [115200, 19200]:
    print(f"\n{'='*60}")
    print(f"Testing at {baud} baud")
    print('='*60)
    
    try:
        ser = serial.Serial(port, baud, timeout=0.5)
        time.sleep(0.2)
        ser.reset_input_buffer()
        
        print("Please scan a tag now...")
        print("Listening for 5 seconds...\n")
        
        start = time.time()
        data_count = 0
        
        while time.time() - start < 5:
            if ser.in_waiting > 0:
                data = ser.read(ser.in_waiting)
                data_count += 1
                
                hex_str = ' '.join(f'{b:02X}' for b in data[:50])  # Show first 50 bytes
                print(f"[{data_count}] Received {len(data)} bytes: {hex_str}")
                
                # Check for potential RSSI in data
                if len(data) >= 4:
                    print(f"    Byte[3] = 0x{data[3]:02X} ({data[3]:3d}) → signed: {data[3] if data[3] < 128 else data[3] - 256:+4d}")
            
            time.sleep(0.05)
        
        if data_count == 0:
            print("✗ No data received")
        else:
            print(f"\n✓ Received {data_count} data packets")
        
        ser.close()
        
    except Exception as e:
        print(f"Error: {e}")

print("\n" + "="*60)
print("Test complete!")
