#!/usr/bin/env python3
"""
Simple raw serial monitor - shows everything received
"""

import serial
import sys
import time

port = '/dev/cu.usbserial-110'
if len(sys.argv) > 1:
    port = sys.argv[1]

baud_rates = [9600, 19200, 38400, 57600, 115200]

print(f"Testing port: {port}")
print("="*60)

for baud in baud_rates:
    print(f"\n### Testing {baud} baud ###")
    try:
        ser = serial.Serial(port, baud, timeout=0.5)
        print(f"Connected at {baud} baud. Reading for 3 seconds...")
        print("SCAN A TAG NOW!")
        print("-"*60)
        
        start = time.time()
        data_received = False
        
        while time.time() - start < 3:
            if ser.in_waiting > 0:
                data = ser.read(ser.in_waiting)
                data_received = True
                
                # Show hex
                hex_str = ' '.join(f'{b:02X}' for b in data)
                print(f"HEX: {hex_str}")
                
                # Show ASCII (if printable)
                try:
                    ascii_str = data.decode('ascii', errors='replace')
                    if any(c.isprintable() and c != '\x00' for c in ascii_str):
                        print(f"ASCII: {ascii_str.strip()}")
                except:
                    pass
                
                # Show as decimal string
                try:
                    if all(b in b'0123456789\r\n ' for b in data):
                        print(f"DECIMAL: {data.decode('ascii').strip()}")
                except:
                    pass
                
                print()
            
            time.sleep(0.05)
        
        if not data_received:
            print("No data received")
        
        ser.close()
        
    except Exception as e:
        print(f"Error at {baud}: {e}")

print("\n" + "="*60)
print("Test complete!")
print("\nIf you saw readable data at a specific baud rate,")
print("run the main script with: --baud <that_rate>")
