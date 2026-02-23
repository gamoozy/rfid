#!/usr/bin/env python3
"""
Test if reader responds to commands at different baud rates
"""

import serial
import time

port = '/dev/cu.usbserial-110'

print("Testing reader command mode at different baud rates...\n")

# Test both baud rates
for baud in [115200, 19200, 57600, 9600]:
    print(f"\n{'='*60}")
    print(f"Testing at {baud} baud")
    print('='*60)
    
    try:
        ser = serial.Serial(port, baud, timeout=0.5)
        time.sleep(0.2)
        
        # Clear any existing data
        ser.reset_input_buffer()
        time.sleep(0.1)
        
        # Send inventory command
        cmd = bytes([0xA0, 0x04, 0x89, 0x00, 0x8D, 0xA1])
        print(f"Sending inventory command: {cmd.hex().upper()}")
        ser.write(cmd)
        time.sleep(0.3)
        
        # Check for response
        if ser.in_waiting > 0:
            response = ser.read(ser.in_waiting)
            print(f"✓ Got response ({len(response)} bytes): {response.hex().upper()}")
            print(f"  First byte: 0x{response[0]:02X}")
            
            # Check if it's a valid frame
            if response[0] == 0xA0:
                print(f"  → Valid 0xA0 frame!")
            elif response[0] == 0xBB:
                print(f"  → Valid 0xBB frame!")
        else:
            print("✗ No response")
        
        # Try listening for a bit to see if there's continuous output
        print("\nListening for 2 seconds...")
        start = time.time()
        data_received = False
        while time.time() - start < 2:
            if ser.in_waiting > 0:
                data = ser.read(min(50, ser.in_waiting))
                if not data_received:
                    print(f"Continuous data detected: {data.hex().upper()}")
                    data_received = True
            time.sleep(0.1)
        
        if not data_received:
            print("No continuous data")
        
        ser.close()
        
    except Exception as e:
        print(f"Error: {e}")

print("\n" + "="*60)
print("Test complete!")
