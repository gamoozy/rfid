#!/usr/bin/env python3
"""
RFID Reader Command Tool

Sends commands to R16-12DB reader to configure and start inventory.
Use this to test if the reader responds to commands.
"""

import serial
import serial.tools.list_ports
import time
import sys

# Common R16-12DB commands
COMMANDS = {
    'inventory_single': bytes([0xA0, 0x04, 0x89, 0x00, 0x8D, 0xA1]),  # Single inventory
    'inventory_continuous': bytes([0xA0, 0x04, 0x27, 0x00, 0x2B, 0xA1]),  # Continuous inventory
    'stop_inventory': bytes([0xA0, 0x03, 0x28, 0x2B, 0xA1]),  # Stop inventory
    'get_version': bytes([0xA0, 0x03, 0x74, 0x77, 0xA1]),  # Get firmware version
    'set_power': bytes([0xA0, 0x05, 0xB6, 0x00, 0x1E, 0xD5, 0xA1]),  # Set power to 30dBm
}

def find_reader_port():
    """Find the RFID reader port"""
    ports = list(serial.tools.list_ports.comports())
    for port in ports:
        if 'usbserial' in port.device:
            return port.device
    return None

def send_command(ser, command_name):
    """Send a command to the reader"""
    if command_name not in COMMANDS:
        print(f"Unknown command: {command_name}")
        return
    
    cmd = COMMANDS[command_name]
    print(f"\nSending {command_name}: {cmd.hex()}")
    ser.write(cmd)
    time.sleep(0.1)
    
    # Read response
    if ser.in_waiting > 0:
        response = ser.read(ser.in_waiting)
        print(f"Response ({len(response)} bytes): {response.hex()}")
        return response
    else:
        print("No response")
        return None

def main():
    port = find_reader_port()
    if not port:
        print("No reader found. Please specify port.")
        if len(sys.argv) > 1:
            port = sys.argv[1]
        else:
            sys.exit(1)
    
    print(f"Connecting to {port}...")
    
    try:
        ser = serial.Serial(port, 115200, timeout=1)
        print("Connected!")
        
        # Try to get version first
        print("\n=== Testing reader communication ===")
        send_command(ser, 'get_version')
        time.sleep(0.5)
        
        # Set power
        print("\n=== Setting power ===")
        send_command(ser, 'set_power')
        time.sleep(0.5)
        
        # Start continuous inventory
        print("\n=== Starting continuous inventory ===")
        print("Place a tag near the reader...")
        send_command(ser, 'inventory_continuous')
        
        # Read for 10 seconds
        print("\nListening for tags (10 seconds)...")
        start_time = time.time()
        while time.time() - start_time < 10:
            if ser.in_waiting > 0:
                data = ser.read(ser.in_waiting)
                print(f"\nReceived ({len(data)} bytes): {data.hex()}")
                print(f"  ASCII: {data}")
            time.sleep(0.1)
        
        # Stop inventory
        print("\n=== Stopping inventory ===")
        send_command(ser, 'stop_inventory')
        
        ser.close()
        print("\nDone!")
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
