// WiFi & Server Configuration for Arduino/ESP32
// Update these values with your network credentials

#ifndef CONFIG_H
#define CONFIG_H

// WiFi SSID and Password
const char* WIFI_SSID = "Rafsan's S21";
const char* WIFI_PASSWORD = "12345678";

// Server Configuration
// NOTE: Make sure to update SERVER_IP with your laptop's new IP address once connected to the hotspot!
const char* SERVER_IP = "10.12.93.20"; // Update with current laptop IP
const int SERVER_PORT = 8080;

// Alternative WiFi Configuration (uncomment to use)
// const char* WIFI_SSID = "SSH_E_518";
// const char* WIFI_PASSWORD = "49082623";
// const char* SERVER_IP = "192.168.0.38";

#endif // CONFIG_H
