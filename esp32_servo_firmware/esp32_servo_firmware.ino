/*
 * ESP32 Servo Controller Firmware
 * 
 * Controls two servos (X and Y axes) via serial commands
 * Compatible with 270° servos (FT5835M) limited to 180° range
 * 
 * Hardware Setup:
 * - Servo X: GPIO 18
 * - Servo Y: GPIO 23
 * - External 5-6V power supply with common ground
 * 
 * Serial Commands (115200 baud):
 * - X<angle>     : Set X servo angle (e.g., "X90")
 * - Y<angle>     : Set Y servo angle (e.g., "Y135")
 * - B<x>,<y>     : Set both servos (e.g., "B90,135")
 * - C            : Center both servos (135°)
 * - S            : Get status
 */

#include <ESP32Servo.h>

// GPIO pins
const int SERVO_X_PIN = 18;
const int SERVO_Y_PIN = 23;

// Servo objects
Servo servoX;
Servo servoY;

// Angle limits for 270° servos limited to 180° range
const int MIN_ANGLE = 45;
const int MAX_ANGLE = 225;
const int CENTER_ANGLE = 135;

// Current positions
int currentX = CENTER_ANGLE;
int currentY = CENTER_ANGLE;

// Serial buffer
String inputBuffer = "";

void setup() {
  // Initialize serial
  Serial.begin(115200);
  while (!Serial) {
    delay(10);
  }
  
  Serial.println("\n=== ESP32 Servo Controller ===");
  Serial.println("Firmware: v1.0");
  Serial.println("Model: FT5835M (270° servos)");
  Serial.println("Range: 45-225° (180° limited)");
  
  // Configure servo library for ESP32
  ESP32PWM::allocateTimer(0);
  ESP32PWM::allocateTimer(1);
  
  // Attach servos
  servoX.setPeriodHertz(50);  // Standard 50Hz servo
  servoY.setPeriodHertz(50);
  
  servoX.attach(SERVO_X_PIN, 500, 2500);  // Min/Max pulse width in microseconds
  servoY.attach(SERVO_Y_PIN, 500, 2500);
  
  // Initialize to center position
  servoX.write(currentX);
  servoY.write(currentY);
  
  Serial.print("X Servo: GPIO ");
  Serial.println(SERVO_X_PIN);
  Serial.print("Y Servo: GPIO ");
  Serial.println(SERVO_Y_PIN);
  Serial.println("Center: 135°, 135°");
  Serial.println("\nReady! Waiting for commands...");
  Serial.println("Commands: X<angle>, Y<angle>, B<x>,<y>, C, S");
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
      
    default:
      Serial.print("ERROR: Unknown command: ");
      Serial.println(cmd);
      Serial.println("Valid: X<angle>, Y<angle>, B<x>,<y>, C, S");
  }
}

int clampAngle(int angle) {
  if (angle < MIN_ANGLE) return MIN_ANGLE;
  if (angle > MAX_ANGLE) return MAX_ANGLE;
  return angle;
}

void setServoX(int angle) {
  angle = clampAngle(angle);
  currentX = angle;
  servoX.write(angle);
  Serial.print("X → ");
  Serial.print(angle);
  Serial.println("°");
}

void setServoY(int angle) {
  angle = clampAngle(angle);
  currentY = angle;
  servoY.write(angle);
  Serial.print("Y → ");
  Serial.print(angle);
  Serial.println("°");
}

void setBothServos(int angleX, int angleY) {
  angleX = clampAngle(angleX);
  angleY = clampAngle(angleY);
  currentX = angleX;
  currentY = angleY;
  servoX.write(angleX);
  servoY.write(angleY);
  Serial.print("BOTH → X:");
  Serial.print(angleX);
  Serial.print("° Y:");
  Serial.print(angleY);
  Serial.println("°");
}

void centerServos() {
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
  Serial.println("--------------\n");
}
