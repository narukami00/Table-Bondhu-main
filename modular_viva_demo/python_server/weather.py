# weather.py - Weather Data Collector

import json
import urllib.request
import config

def get_weather():
    """Fetch current outdoor conditions for KUET Campus, Khulna, Bangladesh via Open-Meteo REST API."""
    try:
        url = "https://api.open-meteo.com/v1/forecast?latitude=22.8956&longitude=89.5011&current_weather=true"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
            current = data.get("current_weather", {})
            temp = round(current.get("temperature", 25))
            code = current.get("weathercode", 0)
            
            # Map Open-Meteo WMO Codes to Display Avatars
            if code == 0:
                desc, icon_idx = "SUNNY", 0
            elif code in [1, 2, 3, 45, 48]:
                desc, icon_idx = "CLOUDY", 1
            elif code in [71, 72, 73, 75, 77, 85, 86]:
                desc, icon_idx = "SNOWY", 3
            else:
                desc, icon_idx = "RAINY", 2
                
            return temp, desc, icon_idx
    except Exception as e:
        print(f"[Weather Error] API connection failed: {e}")
        return None, None, None


def fetch_and_send_weather(conn):
    """Sends current temperature and weather icon indices to the physical ESP32 device."""
    temp, desc, icon_idx = get_weather()
    if temp is not None:
        try:
            with config.send_lock:
                conn.sendall(f"WEATHER:{temp}:{desc}:{icon_idx}\n".encode())
            print(f"[Weather] Sent current conditions: {temp}°C, {desc}")
        except Exception as e:
            print(f"[Weather Error] Failed to send socket: {e}")
