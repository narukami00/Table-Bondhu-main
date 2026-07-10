# TCP Protocol Reference

Communication between ESP32 and Python server over TCP port 8080. The connection is bidirectional with a mixed binary/text protocol: the ESP32 sends raw PCM audio with embedded text commands, while the server sends pure text commands.

## Connection Lifecycle

1. ESP32 connects to server on port 8080
2. Server calibrates noise baseline from 1s of incoming audio
3. Server sends `UI_STATE:IDLE\n`
4. Server begins keyword detection loop (background)
5. Server fetches and sends weather data
6. Bidirectional streaming begins
7. Connection times out after 30s of no data from ESP32

## ESP32 → Server Commands

Commands are embedded as UTF-8 text within the binary PCM audio stream. The server uses marker-based extraction to separate commands from audio bytes.

### `CMD:WOKE\n`
**Purpose**: Button press detected — recording started
**When**: User presses D14 button
**Server response**: Enters recording mode, allocates speech buffer

### `___END___\n`
**Purpose**: Button released — recording stopped, process speech
**When**: User releases D14 button
**Server response**: Transcribes audio, queries LLM, sends response

### `LDR:value\n`
**Purpose**: Light sensor reading for adaptive theming
**When**: Every 5 seconds when LDR is read (audio ADC temporarily disabled)
**Server response**: Logged, not acted upon

### `TIMER_DONE\n`
**Purpose**: Timer countdown completed on ESP32
**When**: `timerSecondsLeft` reaches 0
**Server response**: Triggers alarm sound on laptop, sets `active_alarm_active`

### `PIR:MOTION\n`
**Purpose**: PIR sensor detected motion
**When**: Rising edge on GPIO 27 (debounced, 5s cooldown)
**Server response**: Logged to console for calibration

### `PIR:WAKE\n`
**Purpose**: ESP32 woke from sleeping state due to motion
**When**: PIR detects motion while in `STATE_SLEEPING`
**Server response**: Logged to console

## Server → ESP32 Commands

All commands are newline-terminated UTF-8 text strings.

### State Commands

#### `UI_STATE:IDLE\n`
Returns ESP32 to clock display.

#### `UI_STATE:LISTENING\n`
ESP32 shows listening overlay with animated dots.

#### `UI_STATE:THINKING\n`
ESP32 shows thinking animation.

#### `UI_STATE:GREETING\n`
Triggers waving animation that returns to clock (skips listening state).

#### `CMD:START_SLEEP\n`
Forces the ESP32 to drop into sleep mode immediately.

### Display Commands

#### `UI_MSG:text\n`
Display text in speech bubble. Triggers speaking animation.

#### `UI_LIST:item1|item2|item3\n`
Display paginated list (used for reminder list). Pipe `|` separator converted to newlines.

#### `DURATION:seconds\n`
Override the speaking animation duration. Float in seconds.

### Timer Commands

#### `TIMER_START:seconds\n`
Start countdown timer.

#### `TIMER_PAUSE\n` / `TIMER_RESUME\n` / `TIMER_CANCEL\n` / `TIMER_STOP\n`
Timer control commands.

### Weather Command

#### `WEATHER:temp:DESCRIPTION:iconIndex\n`
Weather data for clock face. iconIndex: 0=sun, 1=cloud, 2=rain, 3=snow.

### Alarm Command

#### `UI_ALARM:taskName\n`
Trigger alarm state. Auto-dismisses after 30s.

### Sleep Summary Command

#### `UI_SLEEP_SUMMARY:type:duration:movements:avg_noise:avg_ldr:quality\n`
Pushes sleep session summary data to the client and displays the summary page.
- `type`: "Sleep" or "Nap"
- `duration`: Float (hours, e.g., "8.2")
- `movements`: Int (movement count)
- `avg_noise`: Float (average audio RMS)
- `avg_ldr`: Int (average light level)
- `quality`: "Good", "Fair", or "Poor"

## Audio Streaming

Raw PCM audio is continuously streamed from ESP32 to server. Format:
- **Sample rate**: 16kHz
- **Bit depth**: 16-bit signed integer (int16)
- **Channels**: Mono
- **Byte order**: Little-endian

### ESP32 Processing
1. I2S reads 16-bit samples from ADC (GPIO32)
2. Raw samples accumulated in 512-sample buffer
3. DC offset removed via exponential filter: `y = x - x_prev + 0.995 * y_prev`
4. Gain applied: `scaled = filtered * 12.0`
5. Clamped to int16 range, sent in 1024-byte TCP chunks

### Server Processing
1. TCP data accumulated in `recv_buffer`
2. Text commands extracted by marker scanning (not `\n` splitting)
3. Partial command markers at buffer tail handled safely
4. Audio bytes fed to keyword buffer and speech buffer
5. On recording end: resampled to 16kHz, converted to float32, fed to Parakeet ASR

## Thread Safety

- `send_lock` (global): Prevents interleaved `sendall()` from multiple threads
- `chat_lock` (global): Protects `LocalChatSession.history` across concurrent LLM requests
- `db_lock` (global): Protects `reminders.json` file reads/writes
- `TCP_NODELAY`: Enabled on socket to avoid Nagle algorithm delays
