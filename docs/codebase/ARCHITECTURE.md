# Table-Bondhu Architecture Map (`ARCHITECTURE.md`)

This document records the high-level architecture, design patterns, software layers, and bidirectional data flows used in the Table-Bondhu system.

---

## 1. High-Level Architecture Design

Table-Bondhu uses a **Dual-Node Client-Server Architecture** designed to offload computationally heavy tasks (speech recognition, LLM processing, and speech synthesis) from a low-power microcontroller to a local laptop or PC:

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                 EMBEDDED CLIENT (ESP32)                         │
│                                                                                 │
│  Sensing Layer      ◄─── (LDR, PIR, Mic, Buttons)                               │
│       │                                                                         │
│       ▼                                                                         │
│  State Controller   ◄─── Gathers data and runs local UI state machines          │
│       │                                                                         │
│       ▼                                                                         │
│  Double Buffer      ◄─── Builds visual layouts in internal RAM                  │
│       │                                                                         │
│       ▼                                                                         │
│  TFT SPI Output     ◄─── Sends completed frames to the physical screen          │
└───────┬─────────────────────────────────────────────────────────────────────────┘
        │
        │ Bidirectional TCP Connection (Port 8080)
        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                COMPANION BACKEND (PC)                           │
│                                                                                 │
│  Socket Gateway     ◄─── Handles TCP connection, separating commands and audio  │
│       │                                                                         │
│       ▼                                                                         │
│  ASR Pipeline       ◄─── Translates raw audio streams to text transcriptions    │
│       │                                                                         │
│       ▼                                                                         │
│  LLM Engine         ◄─── Generates assistant replies and parses structured commands │
│       │                                                                         │
│       ▼                                                                         │
│  TTS Voice Engine   ◄─── Synthesizes responses and modulates Pikachu effects    │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Detailed Technical Components

To keep the documentation organized, detailed technical details are separated into dedicated files:

1.  **Physical Component Integration ([HARDWARE.md](file:///F:/__KUET%20Assignments/IOT/Table-Bondhu-main/docs/codebase/HARDWARE.md)):** Pinout registries, series voltage divider circuits, button wiring, and active-low input behaviors.
2.  **Framing Protocols & API specification ([COMMUNICATION.md](file:///F:/__KUET%20Assignments/IOT/Table-Bondhu-main/docs/codebase/COMMUNICATION.md)):** Mixed binary/ASCII parsing, Nagle’s algorithm parameters, REST API specifications, and UDP discovery beacons.
3.  **Local Speech Processing & Synthesis ([AI_ENGINES.md](file:///F:/__KUET%20Assignments/IOT/Table-Bondhu-main/docs/codebase/AI_ENGINES.md)):** Parakeet conformer transcribing, system prompt guardrails, Piper synthesis, and Pikachu voice modulation.
4.  **UI State Machine & Double Buffer rendering ([UI_ANIMATIONS.md](file:///F:/__KUET%20Assignments/IOT/Table-Bondhu-main/docs/codebase/UI_ANIMATIONS.md)):** RAM buffer configurations, dynamic sprite sizing, text word-wrapping, page pagination, and blink/talk loop frames.
5.  **Reminder persistence & Countdown timer engine ([ALARM_TIMER_SYSTEM.md](file:///F:/__KUET%20Assignments/IOT/Table-Bondhu-main/docs/codebase/ALARM_TIMER_SYSTEM.md)):** Thread-safety file locks (`db_lock`), natural time parsing, relative time math, and local countdown timer states.
6.  **Sleep state logic & Pre-Wake check ([SLEEP_SYSTEM.md](file:///F:/__KUET%20Assignments/IOT/Table-Bondhu-main/docs/codebase/SLEEP_SYSTEM.md)):** NTP clock gating, PIR history arrays, room RMS noise monitoring, pre-wake wave verification, and quality categorization rules.
7.  **Flutter Companion App ([ANDROID_APP.md](file:///F:/__KUET%20Assignments/IOT/Table-Bondhu-main/docs/codebase/ANDROID_APP.md)):** Wi-Fi setup bridges, discovery caching, low-latency push-to-talk recorders, persistent night overlays, and custom vector charting.

---

## 3. Core Design Patterns

The system implements several common design patterns:

*   **State Pattern (ESP32):** The firmware uses a state variable (`currentState`) to manage its behavior. Actions like button presses, sensor readings, and screen updates are handled differently depending on the active state.
*   **Observer Pattern (Android Discovery):** The mobile app binds to a raw UDP broadcast socket, listening for incoming beacons. When a beacon is received, it extracts the server's IP address and automatically updates the active API binding.
*   **Producer-Consumer Pattern (TCP Server):** The server's TCP socket handler acts as a producer, continuously reading bytes from the network card and appending them to a shared buffer. The ASR and command execution pipelines act as consumers, pulling data from the buffer to transcribe speech and run actions.

---

## 4. Evidence Paths
*   Dual-node communication: [docs/TEACHER_QA_GUIDE.md#L7-L23](file:///F:/__KUET%20Assignments/IOT/Table-Bondhu-main/docs/TEACHER_QA_GUIDE.md#L7-L23)
*   TCP client connection: [gemini_LLM_btn.ino#L1831-L1848](file:///F:/__KUET%20Assignments/IOT/Table-Bondhu-main/gemini_LLM_btn/gemini_LLM_btn.ino#L1831-L1848)
*   REST server initialization: [agentic_companion.py#L2060-L2064](file:///F:/__KUET%20Assignments/IOT/Table-Bondhu-main/agentic_companion.py#L2060-L2064)
*   Flutter app entry point: [table_bondhu_app/lib/main.dart#L13-L36](file:///F:/__KUET%20Assignments/IOT/Table-Bondhu-main/table_bondhu_app/lib/main.dart#L13-L36)
