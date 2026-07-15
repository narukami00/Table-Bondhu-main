# Table-Bondhu Companion Android App Architecture (`ANDROID_APP.md`)

This document provides a low-level, technical breakdown of the Flutter application, Wi-Fi provisioning bridge, UDP network discovery, push-to-talk mic drivers, and custom vector graphing engines used in the Table-Bondhu companion app.

---

## 1. Page Structure & Navigation

The Android app is built using Flutter and structured around a single-page navigation layout managed by `MainNavigationScreen`.

```
                    ┌──────────────────────────────┐
                    │     MainNavigationScreen     │
                    └──────────────┬───────────────┘
                                   │
         ┌──────────────────┬──────┴───────────┬──────────────────┐
         ▼                  ▼                  ▼                  ▼
┌─────────────────┐┌─────────────────┐┌─────────────────┐┌─────────────────┐
│ ConnectionTab   ││     ChatTab     ││  RemindersTab   ││    SleepTab     │
│ Server binding  ││ Push-to-Talk    ││ Add/delete list ││ History, Window │
└─────────────────┘└─────────────────┘└─────────────────┘└─────────────────┘
```

*   **Security Gating:** The app checks the connection to the server REST API. If the server is offline, navigation is locked, keeping the user on the **ConnectionTab** until a connection is established.

---

## 2. Wi-Fi Provisioning Bridge (AP Mode Setup)

If the ESP32 cannot connect to your Wi-Fi or needs reconfiguring:

```
 ┌─────────────┐       AP Connection        ┌─────────────┐
 │ Phone App   │ ─────────────────────────► │ ESP32 AP    │
 └──────┬──────┘                            └──────┬──────┘
        │                                          │
        │ HTTP POST /setup                         │ Writes SSID/PASS to NVS,
        │ (SSID, Password, Laptop IP)              │ Restarts and connects
        ▼                                          ▼
```

1.  **ESP32 Access Point:** Holding the **BOOT** button (GPIO 0) during startup forces the ESP32 into Access Point (AP) mode. It creates an open Wi-Fi network named `Table-Bondhu-Config` and starts a web server on `192.168.4.1`.
2.  **App Provisioning Form:** The user connects their phone to the `Table-Bondhu-Config` Wi-Fi network, opens the app, enters the target Wi-Fi name, password, and laptop IP address, and taps **Provision**.
3.  **HTTP Handshake:** The app sends an HTTP POST request to the ESP32 setup endpoint:

```dart
// --- Provisioning payload (main.dart: Lines 360 - 378) ---
final response = await http.post(
  Uri.parse('http://192.168.4.1/setup'),
  headers: {'Content-Type': 'application/json'},
  body: json.encode({
    'ssid': ssidController.text.trim(),
    'pass': passController.text.trim(),
    'server': serverIpController.text.trim(),
  }),
).timeout(const Duration(seconds: 8));
```

4.  **Save to NVS:** The ESP32 parses this JSON payload, saves the credentials to Non-Volatile Storage (NVS) flash memory, sends a success confirmation back to the app, and restarts to connect to the new Wi-Fi network.

---

## 3. Auto-Discovery & Persistent Server Binding

To make connection easy, the app uses a background UDP discovery system:

1.  **UDP Broadcasts:** The Python server broadcasts UDP discovery packets containing its IP address on port `9999` every 5 seconds.
2.  **UDP Socket Listener:** The Flutter app runs a background UDP socket listener that catches these broadcast packets:

```dart
// --- Listen for Discovery Packets (main.dart: Lines 295 - 310) ---
RawDatagramSocket.bind(InternetAddress.anyIPv4, 9999).then((RawDatagramSocket socket) {
  socket.listen((RawDatagramEvent event) {
    if (event == RawDatagramEvent.read) {
      Datagram? dg = socket.receive();
      if (dg != null) {
        String msg = utf8.decode(dg.data).strip();
        if (msg.startsWith("TABLE_BONDHU_SERVER:")) {
          String discoveredIp = msg.split(":")[1];
          _bindServerIp(discoveredIp); // Save discovered IP to cache
        }
      }
    }
  });
});
```

3.  **Persistent Cache:** The discovered IP is saved to `saved_server_ip.txt` in the phone's internal storage. On next launch, the app reads this file to connect automatically without needing a discovery scan.
4.  **Ping Loop:** A background timer pings the server REST API (`GET /api/ping`) every 4 seconds to verify the connection.

---

## 4. Push-to-Talk Voice Interface

The voice chat interface uses a touch-down/touch-up listener to support push-to-talk:

```dart
// --- Push-to-Talk Interface (main.dart: Lines 645 - 670) ---
Listener(
  onPointerDown: (details) => _startVoiceRecording(), // Finger down -> start recording
  onPointerUp: (details) => _stopAndSendVoice(),      // Finger up -> stop and send
  child: CircleAvatar(
    radius: 40,
    backgroundColor: _isRecording ? Colors.red : Color(0xFFFEE000),
    child: Icon(Icons.mic, size: 40, color: Colors.black),
  ),
)
```

### Audio Pipeline:
1.  **Direct Event Listener:** We use a raw `Listener` widget instead of a `GestureDetector`. Standard gesture detectors introduce a 500ms delay to distinguish between short taps and long presses, while `Listener` captures finger contact instantly.
2.  **Audio Capture:** The app records mono audio at 16kHz PCM, saving it to a local `.wav` file using the `record` package.
3.  **Accidental Tap Filter:** If the recording duration is less than **800ms**, the app deletes the recording, displays a notification (*"Hold to talk, release to send"*), and cancels the upload.
4.  **Base64 Encoder:** If the recording is valid, the app reads the `.wav` file, converts the raw bytes to a base64 string, and uploads it to the server `/api/voice_chat` endpoint.

---

## 5. Custom Vector Graphing Engine

To avoid adding bulky graphing libraries, the **Sleep Diagnostics** screen uses Flutter's built-in `CustomPainter` to render smooth vector graphs.

### A. Sleep Duration Trend Graph (`SleepDurationChartPainter`)
*   This draws a smooth line graph representing sleep durations over recent sessions.
*   It calculates scaling factors based on the maximum sleep duration in your history, draws horizontal grid lines, plots coordinate offsets for each session, and connects the points using cubic Bezier curves (`path.cubicTo`) to create a smooth, curved line.

```dart
// --- Vector Curve Generation (main.dart: Lines 2872 - 2898) ---
final path = Path()..moveTo(points.first.dx, points.first.dy);
for (int i = 1; i < points.length; i++) {
  final p0 = points[i - 1];
  final p1 = points[i];
  final controlX = p0.dx + (p1.dx - p0.dx) / 2; // Compute midpoint
  path.cubicTo(controlX, p0.dy, controlX, p1.dy, p1.dx, p1.dy);
}
canvas.drawPath(path, paintLine);
```

### B. Sleep Quality Ratio Chart (`SleepQualityPiePainter`)
*   Renders a circular ring segmented by colors representing the ratios of Good (Green), Fair (Orange), and Poor (Red) sleep sessions in your history.
*   It converts ratio values into radians ($2\pi \times \text{ratio}$) and draws arcs using `canvas.drawArc` to build the segmented ring.

---

## 6. Comprehensive Teacher Viva Q&A

### Q1: Why did you choose raw `Listener` instead of standard `GestureDetector` for the push-to-talk button?
**Answer:** Flutter's `GestureDetector` has a built-in delay (typically 300–500ms) used to distinguish between a tap, a double tap, and a long press. 
For a walkie-talkie style push-to-talk button, this delay makes the app feel unresponsive, often cutting off the start of the user's speech. A raw `Listener` intercepts touch events (`onPointerDown` and `onPointerUp`) directly at the operating system level, starting and stopping recording instantly without delay.

### Q2: Why does the app convert audio files to Base64 instead of uploading the raw binary file?
**Answer:** Uploading raw binary files over HTTP requires multipart/form-data encoding, which has high boundary parsing overhead.
Converting the audio file to **Base64** encodes the binary data into a clean ASCII string. This allows us to send the audio inside a standard JSON payload (`{"audio": "base64_string..."}`), which simplifies parsing on the server and makes it easy to add metadata (such as sample rate or duration) to the request body.

### Q3: How does the app save the discovered server IP address so it persists when the app is closed?
**Answer:** The app uses the `path_provider` package to find the device's application documents directory. When a server IP is discovered via UDP, the app writes the IP string to a file named `saved_server_ip.txt` in this directory. 
On boot, the app checks if this file exists. If it does, the app reads the saved IP and attempts to connect, bypassing the need for a UDP scan.

### Q4: How do the custom painters scale charts dynamically for different screen sizes?
**Answer:** The `paint(Canvas canvas, Size size)` method provides a `size` parameter containing the width and height of the parent widget.
Instead of using fixed pixel coordinates, we calculate drawing points relative to this size (e.g. `double stepX = size.width / (count - 1)`). This ensures the charts scale and render correctly on any screen size or orientation.

---

## 7. Evidence Paths
*   Main navigation gating: [main.dart#L40-L105](file:///F:/__KUET%20Assignments/IOT/Table-Bondhu-main/table_bondhu_app/lib/main.dart#L40-L105)
*   Wi-Fi provisioning post route: [main.dart#L360-L380](file:///F:/__KUET%20Assignments/IOT/Table-Bondhu-main/table_bondhu_app/lib/main.dart#L360-L380)
*   UDP Auto-Discovery listener: [main.dart#L295-L315](file:///F:/__KUET%20Assignments/IOT/Table-Bondhu-main/table_bondhu_app/lib/main.dart#L295-L315)
*   Push-to-Talk UI implementation: [main.dart#L645-L670](file:///F:/__KUET%20Assignments/IOT/Table-Bondhu-main/table_bondhu_app/lib/main.dart#L645-L670)
*   Sleep Analytics Custom Painters: [main.dart#L2848-L2990](file:///F:/__KUET%20Assignments/IOT/Table-Bondhu-main/table_bondhu_app/lib/main.dart#L2848-L2990)
