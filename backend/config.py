"""
Shared configuration for all Flask servers
"""
import os
import json
from datetime import timedelta

# ─── ENVIRONMENT ──────────────────────────────────────────────────────────
IS_PRODUCTION = os.environ.get('FLASK_ENV') == 'production'

# ─── FIREBASE CONFIG ──────────────────────────────────────────────────────
def get_firebase_credentials():
    """Get Firebase credentials from file or environment variable"""
    if IS_PRODUCTION:
        creds_json = os.environ.get('FIREBASE_CREDENTIALS_JSON')
        if creds_json:
            return json.loads(creds_json)
        else:
            raise ValueError("FIREBASE_CREDENTIALS_JSON not set in environment")
    else:
        return 'gcsw-cca5d-firebase-adminsdk-fbsvc-d23a6a3758.json'

FIREBASE_CREDENTIALS = get_firebase_credentials()

# ─── FLASK CONFIG ─────────────────────────────────────────────────────────
class BaseConfig:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    JSON_SORT_KEYS = False
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)

class StudentConfig(BaseConfig):
    HOST = '0.0.0.0' if IS_PRODUCTION else '127.0.0.1'
    PORT = int(os.environ.get('PORT', 5000))
    DEBUG = not IS_PRODUCTION

class AdminConfig(BaseConfig):
    HOST = '0.0.0.0' if IS_PRODUCTION else '127.0.0.1'
    PORT = int(os.environ.get('PORT', 5001))
    DEBUG = not IS_PRODUCTION

class ConsultantConfig(BaseConfig):
    HOST = '0.0.0.0' if IS_PRODUCTION else '127.0.0.1'
    PORT = int(os.environ.get('PORT', 5002))
    DEBUG = not IS_PRODUCTION