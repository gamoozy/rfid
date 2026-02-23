#!/usr/bin/env python3
"""
Quick test script for ESP32 servo controller
"""

from servo_controller_esp32 import ServoController
import time

print("="*60)
print("🤖 ESP32 Servo Controller - Quick Test")
print("="*60)

# Create controller
controller = ServoController()

# Connect
print("\n📡 Connecting to ESP32...")
if controller.connect():
    print("✅ Connected successfully!")
    print(f"   Port: {controller.port}")
    print(f"   Current position: X={controller.current_x}°, Y={controller.current_y}°")
    
    try:
        # Test movements
        print("\n🔄 Testing servo movements...")
        
        print("\n1. Moving to A1 (90, 90)...")
        controller.move_to(90, 90)
        time.sleep(2)
        
        print("2. Moving to A3 (180, 90)...")
        controller.move_to(180, 90)
        time.sleep(2)
        
        print("3. Moving to center (135, 135)...")
        controller.center()
        time.sleep(2)
        
        print("\n✅ All tests passed!")
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Error during test: {e}")
    finally:
        print("\n📴 Disconnecting...")
        controller.disconnect()
        print("👋 Done!")
else:
    print("❌ Failed to connect to ESP32")
    print("\n🔧 Troubleshooting:")
    print("   1. Is ESP32 plugged in via USB?")
    print("   2. Is the firmware uploaded to ESP32?")
    print("   3. Are servos connected to GPIO 18 (X) and GPIO 23 (Y)?")
    print("   4. Is external 5-6V power connected to servos?")
