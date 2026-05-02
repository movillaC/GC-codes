"""
Shared database module for Firebase initialization and utilities.
Used by all three Flask servers.
"""
import firebase_admin
from firebase_admin import credentials, firestore, auth as firebase_auth
from datetime import datetime, timedelta, timezone
from config import FIREBASE_CREDENTIALS

# ─── FIREBASE INITIALIZATION ──────────────────────────────────────────────
def init_firebase():
    """Initialize Firebase Admin SDK (singleton — called once per process)"""
    if not firebase_admin._apps:
        if isinstance(FIREBASE_CREDENTIALS, dict):
            cred = credentials.Certificate(FIREBASE_CREDENTIALS)
        else:
            cred = credentials.Certificate(FIREBASE_CREDENTIALS)
        firebase_admin.initialize_app(cred)
    return firestore.client()

# ─── LAZY SINGLETON ───────────────────────────────────────────────────────
_db = None

def get_db():
    """Return the Firestore client, initialising Firebase on first call."""
    global _db
    if _db is None:
        _db = init_firebase()
    return _db

# ─── AUTH HELPERS ─────────────────────────────────────────────────────────

def verify_token(request, allowed_roles=None):
    """
    Verify a Firebase ID token from the Authorization header.

    Returns: (uid, decoded_token, role)
    Raises:  Exception on invalid token or unauthorised role.
    """
    try:
        auth_header = request.headers.get('Authorization', '')
        token = auth_header.replace('Bearer ', '').strip()
        if not token:
            raise Exception('No authorization token provided')

        decoded = firebase_auth.verify_id_token(token)
        uid = decoded['uid']
        user_role = get_user_role(uid)

        if allowed_roles and user_role not in allowed_roles:
            raise Exception(
                f'Role "{user_role}" is not authorised for this endpoint'
            )

        return uid, decoded, user_role

    except firebase_admin.exceptions.FirebaseError as e:
        raise Exception(f'Firebase token error: {str(e)}')
    except Exception as e:
        raise Exception(f'Token verification failed: {str(e)}')


def get_user_role(uid):
    """Return the role stored in Firestore for *uid*, defaulting to 'student'."""
    db = get_db()
    doc = db.collection('users').document(uid).get()
    if doc.exists:
        return doc.to_dict().get('role', 'student')
    return 'student'


def user_exists(uid):
    """Return True if a Firestore user document exists for *uid*."""
    db = get_db()
    return db.collection('users').document(uid).get().exists


def create_user(uid, email, role, name=''):
    """Create a new user document in Firestore."""
    db = get_db()
    now = datetime.now(timezone.utc)
    db.collection('users').document(uid).set({
        'uid': uid,
        'email': email,
        'role': role,
        'name': name,
        'created_at': now,
        'updated_at': now,
    })

# ─── DATE HELPERS ─────────────────────────────────────────────────────────

def today_start():
    """Return midnight (UTC) of the current day as a timezone-aware datetime."""
    now = datetime.now(timezone.utc)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def week_start():
    """Return midnight (UTC) of the most recent Monday."""
    now = datetime.now(timezone.utc)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return today - timedelta(days=today.weekday())