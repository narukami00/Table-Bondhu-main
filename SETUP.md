# Environment Setup Guide

## Security Notice ⚠️
**Never commit the `.env` file to version control.** It contains sensitive API keys and is already added to `.gitignore`.

## Setup Instructions

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment Variables
The project uses a `.env` file to store sensitive credentials:

**File: `.env`**
```
GEMINI_API_KEY=your_api_key_here
```

**Do not share or commit this file!**

### 3. How It Works
- All Python scripts now load variables from the `.env` file using `python-dotenv`
- The API key is loaded at runtime via: `os.getenv("GEMINI_API_KEY")`
- If the key is missing, the script will raise a clear error message

### 4. Protected Files
- ✅ `check_api.py` - Updated
- ✅ `gemini_LLM.py` - Updated
- ✅ `gemini_LLM_Button.py` - Updated
- ✅ `gemini_LLM2.py` - Updated

All files now safely load the API key from the `.env` file instead of hardcoding it.
