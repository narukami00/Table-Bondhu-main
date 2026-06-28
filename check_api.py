import json
import urllib.request

LM_STUDIO_MODELS_URL = "http://127.0.0.1:1234/v1/models"

print("Searching for loaded models on LM Studio local server...\n")
try:
    req = urllib.request.Request(LM_STUDIO_MODELS_URL)
    with urllib.request.urlopen(req) as response:
        res = json.loads(response.read().decode("utf-8"))
        print("Successfully connected to LM Studio local server!")
        print("Loaded Models:")
        models = res.get("data", [])
        if models:
            for model in models:
                print(f"- {model.get('id')}")
        else:
            print("No models loaded. Please load a model in LM Studio.")
except Exception as e:
    print(f"Error connecting to LM Studio: {e}")
    print("Please make sure LM Studio is running and local server is started on port 1234.")