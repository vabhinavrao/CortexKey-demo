/*
 * CortexKey Neural Authentication System
 * ESP32 Firmware - EEG Acquisition & Mock Data Generator
 * 
 * Hardware:
 *   ESP32 DevKit V1
 *   BioAmp EXG Pill → GPIO34 (ADC1_CH6)
 *   Electrodes: Fp1, Fp2 (forehead), REF (mastoid)
 * 
 * Serial: 115200 baud
 * Sample Rate: 250 Hz (4ms per sample)
 * Output Format: timestamp,raw_adc,millivolts\n
 * 
 * Commands (via Serial):
 *   START_AUTH  → Begin authentication scan
 *   MOCK_AUTH   → Switch to authenticated mock data
 *   MOCK_IMP   → Switch to impostor mock data
 *   STOP        → Stop streaming
 * 
 * To switch from mock to real sensor, change USE_MOCK_DATA to false.
 */

// ============================================================
// CONFIG
// ============================================================
#define USE_MOCK_DATA    true   // ← Set to false when real sensor arrives
#define EEG_PIN          34     // GPIO34 (ADC1_CH6)
#define SAMPLE_RATE      250    // Hz
#define SAMPLE_INTERVAL  4000   // microseconds (1000000 / 250)
#define SERIAL_BAUD      115200
#define BUTTON_PIN       0      // BOOT button on most ESP32 boards

// Filter coefficients (2nd order IIR)
// 50Hz Notch filter (Q=30, fs=250)
#define NOTCH_B0  0.9694f
#define NOTCH_B1 -1.2727f
#define NOTCH_B2  0.9694f
#define NOTCH_A1 -1.2727f
#define NOTCH_A2  0.9388f

// Bandpass 5-30Hz (Butterworth 2nd order, fs=250)
#define BP_B0  0.1311f
#define BP_B1  0.0f
#define BP_B2 -0.1311f
#define BP_A1 -1.4894f
#define BP_A2  0.7378f

// ============================================================
// STATE
// ============================================================
enum Mode {
  MODE_IDLE,
  MODE_STREAMING,
  MODE_AUTH
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

// Filter state variables
float notch_x1 = 0, notch_x2 = 0, notch_y1 = 0, notch_y2 = 0;
float bp_x1 = 0, bp_x2 = 0, bp_y1 = 0, bp_y2 = 0;

// Button debounce
unsigned long lastButtonPress = 0;
#define DEBOUNCE_MS 300

// ============================================================
// MOCK DATA GENERATION
// ============================================================

/**
 * Generate realistic EEG for an "authenticated" user.
 * Strong Alpha (10Hz) + moderate Beta (20Hz) + low noise.
 * This mimics a relaxed, eyes-closed EEG with a clear Alpha peak.
 */
float generateAuthEEG(float t) {
  // Alpha rhythm (10Hz) — dominant in relaxed state
  float alpha = 2.5f * sin(2.0f * PI * 10.0f * t);
  
  // Beta rhythm (20Hz) — moderate cognitive activity
  float beta = 1.2f * sin(2.0f * PI * 20.0f * t);
  
  // Sub-harmonics for realism
  float theta = 0.6f * sin(2.0f * PI * 6.0f * t);
  
  // Biological noise
  float noise = 0.3f * (random(-100, 101) / 100.0f);
  
  // Slight amplitude modulation (breathing artifact ~0.3Hz)
  float modulation = 1.0f + 0.1f * sin(2.0f * PI * 0.3f * t);
  
  return (alpha + beta + theta) * modulation + noise;
}

/**
 * Generate noisy EEG for an "impostor" — no coherent frequency peaks.
 */
float generateImpostorEEG(float t) {
  // Mostly random noise
  float noise = 1.5f * (random(-100, 101) / 100.0f);
  
  // Very weak, inconsistent oscillations
  float weak_signal = 0.3f * sin(2.0f * PI * 7.3f * t + random(0, 628) / 100.0f);
  
  // Muscle artifact bursts
  float muscle = 0.0f;
  if (random(0, 100) < 5) {
    muscle = 2.0f * (random(-100, 101) / 100.0f);
  }
  
  return noise + weak_signal + muscle;
}

/**
 * Get a mock sample based on current mode.
 */
float getMockSample(float t) {
  if (mockType == MOCK_AUTHENTICATED) {
    return generateAuthEEG(t);
  } else {
    return generateImpostorEEG(t);
  }
}

// ============================================================
// REAL SENSOR READING
// ============================================================

/**
 * Read from the BioAmp EXG Pill sensor on GPIO34.
 * Returns value in millivolts.
 */
float readRealSensor() {
  int raw = analogRead(EEG_PIN);
  // ESP32 ADC: 12-bit (0-4095), 0-3.3V range
  float millivolts = (raw / 4095.0f) * 3300.0f;
  // Center around 0 (remove DC offset, assuming ~1650mV midpoint)
  millivolts -= 1650.0f;
  // Scale to typical EEG range (microvolts → millivolts display)
  return millivolts * 0.01f;  // Adjust gain as needed
}

// ============================================================
// SIGNAL PROCESSING (On-device)
// ============================================================

/**
 * Apply 50Hz notch filter (IIR biquad).
 */
float applyNotchFilter(float x) {
  float y = NOTCH_B0 * x + NOTCH_B1 * notch_x1 + NOTCH_B2 * notch_x2
            - NOTCH_A1 * notch_y1 - NOTCH_A2 * notch_y2;
  notch_x2 = notch_x1;
  notch_x1 = x;
  notch_y2 = notch_y1;
  notch_y1 = y;
  return y;
}

/**
 * Apply 5-30Hz bandpass filter (IIR biquad).
 */
float applyBandpassFilter(float x) {
  float y = BP_B0 * x + BP_B1 * bp_x1 + BP_B2 * bp_x2
            - BP_A1 * bp_y1 - BP_A2 * bp_y2;
  bp_x2 = bp_x1;
  bp_x1 = x;
  bp_y2 = bp_y1;
  bp_y1 = y;
  return y;
}

/**
 * Reset filter states (call when starting new scan).
 */
void resetFilters() {
  notch_x1 = notch_x2 = notch_y1 = notch_y2 = 0;
  bp_x1 = bp_x2 = bp_y1 = bp_y2 = 0;
}

// ============================================================
// SERIAL COMMAND HANDLER
// ============================================================

void handleSerialCommand() {
  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    cmd.toUpperCase();

    if (cmd == "START_AUTH") {
      currentMode = MODE_AUTH;
      sampleCount = 0;
      startTime = millis();
      resetFilters();
      Serial.println("CMD:AUTH_STARTED");
    }
    else if (cmd == "MOCK_AUTH") {
      mockType = MOCK_AUTHENTICATED;
      Serial.println("CMD:MOCK_AUTH_SET");
    }
    else if (cmd == "MOCK_IMP") {
      mockType = MOCK_IMPOSTOR;
      Serial.println("CMD:MOCK_IMP_SET");
    }
    else if (cmd == "STOP") {
      currentMode = MODE_IDLE;
      Serial.println("CMD:STOPPED");
    }
    else if (cmd == "START") {
      currentMode = MODE_STREAMING;
      sampleCount = 0;
      startTime = millis();
      resetFilters();
      Serial.println("CMD:STREAMING_STARTED");
    }
    else if (cmd == "STATUS") {
      Serial.print("CMD:STATUS:");
      Serial.print(currentMode == MODE_IDLE ? "IDLE" : 
                    currentMode == MODE_STREAMING ? "STREAMING" : "AUTH");
      Serial.print(",MOCK:");
      Serial.println(mockType == MOCK_AUTHENTICATED ? "AUTH" : "IMP");
    }
    else if (cmd == "PING") {
      Serial.println("CMD:PONG");
    }
  }
}

// ============================================================
// BUTTON HANDLER (Toggle mock mode)
// ============================================================

void handleButton() {
  if (digitalRead(BUTTON_PIN) == LOW) {
    if (millis() - lastButtonPress > DEBOUNCE_MS) {
      lastButtonPress = millis();
      // Toggle mock type
      if (mockType == MOCK_AUTHENTICATED) {
        mockType = MOCK_IMPOSTOR;
        Serial.println("CMD:BUTTON_MOCK_IMP");
      } else {
        mockType = MOCK_AUTHENTICATED;
        Serial.println("CMD:BUTTON_MOCK_AUTH");
      }
    }
  }
}

// ============================================================
// SETUP
// ============================================================

void setup() {
  Serial.begin(SERIAL_BAUD);
  while (!Serial) { delay(10); }

  // Configure ADC
  analogReadResolution(12);  // 12-bit ADC
  analogSetAttenuation(ADC_11db);  // Full 0-3.3V range
  pinMode(EEG_PIN, INPUT);
  
  // Button
  pinMode(BUTTON_PIN, INPUT_PULLUP);

  // Seed random for mock data
  randomSeed(analogRead(0) ^ micros());

  // Startup message
  Serial.println("CMD:CORTEXKEY_READY");
  Serial.println("CMD:VERSION:1.0");
  Serial.print("CMD:MODE:");
  Serial.println(USE_MOCK_DATA ? "MOCK" : "REAL_SENSOR");
  Serial.println("CMD:COMMANDS:START_AUTH,MOCK_AUTH,MOCK_IMP,STOP,START,STATUS,PING");

  startTime = millis();
  lastSampleMicros = micros();
}

// ============================================================
// MAIN LOOP
// ============================================================

void loop() {
  // Handle incoming commands
  handleSerialCommand();
  
  // Handle button press
  handleButton();

  // Only sample when in active mode
  if (currentMode == MODE_IDLE) {
    delay(10);  // Save power
    return;
  }

  // Precise timing at 250 Hz
  unsigned long now = micros();
  if (now - lastSampleMicros < SAMPLE_INTERVAL) {
    return;  // Not time yet
  }
  lastSampleMicros += SAMPLE_INTERVAL;

  // Calculate time in seconds
  float t = sampleCount / (float)SAMPLE_RATE;
  
  // Get sample
  float sample;
  int rawADC;
  
  if (USE_MOCK_DATA) {
    sample = getMockSample(t);
    // Convert to fake ADC value for consistency
    rawADC = (int)((sample + 3.3f) / 6.6f * 4095.0f);
    rawADC = constrain(rawADC, 0, 4095);
  } else {
    rawADC = analogRead(EEG_PIN);
    sample = (rawADC / 4095.0f) * 3300.0f;
    sample -= 1650.0f;  // Remove DC offset
    sample *= 0.01f;    // Scale to reasonable range
  }

  // Apply filters
  float filtered = applyNotchFilter(sample);
  filtered = applyBandpassFilter(filtered);

  // Output: timestamp_ms, raw_adc, millivolts
  unsigned long timestamp = millis() - startTime;
  Serial.print(timestamp);
  Serial.print(',');
  Serial.print(rawADC);
  Serial.print(',');
  Serial.println(filtered, 4);

  sampleCount++;

  // In AUTH mode, stop after 6 seconds (1500 samples)
  if (currentMode == MODE_AUTH && sampleCount >= 1500) {
    currentMode = MODE_IDLE;
    Serial.println("CMD:AUTH_SCAN_COMPLETE");
  }
}
