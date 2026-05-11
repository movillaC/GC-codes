# Gemini API Security Implementation

## Overview
The Gemini API key is now handled **securely on the backend** and is never exposed to the frontend.

## Architecture

### Before (Vulnerable ❌)
- Frontend directly calls Gemini API
- API key embedded in browser JavaScript
- Key visible in network requests
- Key exposed in source code

### After (Secure ✅)
- Frontend calls `/api/gemini-generate` backend endpoint
- Backend calls Gemini API with the API key from environment variables
- API key stays on server only
- Browser never sees the API key

## Endpoints

### `POST /api/gemini-generate`
**Secure backend endpoint for Gemini calls**

**Request:**
```json
{
  "prompt": "Your prompt text here"
}
```

**Headers:**
- `Authorization: Bearer <firebase-token>` (required)
- `Content-Type: application/json`

**Response:**
```json
{
  "success": true,
  "text": "Generated response from Gemini..."
}
```

## Frontend Usage

### Ai.html (Chat Interface)
```javascript
const token = await auth.currentUser.getIdToken();
const response = await fetch('/api/gemini-generate', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer ' + token
  },
  body: JSON.stringify({ prompt: text })
});
const data = await response.json();
if (data.success) {
  console.log(data.text); // Use the response
}
```

### Profile.html (AI Suggestions)
```javascript
const response = await fetch('/api/gemini-generate', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer ' + token
  },
  body: JSON.stringify({ prompt: prompt })
});
const data = await response.json();
if (data.success) {
  // Display data.text with proper formatting
}
```

## Environment Variables

### Local Development (.env)
```
FLASK_ENV=development
SECRET_KEY=your-secret-key-here
GEMINI_API_KEY=AIzaSyAMKEgEMuBLTCrL1yMyqzOPB4InwvXSnTY
FIREBASE_CREDENTIALS_JSON={"type":"service_account",...}
```

### Render Deployment (Environment Variables)
**DO NOT commit your API key to git!**

1. Go to Render Dashboard
2. Select your service
3. Go to **Environment**
4. Add these variables:
   - `GEMINI_API_KEY`: Your Google Gemini API key
   - `FLASK_ENV`: `production`
   - `SECRET_KEY`: A strong random secret
   - `FIREBASE_CREDENTIALS_JSON`: Your Firebase service account JSON

## Security Checklist

- ✅ API key is in environment variables only (never in code)
- ✅ API key is never sent to browser
- ✅ API key is not logged in responses
- ✅ Endpoint requires Firebase authentication
- ✅ Endpoint validates user token before proceeding
- ✅ Request timeout set to 30 seconds (prevent hanging)
- ✅ Error messages don't expose sensitive info

## Deployment Steps (Render)

1. **Update environment variables** in Render dashboard
2. **Do NOT** include `.env` file in git
3. **Do NOT** hardcode API keys in HTML/JS
4. **Verify** that `GEMINI_API_KEY` env variable is set
5. **Test** the endpoint: `POST /api/gemini-generate` with auth token

## Testing

**Local test with curl:**
```bash
# Get a Firebase token first (from browser console)
TOKEN="your-firebase-token"

curl -X POST http://localhost:5000/api/gemini-generate \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"What is wellness?"}'
```

## Troubleshooting

### Error: "Gemini API not configured"
- Check that `GEMINI_API_KEY` is set in environment variables
- Verify it's not in git history (use `git log` to check)

### Error: "Invalid token"
- Token expired? Get a fresh one from Firebase
- Check that `verify_token()` function is working

### API calls failing
- Check Render logs: `render logs <service-name>`
- Verify API key is valid at https://console.cloud.google.com
- Check internet connectivity on Render

## Files Modified

1. **backend/student_server.py**
   - Added `import os` and `import requests`
   - Added `/api/gemini-generate` endpoint

2. **backend/templates/student/Ai.html**
   - Removed hardcoded API key
   - Updated to call backend endpoint

3. **backend/templates/student/Profile.html**
   - Removed hardcoded API key
   - Updated to call backend endpoint
   - Simplified response handling (no longer streaming)
