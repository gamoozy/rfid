#!/usr/bin/env python3
"""
Debug test - shows what happens when you scan tags
"""
import subprocess
import sys
import time
import signal
import threading

def print_scan_events(proc):
    """Print only scan-related events"""
    for line in iter(proc.stdout.readline, ''):
        if not line:
            break
        if any(x in line for x in ['SeatID=', 'Different tag', 'STALE', 'accepted']):
            print(line.rstrip())

print("="*60)
print("DEBUG TEST - See what happens when you scan")
print("="*60)
print("\nStarting reader with debug output...")
print("Scan your tags and watch for scan events below.")
print("Press Ctrl+C to stop.\n")
print("-"*60)

proc = subprocess.Popen(
    [sys.executable, 'reader_capture.py', '--debug', '--tagmap', 'tagmap.csv'],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
    bufsize=1
)

# Start thread to print output
thread = threading.Thread(target=print_scan_events, args=(proc,))
thread.daemon = True
thread.start()

try:
    time.sleep(5)
    print("\n>>> SCAN FIRST TAG NOW <<<\n")
    time.sleep(5)
    print("\n>>> SCAN SECOND TAG NOW (different one) <<<\n")
    time.sleep(5)
    print("\n>>> SCAN THIRD TAG (optional) <<<\n")
    time.sleep(5)
except KeyboardInterrupt:
    pass

print("\n" + "-"*60)
print("Stopping reader...")
proc.send_signal(signal.SIGINT)
proc.wait()

print("\nTest complete.")
print("\nExpected behavior:")
print("  - Each different tag should show 'SeatID=...' once")
print("  - Same tag scanned again should be marked STALE")
print("  - Different tags should be accepted immediately")
