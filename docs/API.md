# API Protocol Documentation

## TCP Protocol between ESP32 and Python Server

### Port: 8080

### Message Format

#### Audio Upload (ESP32 → Python)
```
[___START___] + [raw audio bytes] + [___END___]
```

- `___START___` marker indicates recording start
- Raw audio data follows (16-bit, mono, 16kHz)
- `___END___` marker indicates recording end

#### Response (Python → ESP32)
```
[AI response text]\n
```

Example:
```
The temperature is 25 degrees Celsius\n
```

### Workflow

1. **ESP32** connects to Python server on `192.168.0.101:8080`
2. **ESP32** records audio when button pressed or continuously
3. **ESP32** sends `___START___` + audio data + `___END___`
4. **Python Server**:
   - Receives audio data
   - Saves to WAV file
   - Transcribes using Google Speech Recognition
   - Sends to Gemini API
   - Gets AI response
5. **Python** sends response back to ESP32
6. **ESP32** displays response on TFT screen

### Configuration

Update in `config.h`:
```cpp
const char* WIFI_SSID = "Your_SSID";
const char* WIFI_PASSWORD = "Your_Password";
const char* SERVER_IP = "192.168.0.101";
const int SERVER_PORT = 8080;
```
