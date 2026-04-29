"""
Shared database module for Firebase initialization and utilities
This module is used by all three Flask servers
"""
import firebase_admin
from firebase_admin import credentials, firestore, auth as firebase_auth
from datetime import datetime, timedelta
from config import FIREBASE_CREDENTIALS

# ─── FIREBASE INITIALIZATION ──────────────────────────────────────────────
def init_firebase():
    """Initialize Firebase Admin SDK (called once per application)"""
    if not firebase_admin._apps:
        cred = credentials.Certificate(FIREBASE_CREDENTIALS)
        firebase_admin.initialize_app(cred)
    return firestore.client()

# ─── LAZY INITIALIZATION ──────────────────────────────────────────────────
_db = None

def get_db():
    """Get Firestore database instance (singleton pattern)"""
    global _db
    if _db is None:
        _db = init_firebase()
    return _db

# ─── HELPER FUNCTIONS ─────────────────────────────────────────────────────

def verify_token(request, allowed_roles=None):
    """
    Verify Firebase ID token from Authorization header.
    
    Args:
        request: Flask request object
        allowed_roles: List of allowed roles. If None, any role is allowed.
    
    Returns:
        Tuple of (uid, decoded_token)
    
    Raises:
        Exception if token is invalid or user role is not allowed
    """
    try:
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        if not token:
            raise Exception('No authorization token provided')
        
        decoded = firebase_auth.verify_id_token(token)
        uid = decoded['uid']
        
        # Verify user exists and get their role
        user_role = get_user_role(uid)
        
        # Check if role is allowed
        if allowed_roles and user_role not in allowed_roles:
            raise Exception(f'User role "{user_role}" is not authorized for this server')
        
        return uid, decoded, user_role
    except Exception as e:
        raise Exception(f'Token verification failed: {str(e)}')

def get_user_role(uid):
    """Get user role from Firestore"""
    db = get_db()
    doc = db.collection('users').document(uid).get()
    if doc.exists:
        return doc.to_dict().get('role', 'student')
    return 'student'

def user_exists(uid):
    """Check if user exists in Firestore"""
    db = get_db()
    return db.collection('users').document(uid).get().exists

def today_start():
    """Get start of today (midnight)"""
    return datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

def week_start():
    """Get start of this week (Monday midnight)"""
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    return today - timedelta(days=today.weekday())

def create_user(uid, email, role, name=''):
    """
    Create a new user in Firestore
    
    Args:
        uid: User ID from Firebase Auth
        email: User email
        role: User role (student, admin, consultant)
        name: User's display name
    """
    db = get_db()
    db.collection('users').document(uid).set({
        'uid': uid,
        'email': email,
        'role': role,
        'name': name,
        'created_at': datetime.now(),
        'updated_at': datetime.now()
    })
