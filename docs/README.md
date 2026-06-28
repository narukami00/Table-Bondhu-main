# Table-Bondhu: Embedded AI Assistant

Refactored modular architecture for ESP32-based voice assistant with Gemini AI backend.

## Quick Start

### Python Backend
```bash
# Install dependencies
pip install -r requirements.txt

# Run server
cd Python
python main.py
```

### Arduino
1. Update `Arduino/config.h` with your WiFi credentials
2. Choose a sketch:
   - `live_rec/` - Continuous audio streaming
   - `gemini_button/` - Button-triggered recording
   - `save_recording/` - Save before uploading
3. Upload to ESP32

## Project Structure
See [docs/STRUCTURE.md](docs/STRUCTURE.md) for full organization.

## Security
- API keys stored in `.env` (git ignored)
- WiFi credentials in `config.h`
- No hardcoded secrets in source code

## Key Features
- Modular Python architecture
- Reusable Arduino utilities
- Organized image assets
- TCP protocol for ESP32 communication
- Gemini AI integration
- Speech-to-text transcription

## Documentation
- [API Protocol](docs/API.md)
- [Structure](docs/STRUCTURE.md)
- [Setup Guide](SETUP.md)
