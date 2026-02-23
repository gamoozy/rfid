#!/usr/bin/env python3
"""
Arrow Key Servo Control - Control servos with keyboard arrow keys
Uses arrow keys to move servos continuously while held down
"""

import serial
import time
import sys
from pynput import keyboard
import threading

ESP32_PORT = '/dev/cu.usbserial-0001'
BAUDRATE = 115200

# Servo position tracking
current_x = 135  # Center (135 for X-axis)
current_y = 180  # Center
step_size = 15   # Degrees per step

# Angle limits
MIN_ANGLE_X = 0
MAX_ANGLE_X = 275  # Maximum left position
MIN_ANGLE_Y = 0
MAX_ANGLE_Y = 360

# Serial connection
ser = None

# Active keys for continuous movement
active_keys = set()
running = True
movement_thread = None

def connect_esp32():
    """Connect to ESP32"""
    global ser
    print("🔌 Connecting to ESP32...")
    try:
        ser = serial.Serial(ESP32_PORT, BAUDRATE, timeout=1)
        time.sleep(2)  # Wait for ESP32 to boot
        
        # Read any startup messages
        if ser.in_waiting:
            print(ser.read_all().decode('utf-8', errors='ignore'))
        
        print("✅ Connected successfully!\n")
        return True
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False

def send_command(cmd):
    """Send command to ESP32"""
    global ser
    try:
        ser.write((cmd + '\n').encode())
        # Clear buffer quickly
        while ser.in_waiting:
            ser.read(1)
    except Exception as e:
        print(f"Error: {e}")

def update_position():
    """Send current position to servos"""
    send_command(f'B{int(current_x)},{int(current_y)}')

def movement_loop():
    """Continuous movement while keys are held"""
    global current_x, current_y, running
    
    while running:
        moved = False
        
        if 'up' in active_keys:
            current_y = min(MAX_ANGLE_Y, current_y + step_size)
            moved = True
        if 'down' in active_keys:
            current_y = max(MIN_ANGLE_Y, current_y - step_size)
            moved = True
        if 'right' in active_keys:
            current_x = max(MIN_ANGLE_X, current_x - step_size)
            moved = True
        if 'left' in active_keys:
            current_x = min(MAX_ANGLE_X, current_x + step_size)
            moved = True
        
        if moved:
            update_position()
            print(f'\rX: {current_x:3d}°  Y: {current_y:3d}°  [Step: {step_size}° | Q=quit C=center]', end='', flush=True)
        
        time.sleep(0.05)  # 20 updates/second for smooth movement

def on_press(key):
    """Handle key press"""
    global current_x, current_y, step_size, running
    
    try:
        # Arrow keys - add to active set
        if key == keyboard.Key.up:
            active_keys.add('up')
        elif key == keyboard.Key.down:
            active_keys.add('down')
        elif key == keyboard.Key.right:
            active_keys.add('right')
        elif key == keyboard.Key.left:
            active_keys.add('left')
        
        # Other keys
        elif hasattr(key, 'char'):
            if key.char == 'c' or key.char == 'C':
                current_x = 135
                current_y = 180
                update_position()
                print("\n🏠 Centered                                    ")
            elif key.char == 'q' or key.char == 'Q':
                print("\n\n👋 Exiting...")
                running = False
                return False
            elif key.char == '+' or key.char == '=':
                step_size = min(90, step_size + 5)
                print(f"\n📏 Step size: {step_size}°                        ")
            elif key.char == '-' or key.char == '_':
                step_size = max(5, step_size - 5)
                print(f"\n📏 Step size: {step_size}°                        ")
    except:
        pass

def on_release(key):
    """Handle key release"""
    # Remove from active set
    if key == keyboard.Key.up:
        active_keys.discard('up')
    elif key == keyboard.Key.down:
        active_keys.discard('down')
    elif key == keyboard.Key.right:
        active_keys.discard('right')
    elif key == keyboard.Key.left:
        active_keys.discard('left')

def main():
    global ser, current_x, current_y, running, movement_thread
    
    print("="*60)
    print("⌨️  Arrow Key Servo Control")
    print("   X-axis: GPIO 18 | Y-axis: GPIO 23")
    print("="*60)
    
    # Connect
    if not connect_esp32():
        print("\n⚠️  Make sure ESP32 firmware is uploaded!")
        return
    
    print("🎮 Controls:")
    print("   ← →  - Move X-axis (← increases, → decreases)")
    print("   ↑ ↓  - Move Y-axis (up/down)")
    print("   C    - Center both servos (X=135°, Y=180°)")
    print("   +/-  - Increase/decrease step size")
    print("   Q    - Quit")
    print("\n💡 X Range: 0-275° | Y Range: 0-360° | Step: 15°")
    print("="*60)
    print()
    
    try:
        # Center servos initially
        send_command('B135,180')
        time.sleep(0.5)
        print(f'X: {current_x:3d}°  Y: {current_y:3d}°  [Step: {step_size}° | Q=quit C=center]', end='', flush=True)
        
        # Start movement thread
        movement_thread = threading.Thread(target=movement_loop, daemon=True)
        movement_thread.start()
        
        # Start listening for keyboard
        with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
            listener.join()
    
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
    finally:
        running = False
        if movement_thread:
            movement_thread.join(timeout=1)
        # Center servos before exit (X=135, Y=180)
        print("\n🏠 Centering servos before exit...")
        send_command('B135,180')
        time.sleep(0.5)
        if ser:
            ser.close()
        print("✅ Disconnected")

if __name__ == '__main__':
    main()
