#!/usr/bin/env python3
"""
Find which byte contains RSSI by comparing scans at different distances
"""

import serial
import time

port = '/dev/cu.usbserial-110'
baud = 19200

print("RSSI Detection Test")
print("="*60)
print("IMPORTANT: Use the SAME tag for both scans!")
print()
print("Instructions:")
print("  1. Hold ONE tag CLOSE to reader - scan it")
print("  2. Hold THE SAME tag FAR from reader - scan it")
print("  3. We'll compare which byte changes (that's the RSSI!)")
print()
print("⚠️  DO NOT use different tags - this test won't work!")
print("="*60)

scans = []

try:
    ser = serial.Serial(port, baud, timeout=0.5)
    time.sleep(0.2)
    ser.reset_input_buffer()
    
    input("\nPress ENTER when ready to scan CLOSE (strong signal)...")
    
    print("Scanning... (move tag away after first detection)")
    
    last_data = None
    
    waiting_for_input = False
    
    while len(scans) < 2:
        try:
            if waiting_for_input:
                time.sleep(0.1)
                continue
                
            if ser.in_waiting > 0:
                data = ser.read(ser.in_waiting)
                
                # For first scan, check it's different from last_data
                # For second scan, accept any data (RSSI might be only byte that changed)
                should_capture = (data and len(data) >= 20 and 
                                (len(scans) == 0 and data != last_data) or 
                                (len(scans) == 1))
                
                if should_capture:
                    scans.append(data)
                    print(f"\n✓ Scan #{len(scans)} captured ({len(data)} bytes)")
                    
                    hex_spaced = ' '.join(f'{b:02X}' for b in data)
                    print(f"  HEX: {hex_spaced}")
                    
                    if len(scans) == 1:
                        waiting_for_input = True
                        input("\nPress ENTER when ready to scan FAR (weak signal)...")
                        waiting_for_input = False
                        last_data = None  # Reset so we can capture same tag
                        ser.reset_input_buffer()  # Clear buffer
                        time.sleep(0.5)
                    
                    last_data = data
        except Exception as e:
            # Ignore transient serial errors
            pass
        
        time.sleep(0.05)
    
    ser.close()
    
    # Compare the two scans
    print("\n" + "="*60)
    print("COMPARISON - Looking for RSSI byte")
    print("="*60)
    
    scan1, scan2 = scans[0], scans[1]
    min_len = min(len(scan1), len(scan2))
    
    print(f"\nByte-by-byte comparison (first {min_len} bytes):")
    print(f"{'Pos':<5} {'Close':<8} {'Far':<8} {'Diff':<6} {'RSSI?'}")
    print("-" * 60)
    
    for i in range(min_len):
        b1, b2 = scan1[i], scan2[i]
        diff = abs(b1 - b2)
        
        # Convert to signed for RSSI display
        s1 = b1 if b1 < 128 else b1 - 256
        s2 = b2 if b2 < 128 else b2 - 256
        
        # Mark as potential RSSI if:
        # 1. Values are different
        # 2. Both are in RSSI range (-90 to -20)
        # 3. Close signal is stronger (less negative) than far
        is_rssi = (diff > 0 and 
                   -90 <= s1 <= -20 and 
                   -90 <= s2 <= -20 and
                   s1 > s2)
        
        marker = " ← LIKELY RSSI!" if is_rssi else ""
        
        if diff > 0:
            print(f"[{i:2d}]  0x{b1:02X} ({s1:+4d}) 0x{b2:02X} ({s2:+4d}) Δ={diff:3d}  {marker}")
    
    print("\n" + "="*60)
    
except KeyboardInterrupt:
    print("\n\nCancelled.")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
