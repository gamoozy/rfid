/*
 * ESP32 Servo Controller Firmware - Simple Version (No External Libraries)
 * 
 * Controls two servos (X and Y axes) via serial commands
 * Uses built-in ESP32 PWM (ledcWrite) - no libraries needed!
 * 
 * Hardware Setup:
 * - Servo X: GPIO 18
 * - Servo Y: GPIO 23
 * - External 5-6V power supply with common ground
 * 
 * Serial Commands (115200 baud):
 * - X<angle>     : Set X servo angle (e.g., "X90")
 * - Y<angle>     : Set Y servo angle (e.g., "Y180")
 * - B<x>,<y>     : Set both servos (e.g., "B90,180")
 * - C            : Center both servos (180°)
 * - S            : Get status
 */

// GPIO pins
const int SERVO_X_PIN = 18;
const int SERVO_Y_PIN = 23;

// PWM channels (ESP32 has 16 channels)
const int SERVO_X_CHANNEL = 0;
const int SERVO_Y_CHANNEL = 1;

// PWM settings
const int PWM_FREQ = 50;        // 50Hz for servos
const int PWM_RESOLUTION = 16;  // 16-bit resolution

// Angle limits for 360° servos - EXTENDED RANGE
const int MIN_ANGLE = 0;
const int MAX_ANGLE = 390;  // Allow going past 360°
const int CENTER_ANGLE = 180;

// Current positions
int currentX = CENTER_ANGLE;
int currentY = CENTER_ANGLE;

// Lock state
bool isLocked = false;

// Serial buffer
String inputBuffer = "";

// Convert angle to PWM duty cycle
// Standard servo: 500-2500 microseconds for 0-360°
// For 50Hz (20ms period): duty = (pulse_us / 20000) * 65536
int angleToDuty(int angle) {
  // Wrap angles beyond 360 (e.g., 370 becomes 10)
  while (angle > 360) {
    angle -= 360;
  }
  while (angle < 0) {
    angle += 360;
  }
  
  // Clamp to 0-360 range
  angle = constrain(angle, 0, 360);
  
  // Map angle to pulse width (500-2500 microseconds)
  int pulseWidth = map(angle, 0, 360, 500, 2500);
  
  // Convert to 16-bit duty cycle
  // For 50Hz: period = 20000 microseconds
  int duty = (pulseWidth * 65536) / 20000;
  
  return duty;
}

void setup() {
  // Initialize serial
  Serial.begin(115200);
  while (!Serial) {
    delay(10);
  }
  
  Serial.println("\n=== ESP32 Servo Controller (Simple) ===");
  Serial.println("Firmware: v1.2 - ESP32 Core 3.x Compatible");
  Serial.println("Model: 360° Continuous Rotation Servos");
  Serial.println("Range: 0-390° (EXTENDED - wraps past 360)");
  
  // Configure PWM - ESP32 Arduino Core 3.x API
  Serial.println("\nConfiguring PWM channels...");
  
  // Detach pins first (new API)
  ledcDetach(SERVO_X_PIN);
  ledcDetach(SERVO_Y_PIN);
  
  // Attach PWM to pins (returns channel, but we ignore it)
  ledcAttach(SERVO_X_PIN, PWM_FREQ, PWM_RESOLUTION);
  Serial.print("  GPIO ");
  Serial.print(SERVO_X_PIN);
  Serial.println(" (X-axis) - CONFIGURED");
  
  ledcAttach(SERVO_Y_PIN, PWM_FREQ, PWM_RESOLUTION);
  Serial.print("  GPIO ");
  Serial.print(SERVO_Y_PIN);
  Serial.println(" (Y-axis) - CONFIGURED");
  
  // Initialize to center position
  int centerDuty = angleToDuty(currentX);
  ledcWrite(SERVO_X_PIN, centerDuty);
  ledcWrite(SERVO_Y_PIN, centerDuty);
  
  Serial.println("\nInitialized to center:");
  Serial.print("  X (GPIO ");
  Serial.print(SERVO_X_PIN);
  Serial.print("): ");
  Serial.print(currentX);
  Serial.print("° (duty: ");
  Serial.print(centerDuty);
  Serial.println(")");
  Serial.print("  Y (GPIO ");
  Serial.print(SERVO_Y_PIN);
  Serial.print("): ");
  Serial.print(currentY);
  Serial.print("° (duty: ");
  Serial.print(centerDuty);
  Serial.println(")");
  
  Serial.print("X Servo: GPIO ");
  Serial.println(SERVO_X_PIN);
  Serial.print("Y Servo: GPIO ");
  Serial.println(SERVO_Y_PIN);
  Serial.println("Center: 180°, 180°");
  Serial.println("\nReady! Waiting for commands...");
  Serial.println("Commands: X<angle>, Y<angle>, B<x>,<y>, C, S, L (lock), U (unlock), T (test)");
}

void loop() {
  // Read serial input
  while (Serial.available() > 0) {
    char c = Serial.read();
    
    if (c == '\n' || c == '\r') {
      // Process command
      if (inputBuffer.length() > 0) {
        processCommand(inputBuffer);
        inputBuffer = "";
      }
    } else {
      inputBuffer += c;
    }
  }
}

void processCommand(String cmd) {
  cmd.trim();
  
  if (cmd.length() == 0) {
    return;
  }
  
  Serial.print("CMD: ");
  Serial.println(cmd);
  
  char cmdType = cmd.charAt(0);
  
  switch (cmdType) {
    case 'X':
    case 'x':
      // Set X servo
      {
        int angle = cmd.substring(1).toInt();
        setServoX(angle);
      }
      break;
      
    case 'Y':
    case 'y':
      // Set Y servo
      {
        int angle = cmd.substring(1).toInt();
        setServoY(angle);
      }
      break;
      
    case 'B':
    case 'b':
      // Set both servos
      {
        int commaIndex = cmd.indexOf(',');
        if (commaIndex > 0) {
          int angleX = cmd.substring(1, commaIndex).toInt();
          int angleY = cmd.substring(commaIndex + 1).toInt();
          setBothServos(angleX, angleY);
        } else {
          Serial.println("ERROR: Invalid format. Use B<x>,<y>");
        }
      }
      break;
      
    case 'C':
    case 'c':
      // Center both servos
      centerServos();
      break;
      
    case 'S':
    case 's':
      // Status
      printStatus();
      break;
      
    case 'L':
    case 'l':
      // Lock servos in current position
      lockServos();
      break;
      
    case 'U':
    case 'u':
      // Unlock servos
      unlockServos();
      break;
      
    case 'T':
    case 't':
      // Test both servos
      testServos();
      break;
      
    default:
      Serial.print("ERROR: Unknown command: ");
      Serial.println(cmd);
      Serial.println("Valid: X<angle>, Y<angle>, B<x>,<y>, C, S, L (lock), U (unlock), T (test)");
  }
}

int clampAngle(int angle) {
  if (angle < MIN_ANGLE) return MIN_ANGLE;
  if (angle > MAX_ANGLE) return MAX_ANGLE;
  return angle;
}

void setServoX(int angle) {
  if (isLocked) {
    Serial.println("ERROR: Servos are LOCKED! Use 'U' to unlock.");
    return;
  }
  angle = clampAngle(angle);
  currentX = angle;
  
  int duty = angleToDuty(angle);
  
  // Debug output
  Serial.print("[DEBUG X] Angle:");
  Serial.print(angle);
  Serial.print(" Duty:");
  Serial.print(duty);
  Serial.print(" GPIO:");
  Serial.println(SERVO_X_PIN);
  
  ledcWrite(SERVO_X_PIN, duty);
  Serial.print("X → ");
  Serial.print(angle);
  Serial.println("°");
}

void setServoY(int angle) {
  if (isLocked) {
    Serial.println("ERROR: Servos are LOCKED! Use 'U' to unlock.");
    return;
  }
  angle = clampAngle(angle);
  currentY = angle;
  
  int duty = angleToDuty(angle);
  
  // Debug output
  Serial.print("[DEBUG Y] Angle:");
  Serial.print(angle);
  Serial.print(" Duty:");
  Serial.print(duty);
  Serial.print(" GPIO:");
  Serial.println(SERVO_Y_PIN);
  
  ledcWrite(SERVO_Y_PIN, duty);
  Serial.print("Y → ");
  Serial.print(angle);
  Serial.println("°");
}

void setBothServos(int angleX, int angleY) {
  if (isLocked) {
    Serial.println("ERROR: Servos are LOCKED! Use 'U' to unlock.");
    return;
  }
  angleX = clampAngle(angleX);
  angleY = clampAngle(angleY);
  currentX = angleX;
  currentY = angleY;
  ledcWrite(SERVO_X_PIN, angleToDuty(angleX));
  ledcWrite(SERVO_Y_PIN, angleToDuty(angleY));
  Serial.print("BOTH → X:");
  Serial.print(angleX);
  Serial.print("° Y:");
  Serial.print(angleY);
  Serial.println("°");
}

void centerServos() {
  if (isLocked) {
    Serial.println("ERROR: Servos are LOCKED! Use 'U' to unlock.");
    return;
  }
  setBothServos(CENTER_ANGLE, CENTER_ANGLE);
  Serial.println("CENTERED");
}

void printStatus() {
  Serial.println("\n--- STATUS ---");
  Serial.print("X Servo (GPIO ");
  Serial.print(SERVO_X_PIN);
  Serial.print("): ");
  Serial.print(currentX);
  Serial.println("°");
  
  Serial.print("Y Servo (GPIO ");
  Serial.print(SERVO_Y_PIN);
  Serial.print("): ");
  Serial.print(currentY);
  Serial.println("°");
  
  Serial.print("Range: ");
  Serial.print(MIN_ANGLE);
  Serial.print("-");
  Serial.print(MAX_ANGLE);
  Serial.println("°");
  
  Serial.print("Lock Status: ");
  Serial.println(isLocked ? "🔒 LOCKED" : "🔓 UNLOCKED");
  Serial.println("--------------\n");
}

void lockServos() {
  isLocked = true;
  Serial.println("===================");
  Serial.print("🔒 LOCKED at X:");
  Serial.print(currentX);
  Serial.print("° Y:");
  Serial.print(currentY);
  Serial.println("°");
  Serial.println("Servos CANNOT move until unlocked with 'U'");
  Serial.println("===================");
}

void unlockServos() {
  isLocked = false;
  Serial.println("===================");
  Serial.println("🔓 UNLOCKED");
  Serial.println("Servos can now move freely");
  Serial.println("===================");
}

void testServos() {
  Serial.println("\n=== SERVO TEST ===");
  Serial.println("Testing X servo (GPIO 18)...");
  
  // Test X at different angles
  Serial.println("X → 0°");
  setServoX(0);
  delay(1000);
  
  Serial.println("X → 180°");
  setServoX(180);
  delay(1000);
  
  Serial.println("X → 360°");
  setServoX(360);
  delay(1000);
  
  Serial.println("\nTesting Y servo (GPIO 23)...");
  
  // Test Y at different angles
  Serial.println("Y → 0°");
  setServoY(0);
  delay(1000);
  
  Serial.println("Y → 180°");
  setServoY(180);
  delay(1000);
  
  Serial.println("Y → 360°");
  setServoY(360);
  delay(1000);
  
  // Return to center
  Serial.println("\nReturning to center...");
  setBothServos(180, 180);
  
  Serial.println("=== TEST COMPLETE ===");
  Serial.println("If X didn't move but Y did, check:");
  Serial.println("  1. X servo signal wire on GPIO 18");
  Serial.println("  2. X servo power connection");
  Serial.println("  3. Try swapping X and Y servos to test");
  Serial.println();
}
