/*
 * ESP32 + Dual CS-D508 — Two-Motor Arrow Key Controller
 * 
 * Motor 1 (Left/Right arrows): GPIO 18 = STEP, GPIO 19 = DIR
 * Motor 2 (Up/Down arrows):    GPIO 16 = STEP, GPIO 17 = DIR
 * 
 * Each arrow key press moves the corresponding motor a fixed number
 * of steps. Motors are locked (holding position) when idle.
 * 
 * Serial Protocol:
 *   R = Motor 1 CW  (Right arrow)
 *   L = Motor 1 CCW (Left arrow)
 *   U = Motor 2 CW  (Up arrow)
 *   D = Motor 2 CCW (Down arrow)
 *   0 = Stop all movement
 *   X = Emergency stop
 */

// ===== Motor 1 Pins (Left/Right arrows) =====
#define M1_STEP_PIN 18
#define M1_DIR_PIN  19

// ===== Motor 2 Pins (Up/Down arrows) =====
#define M2_STEP_PIN 16
#define M2_DIR_PIN  17

#define LED_PIN 2

// ===== Configuration =====
#define STEPS_PER_REV  1600        // Must match DIP switch setting (8x microstepping)
#define STEPS_PER_PRESS 1          // Steps per arrow key press (1 microstep)
#define STEP_SPEED     400.0       // Steps/sec (~15 RPM) — slower speed

// ===== Motor State =====
struct Motor {
  uint8_t stepPin;
  uint8_t dirPin;
  volatile long stepsRemaining;    // Steps left to execute (0 = idle/locked)
  bool direction;                  // true = CW, false = CCW
  unsigned long lastStepTime;      // Micros of last step pulse
  unsigned long stepInterval;      // Micros between steps
  const char* name;
};

Motor motor1 = { M1_STEP_PIN, M1_DIR_PIN, 0, true, 0, 0, "M1" };
Motor motor2 = { M2_STEP_PIN, M2_DIR_PIN, 0, true, 0, 0, "M2" };

// ===== Helpers =====

void flushInput() {
  delay(2);
  while (Serial.available()) Serial.read();
}

void serialPrint(const char* msg) {
  Serial.println(msg);
  flushInput();
}

// Queue a movement on a motor
void queueMove(Motor &m, bool dir, int steps) {
  // If direction changed, cancel old movement and start fresh
  if (dir != m.direction) {
    m.stepsRemaining = 0;
  }
  m.direction = dir;
  digitalWrite(m.dirPin, dir ? HIGH : LOW);
  delayMicroseconds(50);  // Let DIR settle (extra margin for CS-D508 opto)
  m.stepsRemaining += steps;  // Accumulate if same direction
  m.stepInterval = (unsigned long)(1000000.0 / STEP_SPEED);
  
  Serial.print(m.name);
  Serial.print(dir ? " CW " : " CCW ");
  Serial.print(steps);
  Serial.println(" steps");
  flushInput();
}

// Execute one step if it's time (non-blocking)
void updateMotor(Motor &m) {
  if (m.stepsRemaining <= 0) return;
  
  unsigned long now = micros();
  if (now - m.lastStepTime >= m.stepInterval) {
    digitalWrite(m.stepPin, HIGH);
    delayMicroseconds(3);
    digitalWrite(m.stepPin, LOW);
    m.lastStepTime = now;
    m.stepsRemaining--;
    
    if (m.stepsRemaining <= 0) {
      Serial.print(m.name);
      Serial.println(" DONE");
      flushInput();
    }
  }
}

// Stop a motor immediately
void stopMotor(Motor &m) {
  m.stepsRemaining = 0;
}

// ===== Setup =====

void setup() {
  Serial.begin(115200);
  
  // Motor 1 pins
  pinMode(M1_STEP_PIN, OUTPUT);
  pinMode(M1_DIR_PIN, OUTPUT);
  digitalWrite(M1_STEP_PIN, LOW);
  digitalWrite(M1_DIR_PIN, LOW);
  
  // Motor 2 pins
  pinMode(M2_STEP_PIN, OUTPUT);
  pinMode(M2_DIR_PIN, OUTPUT);
  digitalWrite(M2_STEP_PIN, LOW);
  digitalWrite(M2_DIR_PIN, LOW);
  
  // LED
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);
  
  delay(500);
  flushInput();
  
  serialPrint("=== DUAL MOTOR CONTROLLER ===");
  serialPrint("Motor 1: GPIO18/19 (Left/Right arrows)");
  serialPrint("Motor 2: GPIO16/17 (Up/Down arrows)");
  serialPrint("");
  serialPrint("Commands: R L U D 0 X");
  serialPrint("Motors locked. Awaiting commands...");
  serialPrint("READY");
  
  motor1.lastStepTime = micros();
  motor2.lastStepTime = micros();
}

// ===== Serial Command Processing =====

void processSerial() {
  if (!Serial.available()) return;
  
  char c = Serial.read();
  
  // Ignore control chars except ESC (for arrow key sequences)
  if (c < 32 && c != 27) return;
  
  // Handle escape sequences (arrow keys sent directly from terminal)
  if (c == 27) {
    delay(5);
    if (Serial.available()) {
      char c2 = Serial.read();
      if (c2 == '[' && Serial.available()) {
        char c3 = Serial.read();
        switch (c3) {
          case 'C': c = 'R'; break;  // Right arrow → Motor 1 CW
          case 'D': c = 'L'; break;  // Left arrow  → Motor 1 CCW
          case 'A': c = 'U'; break;  // Up arrow    → Motor 2 CW
          case 'B': c = 'D'; break;  // Down arrow  → Motor 2 CCW
          default: return;
        }
      } else return;
    } else return;
  }
  
  switch (c) {
    case 'R': case 'r':
      queueMove(motor1, true, STEPS_PER_PRESS);
      break;
      
    case 'L': case 'l':
      queueMove(motor1, false, STEPS_PER_PRESS);
      break;
      
    case 'U': case 'u':
      queueMove(motor2, true, STEPS_PER_PRESS);
      break;
      
    case 'D': case 'd':
      queueMove(motor2, false, STEPS_PER_PRESS);
      break;
      
    case '0':
      stopMotor(motor1);
      stopMotor(motor2);
      serialPrint(">>HALT ALL");
      break;
      
    case 'X': case 'x':
      stopMotor(motor1);
      stopMotor(motor2);
      serialPrint(">>EMERGENCY STOP");
      break;
      
    default:
      break;
  }
}

// ===== Main Loop =====

void loop() {
  processSerial();
  
  // Update both motors (non-blocking)
  updateMotor(motor1);
  updateMotor(motor2);
  
  // LED on when either motor is moving
  bool moving = (motor1.stepsRemaining > 0) || (motor2.stepsRemaining > 0);
  digitalWrite(LED_PIN, moving ? HIGH : LOW);
}
