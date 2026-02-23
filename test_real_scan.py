#!/usr/bin/env python3
"""
Quick test to verify only real scans are accepted
"""
import subprocess
import sys
import time
import signal

print("="*60)
print("FINAL TEST: Real vs Stale Scan Detection")
print("="*60)
print()
print("This test will:")
print("  1. Start the reader")
print("  2. Wait 5 seconds (startup + grace period)")
print("  3. Prompt you to scan")
print("  4. Show results")
print()
input("Press ENTER to start...")

proc = subprocess.Popen(
    [sys.executable, 'reader_capture.py', '--tagmap', 'tagmap.csv'],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True
)

print("\n[Starting reader...]")
time.sleep(5)

print("\n" + "="*60)
print(">>> SCAN YOUR TAG NOW! <<<")
print("="*60)

time.sleep(5)

print("\n[Stopping reader...]")
proc.send_signal(signal.SIGINT)
time.sleep(1)

output, _ = proc.communicate()

# Analyze
lines = output.split('\n')
scan_lines = [line for line in lines if 'SeatID=' in line]

print("\n" + "="*60)
print("RESULTS")
print("="*60)
print(f"\nScans detected: {len(scan_lines)}")

if scan_lines:
    print("\nScan details:")
    for line in scan_lines:
        print(f"  {line}")

# Show stats from output
for line in lines:
    if 'Accepted scans:' in line:
        print(f"\n{line}")
    elif 'Stale data filtered:' in line:
        print(line)
    elif 'Total reads:' in line:
        print(line)

print("\n" + "="*60)
print("VERDICT")
print("="*60)
if len(scan_lines) == 0:
    print("✗ NO scans detected - tag may not have been read")
    print("  Try holding tag closer to reader antenna")
elif len(scan_lines) == 1:
    print("✓ PERFECT! Exactly 1 scan detected from physical tag!")
else:
    print(f"⚠ {len(scan_lines)} scans detected")
    print("  This might be OK if you scanned multiple times")
