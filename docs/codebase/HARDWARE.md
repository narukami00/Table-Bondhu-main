# Table-Bondhu Hardware & Circuit Architecture (`HARDWARE.md`)

This document provides an exhaustive, low-level description of the Table-Bondhu physical hardware, GPIO pinouts, electrical circuit designs, sensor characteristics, and step-by-step schematics. It includes relevant firmware configuration snippets and answers every conceivable teacher or examiner viva question.

---

## 1. Absolute Pinout & Wiring Registry

Below is the definitive pinout registry of the Table-Bondhu embedded node. All GPIO numbers refer to the standard ESP32 30-pin / 38-pin DevKit V1 configurations.

| Component | Pin Label on Component | Standard ESP32 GPIO Pin | Signal Type | Electrical Characteristic |
| :--- | :--- | :--- | :--- | :--- |
| **ST7735 TFT Screen** | VCC | 5V (or VIN) | Power | 5V Input to Screen Regulator |
| | GND | GND | Power | Ground |
| | CS (Chip Select) | GPIO 5 | Output | Active-Low SPI Device Select |
| | RESET | GPIO 4 | Output | Active-Low Hardware Reset |
| | DC (Data/Command) | GPIO 2 | Output | High = Data, Low = Command |
| | SDI / MOSI | GPIO 23 | Output | SPI Master Out Slave In |
| | SCK / SCLK | GPIO 18 | Output | SPI Serial Clock |
| | LED (Backlight) | 3.3V (or via 220Ω to 3.3V) | Power | High = Screen Backlight On |
| **Tactile Push Button**| Pin A (Signal) | GPIO 14 (D14) | Input | Internal `INPUT_PULLUP` (Active Low) |
| | Pin B (Ground) | GND | Power | Ground |
| **Active Buzzer** | Positive (+) | GPIO 13 (D13) | Output | Active-High Digital Drive |
| | Negative (-) | GND | Power | Ground |
| **LDR (Light Sensor)** | Pin A (Power) | 3.3V | Power | 3.3V Reference |
| | Pin B (Signal OUT) | GPIO 34 (D34) | Input (Analog) | ADC1_CH6 (Voltage Divider output) |
| **PIR Motion Sensor** | VCC | 5V | Power | 5V Sensor VCC Input |
| | GND | GND | Power | Ground |
| | OUT | GPIO 27 (D27) | Input (Digital)| Digital High (3.3V) on motion |
| **ADC I2S Microphone** | VCC | 3.3V | Power | 3.3V Reference |
| | GND | GND | Power | Ground |
| | OUT (Analog Signal) | GPIO 32 (D32) | Input (Analog) | ADC1_CH4 (I2S DMA Analog Input) |

---

## 2. Comprehensive Circuit Diagram & Schematics Guide

To draw a professional, textbook-level schematic for your viva or project report, follow these layout rules:

### A. LDR Voltage Divider Circuit (Analog Sensing)
*   **The Problem:** An LDR is a variable resistor whose resistance decreases as light increases. A microcontroller cannot measure resistance directly; it can only measure voltage.
*   **The Solution (Voltage Divider):** Connect a $10\text{k}\Omega$ fixed resistor in series with the LDR between $3.3\text{V}$ and $\text{GND}$ to create a voltage divider.
*   **Schematic Layout:**
    1. Draw a line from the ESP32 **3.3V** pin to one pin of the LDR.
    2. Draw a line from the other pin of the LDR to ESP32 **GPIO 34 (D34)**.
    3. At the intersection of the LDR pin and GPIO 34, draw a branch connection to one pin of a $10\text{k}\Omega$ carbon-film resistor.
    4. Connect the other pin of the $10\text{k}\Omega$ resistor directly to **GND**.
*   **Mathematical Expression:**
    $$V_{\text{out}} = 3.3\text{V} \times \left( \frac{10\text{k}\Omega}{R_{\text{LDR}} + 10\text{k}\Omega} \right)$$
    *   *In Pitch Blackness:* $R_{\text{LDR}}$ is extremely high (up to $1\text{M}\Omega$). Thus, $V_{\text{out}}$ drops close to $0\text{V}$ (Analog read reads near `0`).
    *   *Under Bright Light:* $R_{\text{LDR}}$ drops significantly (down to a few hundred ohms). Thus, $V_{\text{out}}$ rises close to $3.3\text{V}$ (Analog read reads near `4095`).

### B. Tactile Push Button Circuit (Active-Low)
*   **The Problem:** A floating input pin picks up ambient electromagnetic noise, causing random switches between HIGH and LOW states.
*   **The Solution (Internal Pull-Up):** We wire the button directly between the GPIO and Ground. We enable the ESP32’s internal $45\text{k}\Omega$ pull-up resistor to pull the pin HIGH by default when the button is open.
*   **Schematic Layout:**
    1. Draw a line from ESP32 **GPIO 14** to one pin of the tactile button.
    2. Connect the opposite diagonal pin of the button directly to **GND**.
    3. Draw the button symbol as open by default.
    4. When pressed, the switch closes, creating a direct path to Ground ($0\text{V}$). The firmware reads this as a `LOW` state.

### C. PIR Motion Sensor Connections
*   **Schematic Layout:**
    1. Draw a line from the ESP32 **5V (VIN)** pin to the **VCC** pin of the HC-SR501 PIR sensor. (PIR sensors need 5V to power their onboard 3.3V regulators).
    2. Connect the PIR **GND** pin to the ESP32 **GND** pin.
    3. Connect the PIR **OUT** pin directly to ESP32 **GPIO 27**. This pin outputs a clean 3.3V digital signal when motion is detected, requiring no external pull-up or pull-down.

### D. Active Buzzer Circuit
*   **Schematic Layout:**
    1. Connect the Positive (+) pin of the active buzzer directly to ESP32 **GPIO 13**.
    2. Connect the Negative (-) pin of the buzzer directly to **GND**.
    *   *Note:* The ESP32 GPIO can supply up to 40mA. An active buzzer typically draws 10–20mA, meaning it can be driven directly by the GPIO without an external NPN transistor driver (like BC547).

### E. I2S Analog Microphone Circuit
*   **Schematic Layout:**
    1. Connect microphone **VCC** to ESP32 **3.3V**.
    2. Connect microphone **GND** to ESP32 **GND**.
    3. Connect microphone **OUT** (Analog) to ESP32 **GPIO 32 (ADC1_CH4)**.

---

## 3. Relevant Firmware Code Snippets

Here is the exact pin configuration and initialization code from [gemini_LLM_btn.ino](file:///F:/__KUET%20Assignments/IOT/Table-Bondhu-main/gemini_LLM_btn/gemini_LLM_btn.ino):

```cpp
// --- PIN CONFIGURATION (Lines 24 - 28) ---
#define BUTTON_PIN 14 // Tactile Button (GND + D14)
#define BOOT_BTN 0    // Built-in BOOT button for text pagination
#define LDR_PIN 34    // ADC1_CH6 - Light Dependent Resistor
#define BUZZER_PIN 13 // Active Buzzer (HIGH = sound)
#define PIR_PIN 27    // PIR Motion Sensor (digital OUT)

// --- HARDWARE CONFIGURATION IN SETUP() (Lines 1568 - 1584) ---
void setup() {
  // ...
  // Enable internal pull-up for the tactile push button
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  
  // Enable internal pull-up for the pagination BOOT button
  pinMode(BOOT_BTN, INPUT_PULLUP);
  
  // Configure the buzzer pin as digital output
  pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(BUZZER_PIN, LOW); // Turn off buzzer initially
  
  // Configure PIR motion sensor pin as input
  pinMode(PIR_PIN, INPUT);
  
  // Setup LDR analog pin
  pinMode(LDR_PIN, INPUT);
  // ...
}
```

---

## 4. Comprehensive Teacher Viva Q&A

### Q1: Why is the Tactile Button configured with `INPUT_PULLUP` instead of an external resistor?
**Answer:** Microcontrollers have built-in internal pull-up resistors (typically $45\text{k}\Omega$ on the ESP32) that can be enabled in software. Using `INPUT_PULLUP` simplifies hardware assembly, reduces component count, eliminates the need for external pull-up resistors on a breadboard, and prevents floating pins.

### Q2: What is a floating pin, and why is it dangerous in embedded systems?
**Answer:** A floating pin is an input pin not connected to a defined voltage source (neither VCC nor GND). High impedance causes it to act like a tiny antenna, catching electromagnetic noise from surroundings. This causes the pin to rapidly alternate between HIGH and LOW, leading to random triggers, UI glitches, and power consumption spikes.

### Q3: Why is the LDR connected to GPIO 34? Can we use GPIO 12 or 15 instead?
**Answer:** The LDR outputs an analog voltage, which requires an Analog-to-Digital Converter (ADC). GPIO 34 maps to **ADC1_CH6**. 
We cannot use pins associated with ADC2 (such as GPIO 12 or 15) while Wi-Fi is active. The ESP32's Wi-Fi driver uses the ADC2 controller exclusively. Attempting to call `analogRead()` on an ADC2 pin while Wi-Fi is running returns errors or incorrect values. Therefore, all analog sensors (LDR and Mic OUT) must connect to ADC1 (GPIO 30–39).

### Q4: What is the bit resolution of the ESP32 ADC, and what does it mean?
**Answer:** The ESP32 has a **12-bit ADC resolution** by default. This divides the input voltage range (typically 0V to 3.3V) into $2^{12} = 4096$ steps.
*   $0\text{V}$ analog input corresponds to a digital value of `0`.
*   $3.3\text{V}$ analog input corresponds to a digital value of `4095`.
*   The voltage step size is $\frac{3.3\text{V}}{4095} \approx 0.8\text{mV}$ per step.

### Q5: Why does the HC-SR501 PIR sensor need 5V (VIN) if the ESP32 logic is 3.3V?
**Answer:** The HC-SR501 PIR sensor has an onboard 78M05 voltage regulator that drops the input voltage down to 3.3V to power its BISS0001 control chip. This regulator needs an input voltage of at least 5V to work correctly. Feeding it 3.3V directly makes the sensor unstable or unresponsive. Conveniently, its digital output pin uses a 3.3V logic level, which makes it safe to connect directly to the ESP32 input pin (GPIO 27) without a logic level shifter.

### Q6: What is the difference between an Active Buzzer and a Passive Buzzer? Which one is used here?
**Answer:**
*   **Active Buzzer (Used Here):** Has an internal oscillating circuit. Applying a DC voltage (HIGH) makes it sound at a fixed frequency (typically 2.5kHz).
*   **Passive Buzzer:** Lacks an internal oscillator. It acts like a speaker, requiring an external AC signal (PWM wave) to oscillate and produce sound.
*   *Note:* In our firmware, we drive the active buzzer using standard GPIO states (`digitalWrite(BUZZER_PIN, HIGH)`), but we also support frequency generation via PWM using `ledcWriteTone` to produce varying alarm tones.

### Q7: If the PIR sensor outputs 3.3V when motion is detected, why does the code have a debouncing mechanism?
**Answer:** PIR sensors use a pyroelectric sensor element that detects changes in infrared radiation. When a person moves, the analog output spikes. However, around the edges of the detection field, the signal oscillates, causing the digital OUT pin to flicker between HIGH and LOW (chatter). We implement a software debounce check: the raw PIR pin must stay HIGH for at least `200ms` continuously to confirm a motion event, filtering out transient electrical or RF noise spikes.

---

## 5. Evidence Paths
*   Pin configuration declarations: [gemini_LLM_btn.ino#L24-L28](file:///F:/__KUET%20Assignments/IOT/Table-Bondhu-main/gemini_LLM_btn/gemini_LLM_btn.ino#L24-L28)
*   Pin mode initializations: [gemini_LLM_btn.ino#L1568-L1584](file:///F:/__KUET%20Assignments/IOT/Table-Bondhu-main/gemini_LLM_btn/gemini_LLM_btn.ino#L1568-L1584)
*   LDR analog read execution: [gemini_LLM_btn.ino#L816](file:///F:/__KUET%20Assignments/IOT/Table-Bondhu-main/gemini_LLM_btn/gemini_LLM_btn.ino#L816)
*   PIR digital read execution: [gemini_LLM_btn.ino#L1680](file:///F:/__KUET%20Assignments/IOT/Table-Bondhu-main/gemini_LLM_btn/gemini_LLM_btn.ino#L1680)
