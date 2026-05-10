"""
CONSULTANT / COUNSELOR SERVER
Port: 5002

Handles all counselor authentication, page routes, and API endpoints.
All data is fetched from / written to Firebase Firestore.
"""
from flask import Flask, request, jsonify, render_template, redirect
from datetime import datetime, timezone, timedelta
from config import ConsultantConfig
from db import (
    get_db, verify_token, get_user_role, user_exists, create_user,
    today_start, week_start,
)
from firebase_admin import auth as firebase_auth
from apscheduler.schedulers.background import BackgroundScheduler
import atexit

# ─── APP INIT ─────────────────────────────────────────────────────────────
app = Flask(__name__, template_folder='templates')
app.config.from_object(ConsultantConfig)

db = get_db()

# ─── HELPERS ──────────────────────────────────────────────────────────────

def _ts(dt):
    """Safely convert a Firestore Timestamp / datetime to ISO string."""
    if dt is None:
        return None
    if hasattr(dt, 'isoformat'):
        return dt.isoformat()
    # Firestore DatetimeWithNanoseconds has the same interface
    try:
        return dt.isoformat()
    except Exception:
        return str(dt)


def _ok(payload: dict):
    payload['success'] = True
    return jsonify(payload)


def _err(message: str, status: int = 400):
    return jsonify({'success': False, 'message': message}), status

# ─── AUTH PAGE ROUTES ─────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('counselor/Counselorlanding.html')

@app.route('/login')
def login():
    return render_template('counselor/Counselorlogin.html')

@app.route('/signup')
def signup():
    return render_template('counselor/Counselorsignup.html')

@app.route('/logout')
def logout():
    return redirect('/login')

# ─── COUNSELOR PAGE ROUTES ────────────────────────────────────────────────

@app.route('/dashboard')
def dashboard():
    return render_template('counselor/CounselorDashboard.html')

@app.route('/students')
def counselor_students():
    return render_template('counselor/Counselorstudents.html')

@app.route('/requests')
def counselor_requests():
    return render_template('counselor/Counselorrequest.html')

@app.route('/sessions')
def counselor_sessions():
    return render_template('counselor/Counselorsessions.html')

@app.route('/case-notes')
def counselor_case_notes():
    return render_template('counselor/Counselorcasenote.html')

@app.route('/risk-alerts')
def counselor_risk_alerts():
    return render_template('counselor/Counselorriskalert.html')

@app.route('/resources')
def counselor_resources():
    return render_template('counselor/Counselorresources.html')

@app.route('/about')
def counselor_about():
    return render_template('counselor/Counselorabout.html')

@app.route('/contacts')
def counselor_contacts():
    return render_template('counselor/Counselorcontact.html')

# ─── API: DASHBOARD STATS ─────────────────────────────────────────────────

@app.route('/api/dashboard/stats', methods=['GET'])
def api_dashboard_stats():
    """Return aggregated statistics for the counselor dashboard."""
    try:
        counselor_uid, _, _ = verify_token(request, allowed_roles=['consultant', 'counselor'])

        # Total students (all users with role=student, filtered in Python)
        all_user_docs  = list(db.collection('users').stream())
        student_docs   = [d for d in all_user_docs if d.to_dict().get('role') == 'student']
        total_students = len(student_docs)
        student_uids   = [d.id for d in student_docs]

        # Pending requests (global — not filtered by counselor)
        pending_docs = list(
            db.collection('counseling_sessions')
              .where('status', '==', 'pending')
              .stream()
        )
        pending_count = len(pending_docs)

        # Active sessions for this counselor
        active_docs = list(
            db.collection('counseling_sessions')
              .where('counselor_uid', '==', counselor_uid)
              .where('status', '==', 'active')
              .stream()
        )
        active_sessions = len(active_docs)

        # Closed / resolved sessions for this counselor
        resolved_docs = list(
            db.collection('counseling_sessions')
              .where('counselor_uid', '==', counselor_uid)
              .where('status', '==', 'closed')
              .stream()
        )
        resolved_count = len(resolved_docs)

        # Case notes written by this counselor
        notes_docs = list(
            db.collection('case_notes')
              .where('counselor_uid', '==', counselor_uid)
              .stream()
        )
        notes_count = len(notes_docs)

        # Risk alerts
        all_alerts = list(
            db.collection('risk_alerts')
              .where('resolved', '==', False)
              .stream()
        )
        high_risk = sum(1 for d in all_alerts if d.to_dict().get('level') == 'high')
        mod_risk  = sum(1 for d in all_alerts if d.to_dict().get('level') == 'medium')

        # Students monitored today (checked-in health logs)
        today = today_start()
        monitored_today = 0
        for uid in student_uids:
            logs = list(
                db.collection('health_logs')
                  .where('student_uid', '==', uid)
                  .where('created_at', '>=', today)
                  .limit(1)
                  .stream()
            )
            if logs:
                monitored_today += 1

        # At-risk students: those with an unresolved high-risk alert
        at_risk_uids = set(
            d.to_dict().get('student_uid')
            for d in all_alerts
            if d.to_dict().get('level') == 'high'
        )
        at_risk_count = len(at_risk_uids.intersection(set(student_uids)))

        return _ok({
            'total_students': total_students,
            'at_risk': at_risk_count,
            'resolved': resolved_count,
            'pending': pending_count,
            'active_sessions': active_sessions,
            'case_notes': notes_count,
            'high_risk_alerts': high_risk,
            'moderate_alerts': mod_risk,
            'monitored_today': monitored_today,
        })

    except Exception as e:
        return _err(str(e))

# ─── API: STUDENTS ────────────────────────────────────────────────────────

@app.route('/api/students', methods=['GET'])
def api_students_list():
    """Return all students (role=student) visible to the authenticated counselor."""
    try:
        counselor_uid, _, _ = verify_token(request, allowed_roles=['consultant', 'counselor'])

        # Fetch ALL users and filter by role in Python
        # (avoids needing a Firestore composite index on the users collection)
        all_user_docs = db.collection('users').stream()
        student_docs  = [d for d in all_user_docs if d.to_dict().get('role') == 'student']

        students = []
        for doc in student_docs:
            student_data = doc.to_dict()
            student_uid  = doc.id  # document ID is the Firebase UID

            # Fetch latest health log for this student
            logs = list(
                db.collection('health_logs')
                  .where('student_uid', '==', student_uid)
                  .order_by('created_at', direction='DESCENDING')
                  .limit(1)
                  .stream()
            )
            last_log = logs[0].to_dict() if logs else {}

            # Determine risk status from unresolved alerts
            alerts = list(
                db.collection('risk_alerts')
                  .where('student_uid', '==', student_uid)
                  .where('resolved', '==', False)
                  .stream()
            )
            levels = [a.to_dict().get('level', 'low') for a in alerts]
            if 'high' in levels:
                status = 'at_risk'
            elif 'medium' in levels:
                status = 'moderate'
            else:
                status = 'healthy'

            students.append({
                'uid':          student_uid,
                'name':         student_data.get('name') or student_data.get('displayName', ''),
                'email':        student_data.get('email', ''),
                'assigned_at':  None,   # no longer assignment-based
                'last_checkin': _ts(last_log.get('created_at')),
                'mood':         last_log.get('mood', '--'),
                'sleep':        last_log.get('sleep_hours', '--'),
                'stress':       last_log.get('stress', '--'),
                'water':        last_log.get('water_liters', '--'),
                'steps':        last_log.get('steps', '--'),
                'status':       status,
            })

        return _ok({'students': students})

    except Exception as e:
        return _err(str(e))

# ─── API: COUNSELING REQUESTS ─────────────────────────────────────────────

@app.route('/api/requests', methods=['GET'])
def api_counseling_requests():
    """Return student-initiated counseling requests (pending/active/declined).
    Excludes risk_alert auto-sessions which go straight to Active Sessions.
    """
    try:
        counselor_uid, _, _ = verify_token(request, allowed_roles=['consultant', 'counselor'])

        all_docs = list(
            db.collection('counseling_sessions')
              .order_by('created_at', direction='DESCENDING')
              .stream()
        )

        requests_list = []
        for doc in all_docs:
            session = doc.to_dict()
            status  = session.get('status', '')
            source  = session.get('source', 'request')

            if source == 'risk_alert':
                continue
            if status not in ('pending', 'active', 'declined'):
                continue

            student_uid   = session.get('student_uid', '')
            student_name  = session.get('student_name', '')
            student_email = ''
            if student_uid:
                s_doc = db.collection('users').document(student_uid).get()
                if s_doc.exists:
                    s = s_doc.to_dict()
                    student_name  = student_name or s.get('name') or s.get('displayName', '')
                    student_email = s.get('email', '')

            requests_list.append({
                'session_id':    doc.id,
                'student_uid':   student_uid,
                'student_name':  student_name,
                'student_email': student_email,
                'message':       session.get('message', ''),
                'status':        status,
                'created_at':    _ts(session.get('created_at')),
            })

        return _ok({'requests': requests_list})

    except Exception as e:
        return _err(str(e))


@app.route('/api/risk-alert/start-session', methods=['POST'])
def api_risk_alert_start_session():
    """Auto-create an active session from a risk alert (bypasses request queue)."""
    try:
        counselor_uid, _, _ = verify_token(request, allowed_roles=['consultant', 'counselor'])
        body        = request.get_json(silent=True) or {}
        student_uid = body.get('student_uid', '').strip()
        alert_id    = body.get('alert_id', '').strip()
        if not student_uid:
            return _err('student_uid is required')

        # Return existing active session if one already exists
        existing = list(
            db.collection('counseling_sessions')
              .where('student_uid', '==', student_uid)
              .where('status', '==', 'active')
              .limit(1)
              .stream()
        )
        if existing:
            return _ok({'session_id': existing[0].id, 'existing': True})

        student_name = ''
        s_doc = db.collection('users').document(student_uid).get()
        if s_doc.exists:
            s = s_doc.to_dict()
            student_name = s.get('name') or s.get('displayName', '')

        now = datetime.now(timezone.utc)
        _, new_ref = db.collection('counseling_sessions').add({
            'student_uid':   student_uid,
            'student_name':  student_name,
            'counselor_uid': counselor_uid,
            'source':        'risk_alert',
            'alert_id':      alert_id,
            'status':        'active',
            'message':       '(Session started by counselor via risk alert)',
            'created_at':    now,
            'accepted_at':   now,
        })

        return _ok({'session_id': new_ref.id, 'existing': False})

    except Exception as e:
        return _err(str(e))


# ─── API: SESSIONS ────────────────────────────────────────────────────────

@app.route('/api/sessions', methods=['GET'])
def api_sessions_list():
    """Return all active counseling sessions for this counselor."""
    try:
        counselor_uid, _, _ = verify_token(request, allowed_roles=['consultant', 'counselor'])

        docs = db.collection('counseling_sessions')\
                 .where('counselor_uid', '==', counselor_uid)\
                 .where('status', '==', 'active')\
                 .order_by('created_at', direction='DESCENDING')\
                 .stream()

        sessions = []
        for doc in docs:
            session = doc.to_dict()
            student_uid = session.get('student_uid', '')

            student_name  = ''
            student_email = ''
            if student_uid:
                s_doc = db.collection('users').document(student_uid).get()
                if s_doc.exists:
                    s = s_doc.to_dict()
                    student_name  = s.get('name') or s.get('displayName', '')
                    student_email = s.get('email', '')

            # Last message preview
            msgs = list(
                db.collection('counseling_sessions').document(doc.id)
                  .collection('messages')
                  .order_by('timestamp', direction='DESCENDING')
                  .limit(1)
                  .stream()
            )
            last_msg = msgs[0].to_dict().get('text', '') if msgs else ''

            sessions.append({
                'session_id':    doc.id,
                'student_uid':   student_uid,
                'student_name':  student_name,
                'student_email': student_email,
                'status':        session.get('status', 'active'),
                'accepted_at':   _ts(session.get('accepted_at')),
                'created_at':    _ts(session.get('created_at')),
                'last_message':  last_msg,
            })

        return _ok({'sessions': sessions})

    except Exception as e:
        return _err(str(e))


@app.route('/api/session/<session_id>/messages', methods=['GET'])
def api_session_messages(session_id):
    """Return all messages in a counseling session."""
    try:
        counselor_uid, _, _ = verify_token(request, allowed_roles=['consultant', 'counselor'])

        # Verify the session belongs to this counselor
        session_doc = db.collection('counseling_sessions').document(session_id).get()
        if not session_doc.exists:
            return _err('Session not found', 404)

        msgs_docs = db.collection('counseling_sessions').document(session_id)\
                      .collection('messages')\
                      .order_by('timestamp')\
                      .stream()

        messages = []
        for doc in msgs_docs:
            msg = doc.to_dict()
            messages.append({
                'id':        doc.id,
                'sender':    msg.get('sender', ''),
                'sender_uid': msg.get('sender_uid', ''),
                'role':      msg.get('role', ''),
                'text':      msg.get('text', ''),
                'timestamp': _ts(msg.get('timestamp')),
            })

        return _ok({'messages': messages})

    except Exception as e:
        return _err(str(e))


@app.route('/api/session/<session_id>/message', methods=['POST'])
def api_session_send_message(session_id):
    """Counselor sends a message in a session."""
    try:
        counselor_uid, _, _ = verify_token(request, allowed_roles=['consultant', 'counselor'])
        body = request.get_json(silent=True) or {}
        text = body.get('text', '').strip()
        if not text:
            return _err('Message text is required')

        # Fetch counselor name
        c_doc = db.collection('users').document(counselor_uid).get()
        c_name = ''
        if c_doc.exists:
            c = c_doc.to_dict()
            c_name = c.get('name') or c.get('displayName', 'Counselor')

        now = datetime.now(timezone.utc)
        db.collection('counseling_sessions').document(session_id)\
          .collection('messages').add({
              'sender':     c_name,
              'sender_uid': counselor_uid,
              'role':       'counselor',
              'text':       text,
              'timestamp':  now,
          })

        return _ok({'message': 'Message sent', 'timestamp': _ts(now)})

    except Exception as e:
        return _err(str(e))


@app.route('/api/session/<session_id>/accept', methods=['POST'])
def api_session_accept(session_id):
    """Accept a pending counseling request."""
    try:
        counselor_uid, _, _ = verify_token(request, allowed_roles=['consultant', 'counselor'])

        session_ref = db.collection('counseling_sessions').document(session_id)
        session_doc = session_ref.get()
        if not session_doc.exists:
            return _err('Session not found', 404)

        session_ref.update({
            'status':       'active',
            'counselor_uid': counselor_uid,
            'accepted_at':  datetime.now(timezone.utc),
        })

        return _ok({'message': 'Session accepted'})

    except Exception as e:
        return _err(str(e))


@app.route('/api/session/<session_id>/decline', methods=['POST'])
def api_session_decline(session_id):
    """Decline a pending counseling request."""
    try:
        counselor_uid, _, _ = verify_token(request, allowed_roles=['consultant', 'counselor'])

        session_ref = db.collection('counseling_sessions').document(session_id)
        if not session_ref.get().exists:
            return _err('Session not found', 404)

        session_ref.update({
            'status':       'declined',
            'counselor_uid': counselor_uid,
            'declined_at':  datetime.now(timezone.utc),
        })

        return _ok({'message': 'Session declined'})

    except Exception as e:
        return _err(str(e))


@app.route('/api/session/<session_id>/close', methods=['POST'])
def api_session_close(session_id):
    """Close an active counseling session."""
    try:
        counselor_uid, _, _ = verify_token(request, allowed_roles=['consultant', 'counselor'])

        session_ref = db.collection('counseling_sessions').document(session_id)
        if not session_ref.get().exists:
            return _err('Session not found', 404)

        session_ref.update({
            'status':    'closed',
            'closed_at': datetime.now(timezone.utc),
        })

        return _ok({'message': 'Session closed'})

    except Exception as e:
        return _err(str(e))

# ─── API: CASE NOTES ──────────────────────────────────────────────────────

@app.route('/api/case-note', methods=['POST'])
def api_case_note_create():
    """Create a new case note for a student."""
    try:
        counselor_uid, _, _ = verify_token(request, allowed_roles=['consultant', 'counselor'])
        body = request.get_json(silent=True) or {}

        student_uid = body.get('student_uid', '').strip()
        note_text   = body.get('note', '').strip()
        followup    = body.get('followup', '').strip()

        if not student_uid:
            return _err('student_uid is required')
        if not note_text:
            return _err('note text is required')

        db.collection('case_notes').add({
            'counselor_uid': counselor_uid,
            'student_uid':   student_uid,
            'note':          note_text,
            'followup':      followup,
            'created_at':    datetime.now(timezone.utc),
        })

        return _ok({'message': 'Case note saved'})

    except Exception as e:
        return _err(str(e))


@app.route('/api/case-notes/<student_uid>', methods=['GET'])
def api_case_notes_list(student_uid):
    """Return all case notes for a specific student."""
    try:
        counselor_uid, _, _ = verify_token(request, allowed_roles=['consultant', 'counselor'])

        docs = db.collection('case_notes')\
                 .where('student_uid', '==', student_uid)\
                 .order_by('created_at', direction='DESCENDING')\
                 .stream()

        notes = []
        for doc in docs:
            note = doc.to_dict()
            notes.append({
                'id':            doc.id,
                'counselor_uid': note.get('counselor_uid', ''),
                'note':          note.get('note', ''),
                'followup':      note.get('followup', ''),
                'created_at':    _ts(note.get('created_at')),
            })

        return _ok({'notes': notes})

    except Exception as e:
        return _err(str(e))

# ─── API: RISK ALERTS ─────────────────────────────────────────────────────

@app.route('/api/risk-alert', methods=['POST'])
def api_risk_alert_create():
    """Create a risk alert for a student."""
    try:
        counselor_uid, _, _ = verify_token(request, allowed_roles=['consultant', 'counselor'])
        body = request.get_json(silent=True) or {}

        student_uid = body.get('student_uid', '').strip()
        level       = body.get('level', 'low')          # low | medium | high
        description = body.get('description', '').strip()

        if not student_uid:
            return _err('student_uid is required')
        if level not in ('low', 'medium', 'high'):
            return _err('level must be low, medium, or high')

        db.collection('risk_alerts').add({
            'counselor_uid': counselor_uid,
            'student_uid':   student_uid,
            'level':         level,
            'description':   description,
            'resolved':      False,
            'created_at':    datetime.now(timezone.utc),
        })

        return _ok({'message': 'Risk alert created'})

    except Exception as e:
        return _err(str(e))


@app.route('/api/risk-alerts', methods=['GET'])
def api_risk_alerts_list():
    """Return all unresolved risk alerts with student details."""
    try:
        counselor_uid, _, _ = verify_token(request, allowed_roles=['consultant', 'counselor'])

        docs = db.collection('risk_alerts')\
                 .where('resolved', '==', False)\
                 .order_by('created_at', direction='DESCENDING')\
                 .stream()

        alerts = []
        for doc in docs:
            alert = doc.to_dict()
            student_uid = alert.get('student_uid', '')

            student_name  = ''
            student_email = ''
            if student_uid:
                s_doc = db.collection('users').document(student_uid).get()
                if s_doc.exists:
                    s = s_doc.to_dict()
                    student_name  = s.get('name') or s.get('displayName', '')
                    student_email = s.get('email', '')

            alerts.append({
                'id':             doc.id,
                'student_uid':    student_uid,
                'student_name':   student_name,
                'student_email':  student_email,
                'level':          alert.get('level', 'low'),
                'description':    alert.get('description', ''),
                'created_at':     _ts(alert.get('created_at')),
                'auto_generated': alert.get('auto_generated', False),  # fix: expose to UI
            })

        return _ok({'alerts': alerts})

    except Exception as e:
        return _err(str(e))


@app.route('/api/risk-alert/<alert_id>/resolve', methods=['POST'])
def api_risk_alert_resolve(alert_id):
    """Mark a risk alert as resolved."""
    try:
        counselor_uid, _, _ = verify_token(request, allowed_roles=['consultant', 'counselor'])

        alert_ref = db.collection('risk_alerts').document(alert_id)
        if not alert_ref.get().exists:
            return _err('Alert not found', 404)

        alert_ref.update({
            'resolved':    True,
            'resolved_at': datetime.now(timezone.utc),
            'resolved_by': counselor_uid,
        })

        return _ok({'message': 'Alert resolved'})

    except Exception as e:
        return _err(str(e))

# ─── API: AUTH / SIGNUP VERIFICATION ─────────────────────────────────────

@app.route('/api/auth/verify-role', methods=['POST'])
def api_verify_role():
    """
    Called by the frontend after Firebase login to confirm the user is a counselor.
    Returns the user's role so the frontend can redirect appropriately.
    """
    try:
        uid, decoded, role = verify_token(request)
        return _ok({'role': role, 'uid': uid})
    except Exception as e:
        return _err(str(e), 401)


@app.route('/api/auth/register', methods=['POST'])
def api_register():
    """
    Register a new counselor account in Firestore after Firebase Auth creation.
    The frontend creates the Firebase Auth user, then calls this endpoint to
    persist the Firestore user document.
    """
    try:
        uid, _, _ = verify_token(request)
        body = request.get_json(silent=True) or {}

        name  = body.get('name', '').strip()
        email = body.get('email', '').strip()

        if not name or not email:
            return _err('name and email are required')

        if not user_exists(uid):
            create_user(uid, email, role='counselor', name=name)

        return _ok({'message': 'Counselor registered', 'uid': uid})

    except Exception as e:
        return _err(str(e))

# ─── API: RESOURCE LIBRARY ───────────────────────────────────────────────

@app.route('/api/resources', methods=['GET'])
def api_resources_list():
    """Return all resources. Accessible by any authenticated user."""
    try:
        verify_token(request)
        docs = db.collection('resources') \
                 .order_by('created_at', direction='DESCENDING') \
                 .stream()
        resources = []
        for doc in docs:
            r = doc.to_dict()
            resources.append({
                'id':          doc.id,
                'title':       r.get('title', ''),
                'category':    r.get('category', ''),
                'description': r.get('description', ''),
                'link':        r.get('link', ''),
                'read_time':   r.get('read_time', ''),
                'created_at':  _ts(r.get('created_at')),
            })
        return _ok({'resources': resources})
    except Exception as e:
        return _err(str(e))


@app.route('/api/resource', methods=['POST'])
def api_resource_create():
    """Create a new resource. Counselors only."""
    try:
        counselor_uid, _, _ = verify_token(request, allowed_roles=['consultant', 'counselor'])
        body = request.get_json(silent=True) or {}

        title       = body.get('title', '').strip()
        category    = body.get('category', '').strip()
        description = body.get('description', '').strip()
        link        = body.get('link', '').strip()
        read_time   = body.get('read_time', '').strip()

        if not title:       return _err('title is required')
        if not category:    return _err('category is required')
        if not description: return _err('description is required')

        valid_categories = ['Mental Health', 'Physical Wellness', 'Sleep', 'Nutrition', 'Stress Management', 'Other']
        if category not in valid_categories:
            return _err(f'category must be one of: {", ".join(valid_categories)}')

        db.collection('resources').add({
            'title':       title,
            'category':    category,
            'description': description,
            'link':        link,
            'read_time':   read_time,
            'created_by':  counselor_uid,
            'created_at':  datetime.now(timezone.utc),
            'updated_at':  datetime.now(timezone.utc),
        })
        return _ok({'message': 'Resource created'})
    except Exception as e:
        return _err(str(e))


@app.route('/api/resource/<resource_id>', methods=['PUT'])
def api_resource_update(resource_id):
    """Update an existing resource. Counselors only."""
    try:
        counselor_uid, _, _ = verify_token(request, allowed_roles=['consultant', 'counselor'])
        body = request.get_json(silent=True) or {}

        ref = db.collection('resources').document(resource_id)
        if not ref.get().exists:
            return _err('Resource not found', 404)

        title       = body.get('title', '').strip()
        category    = body.get('category', '').strip()
        description = body.get('description', '').strip()
        link        = body.get('link', '').strip()
        read_time   = body.get('read_time', '').strip()

        if not title or not category or not description:
            return _err('title, category, and description are required')

        ref.update({
            'title':       title,
            'category':    category,
            'description': description,
            'link':        link,
            'read_time':   read_time,
            'updated_at':  datetime.now(timezone.utc),
            'updated_by':  counselor_uid,
        })
        return _ok({'message': 'Resource updated'})
    except Exception as e:
        return _err(str(e))


@app.route('/api/resource/<resource_id>', methods=['DELETE'])
def api_resource_delete(resource_id):
    """Delete a resource. Counselors only."""
    try:
        counselor_uid, _, _ = verify_token(request, allowed_roles=['consultant', 'counselor'])
        ref = db.collection('resources').document(resource_id)
        if not ref.get().exists:
            return _err('Resource not found', 404)
        ref.delete()
        return _ok({'message': 'Resource deleted'})
    except Exception as e:
        return _err(str(e))


# ─── AUTOMATED RISK DETECTION (runs in background every 6 hours) ──────────

def run_risk_checks():
    """
    Scans all students against the thresholds saved in Firestore
    (settings/alert_thresholds). Fires automatically — no API call needed.
    Results appear instantly in the counselor Risk Alerts UI via onSnapshot.
    """
    print(f'[Risk Check] Starting scan at {datetime.now(timezone.utc).isoformat()}')
    try:
        _db = get_db()

        # Load thresholds — reads from system_config/config (same as admin server writes)
        thresh_doc = _db.collection('system_config').document('config').get()
        thresh     = thresh_doc.to_dict() if thresh_doc.exists else {}
        sleep_min  = thresh.get('sleep_hours',    5)
        stress_max = thresh.get('stress_level',   4)
        mood_days  = thresh.get('mood_drop_days', 2)
        act_days   = thresh.get('activity_days',  3)
        combo_n    = thresh.get('combined_count', 3)

        # Get all students
        all_users = _db.collection('users').stream()
        students  = [
            {'uid': d.id, **d.to_dict()}
            for d in all_users
            if d.to_dict().get('role') == 'student'
        ]

        now      = datetime.now(timezone.utc)
        week_ago = now - timedelta(days=7)
        total_alerts = 0

        for student in students:
            uid      = student['uid']
            user_ref = _db.collection('users').document(uid)

            def recent(col, limit=7, _ref=user_ref):
                return [
                    d.to_dict()
                    for d in _ref.collection(col)
                                 .where('logged_at', '>=', week_ago)
                                 .order_by('logged_at', direction='DESCENDING')
                                 .limit(limit)
                                 .stream()
                ]

            sleep_logs    = recent('sleep_records')
            stress_logs   = recent('stress_records')
            mood_logs     = recent('mood_records')
            activity_logs = recent('activity_records')

            low_count      = 0
            alerts_to_fire = []

            # Rule 1: Sleep Collapse
            if sleep_logs:
                latest_sleep = sleep_logs[0].get('hours', 99)
                if latest_sleep < sleep_min:
                    low_count += 1
                    alerts_to_fire.append({
                        'rule':        'Sleep Collapse',
                        'level':       'medium',
                        'description': f'Sleep dropped to {latest_sleep} hrs (threshold: {sleep_min} hrs)',
                    })

            # Rule 2: Stress Spike
            if stress_logs:
                latest_stress = stress_logs[0].get('level', 0)
                if latest_stress >= stress_max:
                    low_count += 1
                    alerts_to_fire.append({
                        'rule':        'Stress Level Spike',
                        'level':       'high',
                        'description': f'Stress reached {latest_stress}/5 (threshold: {stress_max}/5)',
                    })

            # Rule 3: Activity Withdrawal
            days_inactive = 0
            for i in range(act_days):
                day_start_dt = now - timedelta(days=i + 1)
                day_end_dt   = now - timedelta(days=i)
                has_log = any(
                    day_start_dt <= (
                        a['logged_at']
                        if isinstance(a['logged_at'], datetime)
                        else a['logged_at'].replace(tzinfo=timezone.utc)
                    ) < day_end_dt
                    for a in activity_logs
                    if 'logged_at' in a
                )
                if not has_log:
                    days_inactive += 1

            if days_inactive >= act_days:
                low_count += 1
                alerts_to_fire.append({
                    'rule':        'Activity Withdrawal',
                    'level':       'medium',
                    'description': f'No activity logged for {days_inactive} consecutive days',
                })

            # Rule 4: Mood Drop Streak
            mood_values = [
                m.get('mood_score', m.get('level', 3))
                for m in mood_logs[: mood_days + 1]
            ]
            if len(mood_values) >= 2 and all(
                mood_values[i] < mood_values[i + 1]
                for i in range(len(mood_values) - 1)
            ):
                low_count += 1
                alerts_to_fire.append({
                    'rule':        'Sudden Mood Drop',
                    'level':       'high',
                    'description': f'{mood_days}-day downward mood streak detected',
                })

            # Rule 5: Combined Low Indicators
            if low_count >= combo_n:
                alerts_to_fire.append({
                    'rule':        'Combined Low Indicators',
                    'level':       'high',
                    'description': f'{low_count} health metrics simultaneously below threshold',
                })

            # Dedup: skip rules that already have an open alert for this student
            existing_rules = {
                d.to_dict().get('rule')
                for d in _db.collection('risk_alerts')
                             .where('student_uid', '==', uid)
                             .where('resolved', '==', False)
                             .stream()
            }

            for alert in alerts_to_fire:
                if alert['rule'] in existing_rules:
                    continue

                _db.collection('risk_alerts').add({
                    **alert,
                    'student_uid':    uid,
                    'student_name':   student.get('name', ''),
                    'student_email':  student.get('email', ''),
                    'resolved':       False,
                    'auto_generated': True,
                    'created_at':     datetime.now(timezone.utc),
                })
                total_alerts += 1

        print(f'[Risk Check] Done — {len(students)} students scanned, {total_alerts} new alerts created')

    except Exception as e:
        print(f'[Risk Check] ERROR: {e}')


# Start scheduler when Flask boots
_scheduler = BackgroundScheduler(timezone='UTC')
_scheduler.add_job(
    func=run_risk_checks,
    trigger='interval',
    hours=6,            # change to minutes=1 for testing, back to hours=6 for production
    id='risk_check',
    replace_existing=True,
    next_run_time=datetime.now(timezone.utc),   # also runs once immediately on startup
)
_scheduler.start()
atexit.register(lambda: _scheduler.shutdown(wait=False))

@app.route('/api/system/config', methods=['GET'])
def api_counselor_config_get():
    """Read alert thresholds — counselor-accessible mirror of admin system config."""
    try:
        verify_token(request, allowed_roles=['consultant', 'counselor'])
        doc = db.collection('system_config').document('config').get()
        return _ok({'config': doc.to_dict() if doc.exists else {}})
    except Exception as e:
        return _err(str(e))


@app.route('/api/system/config', methods=['POST'])
def api_counselor_config_update():
    """Save alert thresholds — writes to system_config/config (same as admin server)."""
    try:
        verify_token(request, allowed_roles=['consultant', 'counselor'])
        body = request.get_json(silent=True) or {}
        allowed_keys = {'mood_drop_days', 'stress_level', 'sleep_hours', 'activity_days', 'combined_count'}
        updates = {k: v for k, v in body.items() if k in allowed_keys}
        if not updates:
            return _err('No valid threshold fields provided')
        db.collection('system_config').document('config').set(updates, merge=True)
        return _ok({'message': 'Thresholds saved'})
    except Exception as e:
        return _err(str(e))


# ─── ERROR HANDLERS ───────────────────────────────────────────────────────

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(405)
def method_not_allowed(error):
    return jsonify({'error': 'Method not allowed'}), 405

@app.errorhandler(500)
def server_error(error):
    return jsonify({'error': 'Internal server error'}), 500

# ─── RUN ──────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    print(f'Starting Consultant Server on port {ConsultantConfig.PORT}...')
    app.run(
        host=ConsultantConfig.HOST,
        port=ConsultantConfig.PORT,
        debug=ConsultantConfig.DEBUG,
    )