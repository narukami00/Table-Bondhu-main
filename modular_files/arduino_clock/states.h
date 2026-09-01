// states.h - State Enum Definitions for Table-Bondhu Clock

#ifndef STATES_H
#define STATES_H

enum AppState {
  STATE_CLOCK,            // Normal digital clock display mode
  STATE_IDLE,             // Awaiting commands, idle avatar state
  STATE_LISTENING,        // Streaming mic bytes to server
  STATE_THINKING,         // LLM generating text reply
  STATE_SPEAKING,         // Synthesizing speech playback
  STATE_ALARM,            // Buzzer buzzing, flash alarm state
  STATE_TIMER,            // Focus timer active countdown
  STATE_TIMER_PAUSED,     // Focus timer paused state
  STATE_TIMER_FINISHED,   // Focus timer completed, buzzer active
  STATE_SLEEPING,         // Screen off/dark sleep monitoring state
  STATE_SLEEPING_PREWAKE, // Movement detected, verifying wake state
  STATE_REMINDERS,        // Displaying reminder list items
  STATE_WAVING_INTRO      // Waving intro animation trigger state
};

#endif // STATES_H
