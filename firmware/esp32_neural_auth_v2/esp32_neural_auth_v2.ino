/*
 * CortexKey ESP32 Neural Authentication Firmware v2.0
 * with Button-Triggered Testing
 * 
 * Hardware:
 *   ESP32 DevKit V1
 *   BioAmp EXG Pill → GPIO34 (ADC1_CH6)
 *   Button 1 (Valid User) → GPIO18 (pull-up enabled)
 *   Button 2 (Invalid User) → GPIO19 (pull-up enabled)
 * 
 * Serial: 115200 baud
 * Sample Rate: 250 Hz (4ms per sample)
 * Output Format: DATA,timestamp_ms,sample1,sample2...\n
 * 
 * Button Functions:
 *   GPIO18 Press: Start VALID user authentication test
 *   GPIO19 Press: Start INVALID user authentication test
 *   Long Press (2s): Stop and return to idle
 * 
 * Commands (via Serial):
 *   START        → Begin streaming
 *   STOP         → Stop streaming
 *   MOCK_AUTH    → Switch to authenticated mock data
 *   MOCK_IMP     → Switch to impostor mock data
 *   STATUS       → Get current status
 */

// ============================================================
// CONFIGURATION
// ============================================================
#define USE_MOCK_DATA    true   // Set to false when real sensor connected
#define EEG_PIN          34     // GPIO34 (ADC1_CH6)
#define BUTTON_VALID     18     // GPIO18 - Valid user button
#define BUTTON_INVALID   19     // GPIO19 - Invalid user button
#define LED_PIN          2      // Built-in LED

#define SAMPLE_RATE      250    // Hz
#define SAMPLE_INTERVAL  4000   // microseconds (1000000 / 250)
#define SERIAL_BAUD      115200

#define BUTTON_DEBOUNCE  50     // ms
#define LONG_PRESS_TIME  2000   // ms for long press

// ============================================================
// STATE
// ============================================================
enum Mode {
  MODE_IDLE,
  MODE_STREAMING,
  MODE_AUTH_VALID,    // Button-triggered valid user test
  MODE_AUTH_INVALID   // Button-triggered invalid user test
};

enum MockType {
  MOCK_AUTHENTICATED,
  MOCK_IMPOSTOR
};

Mode currentMode = MODE_IDLE;
MockType mockType = MOCK_AUTHENTICATED;

unsigned long sampleCount = 0;
unsigned long startTime = 0;
unsigned long lastSampleMicros = 0;

// Button state tracking
struct ButtonState {
  uint8_t pin;
  bool lastState;
  bool currentState;
  unsigned long pressTime;
  unsigned long releaseTime;
  bool longPressTriggered;
};

ButtonState btnValid = {BUTTON_VALID, HIGH, HIGH, 0, 0, false};
ButtonState btnInvalid = {BUTTON_INVALID, HIGH, HIGH, 0, 0, false};

// ============================================================
// MOCK DATA GENERATION (5X SLOWER FOR VISIBILITY)
// ============================================================

/**
 * Generate realistic SLOW EEG for an "authenticated" user.
 * Frequencies divided by 5 for better visualization on screen.
 * Strong Alpha (2Hz visible) + moderate Beta (4Hz visible) + low noise.
 */
float generateAuthEEG(float t) {
  // Alpha rhythm (10Hz → 2Hz for visibility)
  float alpha = 25.0f * sin(2.0f * PI * 2.0f * t);
  
  // Beta rhythm (20Hz → 4Hz for visibility)
  float beta = 12.0f * sin(2.0f * PI * 4.0f * t);
  
  // Theta (6Hz → 1.2Hz for visibility)
  float theta = 6.0f * sin(2.0f * PI * 1.2f * t);
  
  // Delta (2.5Hz → 0.5Hz for visibility)
  float delta = 4.0f * sin(2.0f * PI * 0.5f * t);
  
  // Biological noise (low)
  float noise = 3.0f * (random(-100, 101) / 100.0f);
  
  // Slow amplitude modulation (breathing artifact ~0.06Hz)
  float modulation = 1.0f + 0.15f * sin(2.0f * PI * 0.06f * t);
  
  // Occasional eye blink artifact
  float blink = 0.0f;
  if (((int)(t * 1000)) % 5000 < 300) {  // Every 5 seconds, 300ms duration
    float blinkT = fmod(t * 1000, 5000) / 300.0f;
    blink = 50.0f * exp(-pow((blinkT - 0.2f), 2) / 0.02f);
  }
  
  return (alpha + beta + theta + delta) * modulation + noise + blink;
}

/**
 * Generate SLOW noisy EEG for an "impostor" user.
 * High noise, weak/shifted alpha, muscle artifacts.
 */
float generateImpostorEEG(float t) {
  // Shifted/weak alpha (different frequency → 1.5Hz visible)
  float alpha = 8.0f * sin(2.0f * PI * 1.5f * t + random(0, 100) / 50.0f);
  
  // High beta/stress (22Hz → 4.4Hz visible)
  float beta = 15.0f * sin(2.0f * PI * 4.4f * t + random(0, 100) / 50.0f);
  
  // Weak theta
  float theta = 4.0f * sin(2.0f * PI * 1.1f * t);
  
  // High noise
  float noise = 12.0f * (random(-100, 101) / 100.0f);
  float whiteNoise = 8.0f * (random(-100, 101) / 100.0f);
  
  // Frequent muscle artifacts (30-60Hz → 6-12Hz visible)
  float muscle = 0.0f;
  if (random(0, 1000) < 50) {  // 5% chance per sample
    muscle = 30.0f * sin(2.0f * PI * 9.0f * t);  // 45Hz → 9Hz visible
  }
  
  // Large random spikes (movement)
  float spike = 0.0f;
  if (random(0, 1000) < 10) {  // 1% chance
    spike = 40.0f * (random(-100, 101) / 100.0f);
  }
  
  return alpha + beta + theta + noise + whiteNoise + muscle + spike;
}

/**
 * Read EEG from ADC (real sensor) or generate mock data
 */
float readEEG() {
  float value;
  float timeSeconds = (millis() - startTime) / 1000.0f;
  
  if (USE_MOCK_DATA) {
    // Generate appropriate mock data based on mode
    if (currentMode == MODE_AUTH_VALID || 
        (currentMode == MODE_STREAMING && mockType == MOCK_AUTHENTICATED)) {
      value = generateAuthEEG(timeSeconds);
    } else {
      value = generateImpostorEEG(timeSeconds);
    }
  } else {
    // Real sensor: Read from ADC
    int rawADC = analogRead(EEG_PIN);
    // Convert to microvolts (assuming 3.3V ref, 12-bit ADC, gain = 1000x)
    value = ((rawADC / 4095.0f) * 3.3f * 1000.0f) - 1650.0f;  // Center around 0
  }
  
  return value;
}

// ============================================================
// BUTTON HANDLING
// ============================================================

void updateButton(ButtonState &btn) {
  btn.currentState = digitalRead(btn.pin);
  unsigned long now = millis();
  
  // Detect press (HIGH → LOW with debounce)
  if (btn.lastState == HIGH && btn.currentState == LOW) {
    if (now - btn.releaseTime > BUTTON_DEBOUNCE) {
      btn.pressTime = now;
      btn.longPressTriggered = false;
    }
  }
  
  // Detect release (LOW → HIGH)
  if (btn.lastState == LOW && btn.currentState == HIGH) {
    btn.releaseTime = now;
  }
  
  btn.lastState = btn.currentState;
}

bool isButtonPressed(ButtonState &btn) {
  return (btn.currentState == LOW);
}

bool isShortPress(ButtonState &btn) {
  unsigned long now = millis();
  if (btn.lastState == LOW && btn.currentState == HIGH) {
    unsigned long pressDuration = btn.releaseTime - btn.pressTime;
    if (pressDuration > BUTTON_DEBOUNCE && pressDuration < LONG_PRESS_TIME) {
      return true;
    }
  }
  return false;
}

bool isLongPress(ButtonState &btn) {
  unsigned long now = millis();
  if (btn.currentState == LOW && !btn.longPressTriggered) {
    if (now - btn.pressTime > LONG_PRESS_TIME) {
      btn.longPressTriggered = true;
      return true;
    }
  }
  return false;
}

// ============================================================
// COMMAND PROCESSING
// ============================================================

void processCommand(String cmd) {
  cmd.trim();
  cmd.toUpperCase();
  
  if (cmd == "START") {
    currentMode = MODE_STREAMING;
    mockType = MOCK_AUTHENTICATED;
    sampleCount = 0;
    startTime = millis();
    lastSampleMicros = micros();
    Serial.println("STATUS:Started streaming (authenticated mode)");
    
  } else if (cmd == "STOP") {
    currentMode = MODE_IDLE;
    Serial.println("STATUS:Stopped");
    
  } else if (cmd == "MOCK_AUTH") {
    mockType = MOCK_AUTHENTICATED;
    Serial.println("STATUS:Switched to authenticated mock data");
    
  } else if (cmd == "MOCK_IMP") {
    mockType = MOCK_IMPOSTOR;
    Serial.println("STATUS:Switched to impostor mock data");
    
  } else if (cmd == "STATUS") {
    Serial.print("STATUS:");
    Serial.print("Mode=");
    switch(currentMode) {
      case MODE_IDLE: Serial.print("IDLE"); break;
      case MODE_STREAMING: Serial.print("STREAMING"); break;
      case MODE_AUTH_VALID: Serial.print("AUTH_VALID"); break;
      case MODE_AUTH_INVALID: Serial.print("AUTH_INVALID"); break;
    }
    Serial.print(",MockType=");
    Serial.print(mockType == MOCK_AUTHENTICATED ? "AUTH" : "IMP");
    Serial.print(",Samples=");
    Serial.print(sampleCount);
    Serial.print(",Uptime=");
    Serial.print(millis() / 1000);
    Serial.println("s");
    
  } else {
    Serial.println("ERROR:Unknown command");
  }
}

// ============================================================
// SETUP
// ============================================================

void setup() {
  Serial.begin(SERIAL_BAUD);
  while (!Serial) { delay(10); }
  
  // Configure pins
  pinMode(EEG_PIN, INPUT);
  pinMode(BUTTON_VALID, INPUT_PULLUP);
  pinMode(BUTTON_INVALID, INPUT_PULLUP);
  pinMode(LED_PIN, OUTPUT);
  
  // Configure ADC
  analogReadResolution(12);
  analogSetAttenuation(ADC_11db);  // 0-3.3V range
  
  // Seed random number generator
  randomSeed(analogRead(0) + analogRead(EEG_PIN));
  
  delay(500);
  
  // Startup banner
  Serial.println("\n========================================");
  Serial.println("  CortexKey ESP32 Authentication v2.0");
  Serial.println("  with Button-Triggered Testing");
  Serial.println("========================================");
  Serial.println("Hardware:");
  Serial.println("  GPIO34: EEG Input (ADC)");
  Serial.println("  GPIO18: Valid User Button");
  Serial.println("  GPIO19: Invalid User Button");
  Serial.println("");
  Serial.print("Mock Mode: ");
  Serial.println(USE_MOCK_DATA ? "ENABLED" : "DISABLED");
  Serial.print("Sample Rate: ");
  Serial.print(SAMPLE_RATE);
  Serial.println(" Hz");
  Serial.println("");
  Serial.println("Button Controls:");
  Serial.println("  Press GPIO18 → Start VALID user test");
  Serial.println("  Press GPIO19 → Start INVALID user test");
  Serial.println("  Hold 2s → Stop and return to idle");
  Serial.println("");
  Serial.println("Serial Commands:");
  Serial.println("  START, STOP, MOCK_AUTH, MOCK_IMP, STATUS");
  Serial.println("========================================");
  Serial.println("CORTEXKEY_READY");
  Serial.println("");
  
  digitalWrite(LED_PIN, LOW);
}

// ============================================================
// MAIN LOOP
// ============================================================

void loop() {
  unsigned long currentMicros = micros();
  
  // Update button states
  updateButton(btnValid);
  updateButton(btnInvalid);
  
  // ===== Button Event Handling =====
  
  // GPIO18: Valid User Button (short press)
  if (isShortPress(btnValid)) {
    if (currentMode == MODE_IDLE || currentMode == MODE_STREAMING) {
      currentMode = MODE_AUTH_VALID;
      mockType = MOCK_AUTHENTICATED;
      sampleCount = 0;
      startTime = millis();
      lastSampleMicros = currentMicros;
      Serial.println("\n========== VALID USER TEST STARTED ==========");
      Serial.println("STATUS:Button 18 pressed - Starting valid user authentication");
      digitalWrite(LED_PIN, HIGH);  // LED on during test
    }
  }
  
  // GPIO19: Invalid User Button (short press)
  if (isShortPress(btnInvalid)) {
    if (currentMode == MODE_IDLE || currentMode == MODE_STREAMING) {
      currentMode = MODE_AUTH_INVALID;
      mockType = MOCK_IMPOSTOR;
      sampleCount = 0;
      startTime = millis();
      lastSampleMicros = currentMicros;
      Serial.println("\n========== INVALID USER TEST STARTED ==========");
      Serial.println("STATUS:Button 19 pressed - Starting invalid user authentication");
      digitalWrite(LED_PIN, HIGH);  // LED on during test
    }
  }
  
  // Long press either button: Stop
  if (isLongPress(btnValid) || isLongPress(btnInvalid)) {
    if (currentMode != MODE_IDLE) {
      currentMode = MODE_IDLE;
      Serial.println("\n========== TEST STOPPED ==========");
      Serial.println("STATUS:Long press detected - Returned to idle");
      digitalWrite(LED_PIN, LOW);  // LED off
    }
  }
  
  // ===== Serial Command Processing =====
  if (Serial.available()) {
    String command = Serial.readStringUntil('\n');
    processCommand(command);
  }
  
  // ===== EEG Sampling =====
  if (currentMode != MODE_IDLE) {
    // Check if it's time for next sample (250 Hz = 4000 µs interval)
    if (currentMicros - lastSampleMicros >= SAMPLE_INTERVAL) {
      lastSampleMicros += SAMPLE_INTERVAL;
      
      // Read EEG sample
      float eegValue = readEEG();
      
      // Send data over serial
      unsigned long timestamp = millis() - startTime;
      Serial.print("DATA,");
      Serial.print(timestamp);
      Serial.print(",");
      Serial.println(eegValue, 3);  // 3 decimal places
      
      sampleCount++;
      
      // Blink LED to show activity
      if (sampleCount % 250 == 0) {  // Every second
        digitalWrite(LED_PIN, !digitalRead(LED_PIN));
      }
      
      // Auto-stop after 10 seconds for button-triggered tests
      if ((currentMode == MODE_AUTH_VALID || currentMode == MODE_AUTH_INVALID) && 
          (millis() - startTime > 10000)) {
        Serial.println("\n========== TEST COMPLETE (10s) ==========");
        Serial.print("STATUS:Completed ");
        Serial.print(currentMode == MODE_AUTH_VALID ? "VALID" : "INVALID");
        Serial.print(" user test - ");
        Serial.print(sampleCount);
        Serial.println(" samples collected");
        currentMode = MODE_IDLE;
        digitalWrite(LED_PIN, LOW);
      }
    }
  }
  
  // Small delay to prevent watchdog issues
  yield();
}
