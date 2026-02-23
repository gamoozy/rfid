#!/usr/bin/env python3
"""
Classroom Visualization - Real-time RFID Attendance Display

Shows a classroom with 20 desks. Desks light up green when their seat is scanned.
Monitors the SQLite database for new scans in real-time.
"""

import tkinter as tk
from tkinter import font as tkfont
import sqlite3
import time
import threading
from datetime import datetime, timedelta
from pathlib import Path


class ClassroomVisualization:
    def __init__(self, db_path='rfid_scans.db', rows=4, cols=5):
        self.db_path = db_path
        self.rows = rows
        self.cols = cols
        self.total_desks = rows * cols
        
        # Track which seats have been scanned
        self.scanned_seats = set()
        self.last_check_time = time.time() - 60  # Check last minute on startup
        
        # Create main window
        self.root = tk.Tk()
        self.root.title("Classroom Attendance - RFID Scanner")
        self.root.configure(bg='#1e1e1e')
        
        # Set window size
        window_width = 1200
        window_height = 800
        self.root.geometry(f"{window_width}x{window_height}")
        
        # Create UI
        self.create_ui()
        
        # Start monitoring thread
        self.running = True
        self.monitor_thread = threading.Thread(target=self.monitor_database, daemon=True)
        self.monitor_thread.start()
        
        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def create_ui(self):
        """Create the user interface"""
        # Title
        title_frame = tk.Frame(self.root, bg='#1e1e1e')
        title_frame.pack(pady=20)
        
        title_font = tkfont.Font(family='Helvetica', size=24, weight='bold')
        title_label = tk.Label(
            title_frame,
            text="🎓 Classroom Attendance Monitor",
            font=title_font,
            bg='#1e1e1e',
            fg='#ffffff'
        )
        title_label.pack()
        
        # Status bar
        self.status_label = tk.Label(
            title_frame,
            text="Waiting for scans...",
            font=('Helvetica', 12),
            bg='#1e1e1e',
            fg='#888888'
        )
        self.status_label.pack(pady=5)
        
        # Classroom grid
        classroom_frame = tk.Frame(self.root, bg='#1e1e1e')
        classroom_frame.pack(expand=True, fill='both', padx=40, pady=20)
        
        # Configure grid weights for centering
        for i in range(self.rows):
            classroom_frame.grid_rowconfigure(i, weight=1)
        for j in range(self.cols):
            classroom_frame.grid_columnconfigure(j, weight=1)
        
        # Create desk widgets
        self.desk_frames = {}
        seat_num = 1
        
        for row in range(self.rows):
            for col in range(self.cols):
                seat_id = f"SEAT-{seat_num:03d}"
                desk = self.create_desk(classroom_frame, seat_id, row, col)
                self.desk_frames[seat_id] = desk
                seat_num += 1
        
        # Stats panel
        stats_frame = tk.Frame(self.root, bg='#2d2d2d', relief='solid', bd=1)
        stats_frame.pack(fill='x', padx=40, pady=(0, 20))
        
        stats_font = tkfont.Font(family='Helvetica', size=14, weight='bold')
        self.stats_label = tk.Label(
            stats_frame,
            text=f"Present: 0 / {self.total_desks}",
            font=stats_font,
            bg='#2d2d2d',
            fg='#4CAF50',
            pady=10
        )
        self.stats_label.pack()
    
    def create_desk(self, parent, seat_id, row, col):
        """Create a single desk widget"""
        # Main desk frame
        desk_frame = tk.Frame(
            parent,
            bg='#3d3d3d',
            relief='raised',
            bd=2,
            highlightthickness=2,
            highlightbackground='#555555'
        )
        desk_frame.grid(row=row, column=col, padx=10, pady=10, sticky='nsew')
        
        # Seat number (large)
        seat_font = tkfont.Font(family='Helvetica', size=32, weight='bold')
        seat_label = tk.Label(
            desk_frame,
            text=seat_id.split('-')[1],  # Just the number
            font=seat_font,
            bg='#3d3d3d',
            fg='#888888',
            pady=20
        )
        seat_label.pack()
        
        # Status indicator
        status_font = tkfont.Font(family='Helvetica', size=10)
        status_label = tk.Label(
            desk_frame,
            text="EMPTY",
            font=status_font,
            bg='#3d3d3d',
            fg='#666666',
            pady=5
        )
        status_label.pack()
        
        # Store references
        return {
            'frame': desk_frame,
            'seat_label': seat_label,
            'status_label': status_label,
            'seat_id': seat_id,
            'scanned': False
        }
    
    def light_up_desk(self, seat_id):
        """Light up a desk when scanned"""
        if seat_id not in self.desk_frames:
            # Handle UNKNOWN or seats not in grid
            if seat_id == 'UNKNOWN':
                self.update_status(f"⚠️ Unknown tag scanned!")
            return
        
        desk = self.desk_frames[seat_id]
        
        if not desk['scanned']:
            # Light up the desk
            desk['frame'].configure(bg='#4CAF50', highlightbackground='#66BB6A')
            desk['seat_label'].configure(bg='#4CAF50', fg='#ffffff')
            desk['status_label'].configure(
                text="✓ PRESENT",
                bg='#4CAF50',
                fg='#ffffff'
            )
            desk['scanned'] = True
            self.scanned_seats.add(seat_id)
            
            # Update stats
            self.update_stats()
            
            # Update status
            seat_num = seat_id.split('-')[1]
            self.update_status(f"✓ Seat {seat_num} scanned - Student present!")
            
            # Flash effect
            self.root.after(100, lambda: self.flash_desk(seat_id, 0))
    
    def flash_desk(self, seat_id, count):
        """Create a subtle flash effect"""
        if count >= 4 or seat_id not in self.desk_frames:
            return
        
        desk = self.desk_frames[seat_id]
        
        if count % 2 == 0:
            desk['frame'].configure(highlightbackground='#81C784')
        else:
            desk['frame'].configure(highlightbackground='#66BB6A')
        
        self.root.after(100, lambda: self.flash_desk(seat_id, count + 1))
    
    def update_stats(self):
        """Update the statistics display"""
        present = len(self.scanned_seats)
        percentage = (present / self.total_desks) * 100 if self.total_desks > 0 else 0
        
        self.stats_label.configure(
            text=f"Present: {present} / {self.total_desks}  |  {percentage:.0f}% Attendance"
        )
    
    def update_status(self, message):
        """Update the status message"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.status_label.configure(text=f"[{timestamp}] {message}")
    
    def monitor_database(self):
        """Monitor the database for new scans"""
        while self.running:
            try:
                if not Path(self.db_path).exists():
                    time.sleep(1)
                    continue
                
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                # Get new scans since last check
                cursor.execute("""
                    SELECT DISTINCT seat_id, MAX(timestamp_epoch) as last_scan
                    FROM rfid_scans
                    WHERE timestamp_epoch > ?
                    GROUP BY seat_id
                    ORDER BY last_scan DESC
                """, (self.last_check_time,))
                
                new_scans = cursor.fetchall()
                
                for seat_id, scan_time in new_scans:
                    if seat_id not in self.scanned_seats:
                        # Schedule UI update in main thread
                        self.root.after(0, self.light_up_desk, seat_id)
                
                # Update last check time
                if new_scans:
                    self.last_check_time = max(scan[1] for scan in new_scans)
                
                conn.close()
                
            except Exception as e:
                print(f"Database monitor error: {e}")
            
            time.sleep(0.5)  # Check every 500ms
    
    def on_closing(self):
        """Handle window close event"""
        self.running = False
        self.root.destroy()
    
    def run(self):
        """Start the visualization"""
        self.update_status("Ready - Monitoring for scans...")
        self.root.mainloop()


def main():
    """Main entry point"""
    import sys
    
    # Check if database exists
    db_path = Path('rfid_scans.db')
    if not db_path.exists():
        print("Warning: Database not found. Make sure to run reader_capture.py first.")
        print("Creating visualization anyway - it will activate when scans are detected.\n")
    
    print("="*60)
    print("Classroom Attendance Visualization")
    print("="*60)
    print("\nStarting visualization...")
    print("- Window shows 20 desks (4 rows x 5 columns)")
    print("- Desks light up GREEN when scanned")
    print("- Real-time monitoring of rfid_scans.db")
    print("\nKeep the reader running in another terminal!")
    print("="*60)
    
    # Create and run visualization
    viz = ClassroomVisualization(db_path=str(db_path), rows=4, cols=5)
    viz.run()


if __name__ == '__main__':
    main()
