# GCSW App - Render Deployment Guide

## Deployment Steps

### 1. Prepare Firebase Credentials
- Open `backend/gcsw-cca5d-firebase-adminsdk-fbsvc-d23a6a3758.json`
- Copy the entire JSON content (including the curly braces)

### 2. Create Render Account & Project
1. Go to [render.com](https://render.com)
2. Sign up or log in
3. Create a new Web Service

### 3. Deploy Each Server

**For each of the three servers (Student, Admin, Consultant):**

#### Option A: Using render.yaml (Recommended)
1. Connect your GitHub repository
2. Render will automatically detect `render.yaml` and deploy all three services

#### Option B: Manual Setup
1. Click "Create New" → "Web Service"
2. Connect GitHub repository
3. Fill in the form:
   - **Name**: `gcsw-student-server` (or admin/consultant)
   - **Runtime**: Python 3.11
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python backend/student_server.py`
   - **Plan**: Free (or Starter for production)

### 4. Set Environment Variables

For **each service**, go to Settings → Environment:

```
SECRET_KEY = your-random-secret-key-here
FIREBASE_CREDENTIALS_JSON = [paste the entire JSON from step 1]
PORT = 8000 (or 8001, 8002 for other services)
FLASK_ENV = production
```

### 5. Deploy
Click "Deploy" and wait for each service to build and start.

## Accessing Your App

After deployment, you'll get URLs like:
- Student: `https://gcsw-student-server.onrender.com`
- Admin: `https://gcsw-admin-server.onrender.com`
- Consultant: `https://gcsw-consultant-server.onrender.com`

## Update Frontend URLs

In your HTML files (templates), update any hardcoded `127.0.0.1` references to your new Render URLs:

```javascript
// Before (local):
fetch('http://127.0.0.1:5000/api/endpoint')

// After (Render):
fetch('https://gcsw-student-server.onrender.com/api/endpoint')
```

## Troubleshooting

- **Firebase errors**: Verify `FIREBASE_CREDENTIALS_JSON` is valid JSON
- **Port issues**: Make sure PORT environment variable is set
- **Module not found**: Check that `requirements.txt` includes all packages
- **Logs**: Check Render dashboard → Logs tab for errors

## Important Notes

- **Free tier limits**: May sleep after 15 min of inactivity
- **Database**: Firebase Firestore is in the cloud, so it persists across deployments
- **CORS**: May need to configure CORS in Flask for cross-domain requests
- **SSL**: Render provides free SSL certificates
