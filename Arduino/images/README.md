// Image organization guide
// Separate large bitmap arrays into different files to improve compile time

// In images.h:
//   - Declare extern pointers to bitmap arrays
//   - Keep definitions clean

// In separate .cpp files (one per image set):
//   - face_bitmap.cpp - Face expressions
//   - icon_bitmap.cpp - UI icons
//   - emoji_bitmap.cpp - Emoji graphics

// This prevents recompiling all images when changing one
// and improves IDE performance

// Example structure:
// face_happy    - Happy face for positive responses
// face_sad      - Sad face for errors
// face_neutral  - Neutral expression
// icon_speaker  - Speaker icon
// icon_mic      - Microphone icon
// icon_wifi     - WiFi status icon
