#!/usr/bin/env python3
"""
Manual Servo Control - Interactive ESP32 Servo Controller
Simple interface to test and move servos on GPIO 18 (X) and GPIO 23 (Y)
"""

import serial
import time
import sys

ESP32_PORT = '/dev/cu.usbserial-0001'
BAUDRATE = 115200

def connect_esp32():
    """Connect to ESP32"""
    print("🔌 Connecting to ESP32...")
    try:
        ser = serial.Serial(ESP32_PORT, BAUDRATE, timeout=1)
        time.sleep(2)  # Wait for ESP32 to boot
        
        # Read any startup messages
        if ser.in_waiting:
            print(ser.read_all().decode('utf-8', errors='ignore'))
        
        print("✅ Connected successfully!\n")
        return ser
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return None

def send_command(ser, cmd):
    """Send command to ESP32"""
    try:
        ser.write((cmd + '\n').encode())
        time.sleep(0.1)
        
        # Read response
        if ser.in_waiting:
            response = ser.read_all().decode('utf-8', errors='ignore')
            print(response)
    except Exception as e:
        print(f"Error: {e}")

def main():
    print("="*60)
    print("🎮 Manual Servo Control for ESP32")
    print("   X-axis: GPIO 18 | Y-axis: GPIO 23")
    print("="*60)
    
    # Connect
    ser = connect_esp32()
    if not ser:
        print("\n⚠️  Make sure you've uploaded the firmware to ESP32!")
        print("   Open esp32_servo_firmware.ino in Arduino IDE and upload it.")
        return
    
    print("📋 Commands:")
    print("   X<angle>  - Move X servo (e.g., X90, X0, X360)")
    print("   Y<angle>  - Move Y servo (e.g., Y180, Y0, Y360)")
    print("   B<x>,<y>  - Move both (e.g., B90,180)")
    print("   C         - Center both servos (180°)")
    print("   T         - 🔍 TEST both servos (auto sweep)")
    print("   L         - 🔒 LOCK servos in current position")
    print("   U         - 🔓 UNLOCK servos (allow movement)")
    print("   S         - Show status")
    print("   Q         - Quit")
    print("\n💡 Angle range: 0-360° FULL RANGE (center=180°)")
    print("="*60)
    
    try:
        # Send center command to start
        print("\n🏠 Centering servos...")
        send_command(ser, 'C')
        
        while True:
            # Get user input
            cmd = input("\n> ").strip()
            
            if not cmd:
                continue
            
            if cmd.upper() == 'Q':
                print("👋 Exiting...")
                break
            
            # Send command
            send_command(ser, cmd)
    
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
    finally:
        # Center servos before exit
        print("\n🏠 Centering servos before exit...")
        send_command(ser, 'C')
        time.sleep(0.5)
        ser.close()
        print("✅ Disconnected")

if __name__ == '__main__':
    main()
