# Setup Guide

## Prerequisites

### Software
- **Python 3.8+** — with pip
- **Arduino IDE 2.x** — with ESP32 board support
- **LM Studio** — for local LLM inference (https://lmstudio.ai)
- **TFT_eSPI library** — install via Arduino Library Manager

### Hardware
- ESP32 Dev Board (any variant)
- 128x160 TFT Display (ST7735/ST7789, SPI connection)
- Tactile push button
- Active buzzer
- Light Dependent Resistor (LDR)
- PIR motion sensor (HC-SR501 or similar)
- Jumper wires, breadboard

## Step 1: Python Server Setup

```bash
cd Table-Bondhu-main
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

### Dependencies

| Package | Purpose |
|---------|---------|
| `python-dotenv` | Load `.env` file for configuration |
| `onnx-asr` | Parakeet TDT 0.6B speech recognition |
| `numpy` | Audio resampling and signal processing |
| `sherpa-onnx` | VITS offline text-to-speech |
| `gTTS` | Google Text-to-Speech (fallback) |
| `pydub` | Audio format conversion and pitch shifting |

### Parakeet Model Setup

The Parakeet ASR model is loaded from a hardcoded path. Update the path in `agentic_companion.py` line 131:

```python
asr_model = onnx_asr.load_model(
    'nemo-conformer-tdt',
    path=r'YOUR_MODEL_PATH_HERE',
    quantization='int8'
)
```

### TTS Model

The VITS TTS model ships in `models/vits-piper-en_US-amy-low/`. No download needed.

## Step 2: LM Studio Setup

1. Install LM Studio from https://lmstudio.ai
2. Load `qwen2.5-coder-1.5b-instruct` model
3. Start local server on port 1234
4. Verify: `python check_api.py`

## Step 3: ESP32 Firmware Setup

### Arduino IDE Configuration

1. Install ESP32 board support:
   - File → Preferences → Board Manager URLs: `https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json`
   - Tools → Board → Board Manager → Install "esp32"

2. Install TFT_eSPI library:
   - Tools → Manage Libraries → Search "TFT_eSPI" → Install

3. Configure TFT_eSPI for your display in `User_Setup.h`

4. Board settings:
   - Tools → Board → ESP32 Dev Module
   - Tools → Partition Scheme → Huge APP
   - Tools → Upload Speed → 921600

### WiFi Configuration

Edit `gemini_LLM_btn/config.h`:

```cpp
const char* WIFI_SSID = "YourWiFiName";
const char* WIFI_PASSWORD = "YourWiFiPassword";
const char* SERVER_IP = "192.168.x.x";  // Your laptop's IP
const int SERVER_PORT = 8080;
```

### Hardware Wiring

| Component | ESP32 Pin | Notes |
|-----------|-----------|-------|
| TFT Display | SPI (GPIO 5, 18, 19, 23, etc.) | Configured in TFT_eSPI |
| Push Button | D14 (GPIO 14) | INPUT_PULLUP, to GND |
| BOOT Button | D0 (GPIO 0) | Built-in, text pagination |
| Active Buzzer | D13 (GPIO 13) | HIGH = sound |
| LDR | D34 (GPIO 34) | ADC1_CH6, with 10K resistor |
| PIR Sensor | D27 (GPIO 27) | Digital OUT, VCC→5V, GND→GND |
| Microphone | D32 (GPIO 32) | ADC1_CH4, I2S input |

## Step 4: Upload and Test

1. Start LM Studio with model loaded
2. Run Python server: `python agentic_companion.py`
3. Upload firmware via Arduino IDE
4. Open Serial Monitor (115200 baud)
5. Press D14 and speak!

## Troubleshooting

### Server won't start
- Ensure LM Studio is running on port 1234
- Check no other process uses port 8080

### ESP32 can't connect
- Verify server IP in `config.h`
- Both devices must be on same network
- Check firewall isn't blocking port 8080

### No audio / garbled speech
- Verify microphone wiring to GPIO 32
- Check I2S configuration
- PIR sensor may cause power issues — try disconnecting PIR VCC to test

### TFT display not working
- Verify SPI wiring and TFT_eSPI User_Setup.h
- Try `tft.setRotation(2)`

### PIR keeps triggering
- Turn sensitivity potentiometer counter-clockwise (reduce sensitivity)
- Turn time delay potentiometer to minimum (~3s)
- Mount dome horizontally, away from heat sources
