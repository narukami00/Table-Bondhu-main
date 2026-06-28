# Project Structure

## Directory Layout

```
Table-Bondhu/
├── .env                          # Secrets (git ignored)
├── .gitignore
├── requirements.txt              # Python dependencies
├── README.md
│
├── Arduino/                      # Arduino/ESP32 Code
│   ├── config.h                  # WiFi & Server config
│   ├── images/
│   │   ├── images.h              # Bitmap declarations
│   │   └── README.md             # Image organization guide
│   ├── utils/
│   │   ├── i2s_setup.h           # Microphone setup
│   │   ├── display.h             # Display functions
│   │   └── wifi.h                # WiFi utility
│   └── sketches/
│       ├── live_rec/             # Live streaming sketch
│       ├── gemini_button/        # Button + AI response
│       └── save_recording/       # Save before sending
│
├── Python/                       # Python Backend
│   ├── main.py                   # Entry point
│   ├── config/
│   │   ├── __init__.py
│   │   └── settings.py           # Load from .env
│   ├── server/
│   │   ├── __init__.py
│   │   ├── tcp_server.py         # Socket server
│   │   └── handlers.py           # Client handlers
│   ├── audio/
│   │   ├── __init__.py
│   │   ├── transcriber.py        # Google STT
│   │   └── processor.py          # Audio handling
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── gemini_client.py      # Gemini API
│   │   └── chat_memory.py        # History management
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── logger.py             # Logging setup
│   │   └── helpers.py            # Utility functions
│   └── recordings/               # Audio files (git ignored)
│
└── docs/
    ├── API.md                    # Protocol documentation
    ├── SETUP.md                  # Installation guide
    └── DEPLOYMENT.md             # Deployment instructions
```

## Module Organization

### Arduino
- **utils/**: Reusable components (I2S, Display, WiFi)
- **images/**: Bitmap data organized by type
- **sketches/**: Different project variants

### Python
- **config/**: Environment-based configuration
- **server/**: TCP server and connection handling
- **audio/**: Transcription and audio processing
- **llm/**: Gemini integration
- **utils/**: Logging and helpers
