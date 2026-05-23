# Student Portal UI — Figma Design Blueprint

## Core Idea Analysis

This is a **Hybrid RFID-QR Classroom Attendance System** built on a Raspberry Pi A+. The system works in two verification phases to prevent attendance fraud:

1. **QR Phase (Digital Identity):** The teacher creates a session, which generates an HMAC-signed QR code displayed in the classroom. Students scan this QR with their phones, proving they are physically in the room at that moment.

2. **RFID Phase (Physical Verification):** After scanning the QR, the student selects their assigned seat on a mobile dashboard. The system then actuates two servos (X/Y axes) to physically point an RFID reader at that seat's location. The student must have their RFID tag present at their seat for the system to verify attendance — proving the student is actually sitting there.

This dual-factor approach (QR = "I'm in the room" + RFID = "I'm at my seat") makes it extremely difficult to fake attendance.

---

## Design System Foundations

| Element | Value |
|---|---|
| **Primary Color** | `#4CAF50` (Green — verified/success) |
| **Secondary Color** | `#2196F3` (Blue — interactive elements) |
| **Warning Color** | `#FFC107` (Amber — scanning/pending) |
| **Error Color** | `#F44336` (Red) |
| **Background** | `#121212` dark theme or `#FAFAFA` light theme |
| **Font** | Inter or SF Pro (mobile-first) |
| **Corner Radius** | 12–16px (cards), 24px (buttons) |
| **Target Device** | Mobile (375×812 — iPhone frame) |

---

## Page-by-Page Breakdown

---

### PAGE 1: Splash / Welcome Screen

**Purpose:** App entry point, branding

| Element | Details |
|---|---|
| University/System logo | Centered, with subtle animation |
| App name | "Smart Attendance" |
| Tagline | "Scan. Sit. Verified." |
| "Get Started" button | Primary green CTA |
| Background | Subtle grid pattern reminiscent of classroom seats |

---

### PAGE 2: Student Login / ID Screen

**Purpose:** Identify the student before entering the flow

| Element | Details |
|---|---|
| Student ID input field | Text field, e.g. "STU-20231234" |
| Student Name (optional) | Auto-filled from university system or manual |
| "Continue" button | Disabled until valid ID entered |
| "Remember Me" toggle | Stores student_id locally |
| University branding | Small logo at top |

> **Figma tip:** Create a component with two states — empty and filled.

---

### PAGE 3: QR Scanner Screen (QR PHASE)

**Purpose:** Student scans the classroom QR code displayed by the teacher

**Layout:**

- **Top bar:** Back arrow + "Scan QR Code" title
- **Camera viewfinder:** Large rectangle (70% of screen) with rounded corners and scanning animation (moving horizontal line)
- **Corner brackets:** Four corner brackets framing the QR target area
- **Instruction text below viewfinder:**
  - "Point your camera at the QR code displayed in class"
  - Icon of a QR code with arrow pointing at it
- **Manual entry link:** "Enter code manually" (fallback if camera fails)
- **Status indicator:** Shows "Searching..." with a subtle pulse animation

**States to design:**

1. **Idle** — viewfinder open, waiting
2. **Detected** — QR found, brief green flash on viewfinder border
3. **Validating** — Spinner overlay: "Verifying session..."
4. **Expired QR Error** — Red banner: "This QR code has expired. Ask your teacher to generate a new one."
5. **Invalid QR Error** — Red banner: "Invalid QR code. Make sure you're scanning the attendance QR."
6. **Success** — Green checkmark animation, auto-navigates to Page 4

**QR Payload decoded (invisible to student):**

```
session_id, classroom_id, expiry timestamp, HMAC signature
```

---

### PAGE 4: Session Info Confirmation

**Purpose:** Confirm the student joined the correct session before seat selection

| Element | Details |
|---|---|
| Green success banner | "Session Joined!" with checkmark |
| Session card | Shows: Course name (e.g. "CS101"), Classroom ("Room A"), Date/Time, Valid until (countdown timer) |
| Student info | "Logged in as: STU-20231234" |
| "Select My Seat" button | Large primary CTA |
| Session timer | Circular countdown showing remaining validity |

---

### PAGE 5: Seat Selection Map (SEAT ALLOCATION PHASE)

**Purpose:** Interactive classroom grid where the student picks their physical seat

**Layout:**

- **Top bar:** "Select Your Seat" + session ID badge
- **Teacher desk label:** Horizontal bar at top: "FRONT — Teacher's Desk"
- **Seat grid:** 4 rows × 5 columns (A1–D5), or dynamic based on `seat_map.json`

**Seat grid visual (each seat is a rounded card):**

```
        Col 1    Col 2    Col 3    Col 4    Col 5
Row A   [ A1 ]   [ A2 ]   [ A3 ]   [ A4 ]   [ A5 ]
Row B   [ B1 ]   [ B2 ]   [ B3 ]   [ B4 ]   [ B5 ]
Row C   [ C1 ]   [ C2 ]   [ C3 ]   [ C4 ]   [ C5 ]
Row D   [ D1 ]   [ D2 ]   [ D3 ]   [ D4 ]   [ D5 ]
```

**Seat states (design as Figma variants):**

| State | Color | Border | Icon | Label |
|---|---|---|---|---|
| **Available** | Dark gray `#2D2D2D` | `#555` | None | "Available" |
| **Selected (by me)** | Blue `#2196F3` glow | `#64B5F6` | Pulse ring | "Selected" |
| **Occupied (by others)** | Muted red `#5D3A3A` | `#F44336` dim | Lock icon | "Taken" |
| **Scanning (my seat)** | Amber `#FFC107` | Glowing amber | Spinning radar | "Verifying..." |
| **Verified (mine)** | Green `#4CAF50` | Glowing green | Checkmark | "Verified!" |
| **Verified (others)** | Dim green `#2E5F2E` | `#4CAF50` dim | Small check | "Occupied" |

**Interactive behavior:**

1. Student taps an "Available" seat
2. Confirmation bottom sheet slides up: "Confirm seat **B3**?"
3. Button: "Claim This Seat" (calls `POST /api/attendance/claim`)
4. After tap, seat turns amber/scanning state

**Bottom section (persistent):**

- Live stats bar: "Present: 5/20 (25%)"
- Legend: color circles with labels

**Figma tip:** Build each seat as a component with 6 variants. Use auto-layout for the grid.

---

### PAGE 6: RFID Verification Waiting Screen

**Purpose:** After claiming a seat, student sees real-time verification status

**Layout:**

- **Top:** "Verifying Your Seat" title
- **Seat info card:** "Seat B3 — Row B, Column 3"
- **Large central animation:** Radar/pulse animation showing the RFID reader physically pointing at their seat (servo visualization)
  - Show X-angle and Y-angle in a subtle data readout
  - "The reader is now pointing at your seat..."
- **Instruction:** "Make sure your RFID tag is on your desk"
- **Progress indicator:** 5-second countdown ring (matches `verification_timeout: 5.0`)
- **Status text (dynamic):**
  - "Moving to your seat..." (servos repositioning)
  - "Scanning for your tag..." (RFID reading)
  - "Tag detected! Verifying..." (tag found, checking match)

**Outcomes (transition to):**

- **Success:** Green explosion animation → Page 7
- **Timeout:** "No tag detected. Try again?" with Retry button
- **Wrong tag:** "Tag doesn't match seat B3. Are you at the right seat?"

---

### PAGE 7: Verification Success Screen

**Purpose:** Confirm attendance was recorded

| Element | Details |
|---|---|
| Large green checkmark | Animated, with confetti or glow |
| "Attendance Verified!" | Bold, large text |
| Details card | Seat: B3, Time: 10:32 AM, Session: CS101-2025-01-15, Status: Present |
| Digital receipt | "Screenshot this as proof" |
| "Done" button | Returns to a summary or closes |
| Share/Save option | Save confirmation as image |

---

### PAGE 8: Student Dashboard (Post-Verification)

**Purpose:** Student's overview after verification or for returning users

**Sections:**

1. **Current session card** — Green if verified, amber if pending
2. **Attendance history** — List of past sessions with date, course, seat, status
3. **Attendance percentage** — Donut chart showing overall rate
4. **Upcoming classes** (optional) — Schedule integration

---

### PAGE 9: Error / Edge Case Screens

Design these as overlay/modal states:

| Scenario | UI |
|---|---|
| **Session expired** | Clock icon + "This session has ended" + contact teacher |
| **Already verified** | Info icon + "You've already been marked present for this session" |
| **System busy (scan_lock active)** | Queue icon + "Another student is being verified. Please wait..." + estimated wait time |
| **Seat already taken** | Lock icon + "Seat B3 is already claimed by another student" |
| **No RFID reader** | Warning icon + "Hardware not available. Contact your instructor." |
| **Network error** | Offline icon + "Can't connect to the system. Check your WiFi." |

---

## Complete User Flow Diagram

```
[Splash] → [Login] → [QR Scanner] → [Session Confirmed] → [Seat Map]
                                                                 │
                                                          Select a seat
                                                                 │
                                                      [RFID Verification Wait]
                                                           │           │
                                                      ✓ Success    ✗ Failure
                                                           │           │
                                                   [Success Screen]  [Retry/Error]
                                                           │
                                                    [Dashboard]
```

---

## Figma Organization Recommendations

| Figma Page | Contents |
|---|---|
| **Cover** | Project title, team, date |
| **Design System** | Colors, typography, icons, spacing tokens |
| **Components** | Seat card (6 variants), buttons, inputs, status banners, nav bars |
| **Student Flow** | All 9 screens in sequence, connected with flow arrows |
| **States & Overlays** | Error modals, loading states, empty states |
| **Prototype** | Interactive prototype with: QR scan → seat select → verify → success |

**Key components to build first:**

1. **Seat Card component** — 6 variants (available, selected, occupied, scanning, verified-mine, verified-other)
2. **Status Banner** — success (green), warning (amber), error (red), info (blue)
3. **Countdown Ring** — for the 5-second RFID verification window
4. **Session Card** — reusable for dashboard and confirmation screens
5. **Bottom Sheet** — for seat confirmation dialog

---

## API Endpoint Mapping

These are the backend endpoints the student portal screens interact with:

| Screen | API Endpoint | Method |
|---|---|---|
| QR Scanner | `/api/session/create` (teacher) | POST |
| QR Validation | `QRService.validate_qr()` (client-side decode) | — |
| Seat Selection | `/api/classroom/state` | GET |
| Claim Seat | `/api/attendance/claim` | POST |
| Verification Status | `/api/status` | GET |
| Dashboard | `/api/session/<session_id>` | GET |
| Reset | `/api/reset` | POST |
