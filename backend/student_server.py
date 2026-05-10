"""
STUDENT SERVER
Port: 5000

Handles student login, signup, and all student-specific routes and APIs
Only students can access this server
"""
from flask import Flask, request, jsonify, render_template, redirect
from datetime import datetime, timezone
from config import StudentConfig
from db import (
    get_db, verify_token, get_user_role, user_exists, create_user,
    today_start, week_start
)
from firebase_admin import auth as firebase_auth

# ─── INITIALIZE APP ───────────────────────────────────────────────────────
app = Flask(__name__, template_folder='templates')
app.config.from_object(StudentConfig)

db = get_db()

# ─── HELPER FUNCTION ──────────────────────────────────────────────────────

def recompute_summaries(uid):
    """
    Recompute and cache daily and weekly summaries for a student.
    Called after every health log submission.
    """
    try:
        ts = today_start()
        ws = week_start()

        def serialize(record):
            d = record.to_dict()
            if 'logged_at' in d and hasattr(d['logged_at'], 'isoformat'):
                d['logged_at'] = d['logged_at'].isoformat()
            return d

        # Get today's records
        sleep_today = [serialize(r) for r in
                       db.collection('users').document(uid).collection('sleep_records')
                       .where('logged_at', '>=', ts).stream()]
        mood_today = [serialize(r) for r in
                      db.collection('users').document(uid).collection('mood_records')
                      .where('logged_at', '>=', ts).stream()]
        water_today = [serialize(r) for r in
                       db.collection('users').document(uid).collection('water_records')
                       .where('logged_at', '>=', ts).stream()]
        stress_today = [serialize(r) for r in
                        db.collection('users').document(uid).collection('stress_records')
                        .where('logged_at', '>=', ts).stream()]
        activity_today = [serialize(r) for r in
                          db.collection('users').document(uid).collection('activity_records')
                          .where('logged_at', '>=', ts).stream()]
        steps_today = [serialize(r) for r in
                       db.collection('users').document(uid).collection('step_records')
                       .where('logged_at', '>=', ts).stream()]

        # Cache daily summary
        daily_summary = {
            'mood':          mood_today[-1]['mood'] if mood_today else None,
            'sleep':         sleep_today[-1]['total'] if sleep_today else None,
            'water_liters':  round(sum(r.get('amount_ml', 0) for r in water_today) / 1000, 1),
            'stress':        'Logged' if stress_today else None,
            'activity_mins': sum(r.get('duration_mins', 0) for r in activity_today),
            'steps':         sum(r.get('steps', 0) for r in steps_today),
            'updated_at':    datetime.now(timezone.utc),
        }
        db.collection('users').document(uid).collection('summaries').document('daily').set(daily_summary, merge=True)

        # Get week's records
        sleep_week = [serialize(r) for r in
                      db.collection('users').document(uid).collection('sleep_records')
                      .where('logged_at', '>=', ws).stream()]
        mood_week = [serialize(r) for r in
                     db.collection('users').document(uid).collection('mood_records')
                     .where('logged_at', '>=', ws).stream()]
        water_week = [serialize(r) for r in
                      db.collection('users').document(uid).collection('water_records')
                      .where('logged_at', '>=', ws).stream()]
        stress_week = [serialize(r) for r in
                       db.collection('users').document(uid).collection('stress_records')
                       .where('logged_at', '>=', ws).stream()]
        activity_week = [serialize(r) for r in
                         db.collection('users').document(uid).collection('activity_records')
                         .where('logged_at', '>=', ws).stream()]
        steps_week = [serialize(r) for r in
                      db.collection('users').document(uid).collection('step_records')
                      .where('logged_at', '>=', ws).stream()]

        # Cache weekly summary
        weekly_summary = {
            'sleep':    sleep_week,
            'mood':     mood_week,
            'water':    water_week,
            'stress':   stress_week,
            'activity': activity_week,
            'steps':    steps_week,
            'updated_at': datetime.now(timezone.utc),
        }
        db.collection('users').document(uid).collection('summaries').document('weekly').set(weekly_summary, merge=True)
    except Exception as e:
        print(f"Error recomputing summaries for {uid}: {e}")

# ─── AUTHENTICATION ROUTES ────────────────────────────────────────────────

@app.route('/')
def index():
    """Landing page"""
    return render_template('student/Landing.html')

@app.route('/login')
def login():
    """Student login page"""
    return render_template('student/login.html')

@app.route('/signup')
def signup():
    """Student signup page"""
    return render_template('student/signup.html')

@app.route('/logout')
def logout():
    """Logout - redirect to login"""
    return redirect('/login')

# ─── STUDENT PAGE ROUTES ──────────────────────────────────────────────────

@app.route('/dashboard')
def dashboard():
    """Main student dashboard"""
    return render_template('student/Dashboard.html')

@app.route('/sleep-tracker')
def sleep_tracker():
    """Sleep tracking page"""
    return render_template('student/Sleeptracker.html')

@app.route('/water-intake')
def water_intake():
    """Water intake tracking page"""
    return render_template('student/Waterintake.html')

@app.route('/mood-tracker')
def mood_tracker():
    """Mood tracking page"""
    return render_template('student/Moodtracker.html')

@app.route('/stress-note')
def stress_note():
    """Stress note page"""
    return render_template('student/Stressnote.html')

@app.route('/activity-log')
def activity_log():
    """Activity logging page"""
    return render_template('student/Activitylog.html')

@app.route('/step-tracker')
def step_tracker():
    """Step tracking page"""
    return render_template('student/Steptracker.html')

@app.route('/ai-chat')
def ai_chat():
    """AI chat page"""
    return render_template('student/Ai.html')

@app.route('/weekly-summary')
def weekly_summary():
    """Weekly summary page"""
    return render_template('student/Weeklysummary.html')

# ─── FCM TOKEN API ────────────────────────────────────────────────

@app.route('/api/fcm-token', methods=['POST'])
def api_fcm_token():
    """Save or update the student's FCM token for push notifications."""
    try:
        uid, _, _ = verify_token(request, allowed_roles=['student'])
        body  = request.get_json(silent=True) or {}
        token = (body.get('token') or body.get('fcm_token') or '').strip()
        if not token:
            return jsonify({'success': False, 'message': 'token is required'}), 400

        db.collection('users').document(uid).set(
            {'fcm_token': token, 'updated_at': datetime.now(timezone.utc)},
            merge=True
        )
        return jsonify({'success': True, 'message': 'FCM token saved.'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400


@app.route('/profile')
def profile_page():
    """Student profile page"""
    return render_template('student/Profile.html')

@app.route('/resource-library')
def resource_library():
    """Resource library page"""
    return render_template('student/Resourcelibrary.html')

@app.route('/counseling')
def counseling():
    """Counseling page"""
    return render_template('student/Counseling.html')

@app.route('/about')
def about():
    """About page"""
    return render_template('student/About.html')

@app.route('/save-confirmation')
def save_confirmation():
    """Save confirmation page"""
    return render_template('student/Saveconfirmation.html')

@app.route('/contacts')
def contacts():
    """Contacts page"""
    return render_template('student/Contacts.html')

# ─── STUDENT API ENDPOINTS ────────────────────────────────────────────────

@app.route('/api/sleep', methods=['POST'])
def api_sleep():
    """Log sleep data"""
    try:
        uid, _, _ = verify_token(request, allowed_roles=['student'])
        body = request.get_json(silent=True) or {}
        sleep_time = body.get('sleep_time')
        wake_time = body.get('wake_time')
        if not sleep_time or not wake_time:
            return jsonify({'success': False, 'message': 'sleep_time and wake_time are required'}), 400

        # Calculate total sleep hours
        sh, sm = map(int, sleep_time.split(':'))
        wh, wm = map(int, wake_time.split(':'))
        sleep_mins = sh * 60 + sm
        wake_mins = wh * 60 + wm
        if wake_mins <= sleep_mins:
            wake_mins += 24 * 60
        total_hours = round((wake_mins - sleep_mins) / 60, 1)
        total = f"{total_hours} hrs"

        # Save to database
        db.collection('users').document(uid).collection('sleep_records').add({
            'sleep_time': sleep_time,
            'wake_time': wake_time,
            'total': total,
            'logged_at': datetime.now(timezone.utc)
        })
        recompute_summaries(uid)
        return jsonify({'success': True, 'total': total, 'message': 'Sleep record saved!'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@app.route('/api/water', methods=['POST'])
def api_water():
    """Log water intake"""
    try:
        uid, _, _ = verify_token(request, allowed_roles=['student'])
        body = request.get_json(silent=True) or {}
        try:
            amount_ml = int(body.get('amount_ml', 0))
        except (ValueError, TypeError):
            return jsonify({'success': False, 'message': 'amount_ml must be a valid integer'}), 400

        # Save to database
        db.collection('users').document(uid).collection('water_records').add({
            'amount_ml': amount_ml,
            'logged_at': datetime.now(timezone.utc)
        })

        # Calculate today's total
        records = db.collection('users').document(uid).collection('water_records')\
                    .where('logged_at', '>=', today_start()).stream()
        total_ml = sum(r.to_dict().get('amount_ml', 0) for r in records)
        total_liters = round(total_ml / 1000, 1)
        percentage = min(round((total_ml / 2000) * 100), 100)

        recompute_summaries(uid)
        return jsonify({'success': True, 'total_liters': total_liters, 'percentage': percentage})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@app.route('/api/mood', methods=['POST'])
def api_mood():
    """Log mood data"""
    try:
        uid, _, _ = verify_token(request, allowed_roles=['student'])
        body = request.get_json(silent=True) or {}
        mood = body.get('mood')
        if not mood:
            return jsonify({'success': False, 'message': 'mood is required'}), 400
        db.collection('users').document(uid).collection('mood_records').add({
            'mood': mood,
            'note': body.get('note', ''),
            'logged_at': datetime.now(timezone.utc)
        })
        recompute_summaries(uid)
        return jsonify({'success': True, 'message': 'Mood logged!'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@app.route('/api/stress', methods=['POST'])
def api_stress():
    """Log stress data"""
    try:
        uid, _, _ = verify_token(request, allowed_roles=['student'])
        body = request.get_json(silent=True) or {}
        note = body.get('note')
        stressor = body.get('stressor')
        if not note or not stressor:
            return jsonify({'success': False, 'message': 'note and stressor are required'}), 400
        db.collection('users').document(uid).collection('stress_records').add({
            'note': note,
            'stressor': stressor,
            'logged_at': datetime.now(timezone.utc)
        })
        recompute_summaries(uid)
        return jsonify({'success': True, 'message': 'Stress note saved!'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@app.route('/api/activity', methods=['POST'])
def api_activity():
    """Log activity data"""
    try:
        uid, _, _ = verify_token(request, allowed_roles=['student'])
        body = request.get_json(silent=True) or {}
        activity = body.get('activity')
        if not activity:
            return jsonify({'success': False, 'message': 'activity is required'}), 400
        try:
            duration_mins = int(body.get('duration_mins', 0))
        except (ValueError, TypeError):
            return jsonify({'success': False, 'message': 'duration_mins must be a valid integer'}), 400

        db.collection('users').document(uid).collection('activity_records').add({
            'activity': activity,
            'duration_mins': duration_mins,
            'logged_at': datetime.now(timezone.utc)
        })

        # Calculate today's total
        records = db.collection('users').document(uid).collection('activity_records')\
                      .where('logged_at', '>=', today_start()).stream()
        total_mins = sum(r.to_dict().get('duration_mins', 0) for r in records)
        percentage = min(round((total_mins / 60) * 100), 100)

        recompute_summaries(uid)
        return jsonify({'success': True, 'total_mins': total_mins, 'percentage': percentage})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@app.route('/api/steps', methods=['POST'])
def api_steps():
    """Log steps data"""
    try:
        uid, _, _ = verify_token(request, allowed_roles=['student'])
        body = request.get_json(silent=True) or {}
        try:
            steps = int(body.get('steps', 0))
        except (ValueError, TypeError):
            return jsonify({'success': False, 'message': 'steps must be a valid integer'}), 400

        db.collection('users').document(uid).collection('step_records').add({
            'steps': steps,
            'logged_at': datetime.now(timezone.utc)
        })

        # Calculate today's total
        records = db.collection('users').document(uid).collection('step_records')\
                        .where('logged_at', '>=', today_start()).stream()
        total_steps = sum(r.to_dict().get('steps', 0) for r in records)
        percentage = min(round((total_steps / 10000) * 100), 100)

        recompute_summaries(uid)
        return jsonify({'success': True, 'total_steps': total_steps, 'percentage': percentage})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

# ─── DASHBOARD SUMMARY APIS ───────────────────────────────────────────────

@app.route('/api/summary/today', methods=['GET'])
def today_summary():
    """
    Get today's summary.
    Reads from the pre-computed 'summaries/daily' doc which is refreshed
    automatically every time a health log is submitted.
    Falls back to live query if no cached doc exists yet.
    """
    try:
        uid, _, _ = verify_token(request, allowed_roles=['student'])

        cached = db.collection('users').document(uid) \
                   .collection('summaries').document('daily').get()

        if cached.exists:
            data = cached.to_dict()
            # Strip the server timestamp before returning
            data.pop('updated_at', None)
            return jsonify({'success': True, 'summary': data})

        # ── Fallback: live query (first call before any log has been submitted) ──
        ts = today_start()
        def latest(col):
            return [r.to_dict() for r in
                    db.collection('users').document(uid).collection(col)
                    .where('logged_at', '>=', ts).stream()]

        sleep    = latest('sleep_records')
        mood     = latest('mood_records')
        water    = latest('water_records')
        stress   = latest('stress_records')
        activity = latest('activity_records')
        steps    = latest('step_records')

        return jsonify({
            'success': True,
            'summary': {
                'mood':          mood[-1]['mood'] if mood else '--',
                'sleep':         sleep[-1]['total'] if sleep else '0 hrs',
                'water_liters':  round(sum(r.get('amount_ml', 0) for r in water) / 1000, 1),
                'stress':        'Logged' if stress else 'None',
                'activity_mins': sum(r.get('duration_mins', 0) for r in activity),
                'steps':         sum(r.get('steps', 0) for r in steps),
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@app.route('/api/summary/weekly', methods=['GET'])
def weekly_summary_api():
    """
    Get weekly summary.
    Reads from the pre-computed 'summaries/weekly' doc which is refreshed
    automatically every time a health log is submitted.
    Falls back to live query if no cached doc exists yet.
    """
    try:
        uid, _, _ = verify_token(request, allowed_roles=['student'])

        cached = db.collection('users').document(uid) \
                   .collection('summaries').document('weekly').get()

        if cached.exists:
            data = cached.to_dict()
            return jsonify({'success': True, 'summary': data})

        # ── Fallback: live query ──
        ws = week_start()

        def serialize(record):
            d = record.to_dict()
            if 'logged_at' in d and hasattr(d['logged_at'], 'isoformat'):
                d['logged_at'] = d['logged_at'].isoformat()
            return d

        def get_records(col):
            return [serialize(r) for r in
                    db.collection('users').document(uid).collection(col)
                    .where('logged_at', '>=', ws).stream()]

        return jsonify({'success': True, 'summary': {
            'sleep':    get_records('sleep_records'),
            'mood':     get_records('mood_records'),
            'water':    get_records('water_records'),
            'stress':   get_records('stress_records'),
            'activity': get_records('activity_records'),
            'steps':    get_records('step_records'),
        }})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

# ─── COUNSELING REQUEST API ───────────────────────────────────────────────

@app.route('/api/counseling/request', methods=['POST'])
def api_counseling_request():
    """Create a new counseling request. Returns the new session_id."""
    try:
        uid, _, _ = verify_token(request, allowed_roles=['student'])
        body = request.get_json(silent=True) or {}
        message = body.get('message', '').strip()
        if not message:
            return jsonify({'success': False, 'message': 'message is required'}), 400

        # Fetch student name for counselor-side display
        s_doc = db.collection('users').document(uid).get()
        student_name = ''
        if s_doc.exists:
            s = s_doc.to_dict()
            student_name = s.get('name') or s.get('displayName', '')

        now = datetime.now(timezone.utc)
        _, new_ref = db.collection('counseling_sessions').add({
            'student_uid':  uid,
            'student_name': student_name,
            'message':      message,
            'status':       'pending',
            'source':       'request',   # distinguishes from risk-alert auto-sessions
            'created_at':   now,
        })

        # Save the opening message as the first message in the sub-collection
        db.collection('counseling_sessions').document(new_ref.id)\
          .collection('messages').add({
              'sender':     student_name or uid,
              'sender_uid': uid,
              'role':       'student',
              'text':       body.get('message'),
              'timestamp':  now,
          })

        return jsonify({'success': True, 'session_id': new_ref.id,
                        'message': 'Counseling request sent!'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400


@app.route('/api/counseling/session', methods=['GET'])
def api_counseling_session():
    """Return the student's most recent non-closed counseling session."""
    try:
        uid, _, _ = verify_token(request, allowed_roles=['student'])

        # Look for active first, then pending, then declined
        for status in ('active', 'pending', 'declined'):
            docs = list(
                db.collection('counseling_sessions')
                  .where('student_uid', '==', uid)
                  .where('status', '==', status)
                  .order_by('created_at', direction='DESCENDING')
                  .limit(1)
                  .stream()
            )
            if docs:
                doc = docs[0]
                session = doc.to_dict()
                return jsonify({'success': True, 'session': {
                    'session_id': doc.id,
                    'status':     session.get('status'),
                    'created_at': session.get('created_at').isoformat()
                                  if hasattr(session.get('created_at'), 'isoformat') else None,
                }})

        return jsonify({'success': True, 'session': None})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400


@app.route('/api/session/<session_id>/messages', methods=['GET'])
def api_session_messages(session_id):
    """Return all messages for a session (student side)."""
    try:
        uid, _, _ = verify_token(request, allowed_roles=['student'])

        session_doc = db.collection('counseling_sessions').document(session_id).get()
        if not session_doc.exists:
            return jsonify({'success': False, 'message': 'Session not found'}), 404
        if session_doc.to_dict().get('student_uid') != uid:
            return jsonify({'success': False, 'message': 'Unauthorized'}), 403

        msgs_docs = db.collection('counseling_sessions').document(session_id)\
                      .collection('messages')\
                      .order_by('timestamp')\
                      .stream()

        messages = []
        for doc in msgs_docs:
            msg = doc.to_dict()
            ts = msg.get('timestamp')
            messages.append({
                'id':        doc.id,
                'sender':    msg.get('sender', ''),
                'role':      msg.get('role', ''),
                'text':      msg.get('text', ''),
                'timestamp': ts.isoformat() if hasattr(ts, 'isoformat') else None,
            })

        return jsonify({'success': True, 'messages': messages})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400


@app.route('/api/session/<session_id>/message', methods=['POST'])
def api_session_send_message(session_id):
    """Student sends a message in an active session."""
    try:
        uid, _, _ = verify_token(request, allowed_roles=['student'])
        body = request.get_json()
        text = (body.get('text') or '').strip()
        if not text:
            return jsonify({'success': False, 'message': 'Message text required'}), 400

        session_doc = db.collection('counseling_sessions').document(session_id).get()
        if not session_doc.exists:
            return jsonify({'success': False, 'message': 'Session not found'}), 404
        if session_doc.to_dict().get('student_uid') != uid:
            return jsonify({'success': False, 'message': 'Unauthorized'}), 403

        s_doc = db.collection('users').document(uid).get()
        student_name = ''
        if s_doc.exists:
            s = s_doc.to_dict()
            student_name = s.get('name') or s.get('displayName', '')

        now = datetime.now(timezone.utc)
        db.collection('counseling_sessions').document(session_id)\
          .collection('messages').add({
              'sender':     student_name or uid,
              'sender_uid': uid,
              'role':       'student',
              'text':       text,
              'timestamp':  now,
          })
        return jsonify({'success': True, 'message': 'Message sent!'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

# ─── API: RESOURCE LIBRARY ───────────────────────────────────────────────

@app.route('/api/resources', methods=['GET'])
def api_resources_list():
    """Return all resources published by counselors."""
    try:
        verify_token(request, allowed_roles=['student'])
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
            })
        return jsonify({'success': True, 'resources': resources})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400


# ─── PROFILE API ──────────────────────────────────────────────────────────

@app.route('/api/profile', methods=['GET'])
def api_profile_get():
    """Return the current student\'s profile data."""
    try:
        uid, _, _ = verify_token(request, allowed_roles=['student'])
        doc = db.collection('users').document(uid).get()
        if not doc.exists:
            return jsonify({'success': False, 'message': 'User not found'}), 404
        d = doc.to_dict()
        # Strip internal fields
        d.pop('disabled', None)
        d.pop('role', None)
        # Serialize timestamps
        for key in ('createdAt', 'updated_at'):
            if key in d and hasattr(d[key], 'isoformat'):
                d[key] = d[key].isoformat()
        return jsonify({'success': True, 'profile': d})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400


@app.route('/api/suggestions', methods=['GET'])
def api_suggestions():
    """Get personalized suggestions and stats based on weekly data and profile."""
    try:
        uid, _, _ = verify_token(request, allowed_roles=['student'])
        
        # Get user profile
        doc = db.collection('users').document(uid).get()
        if not doc.exists:
            return jsonify({'success': False, 'message': 'User not found'}), 404
        
        profile = doc.to_dict()
        baseline = profile.get('baseline', {})
        
        # Get weekly summary
        ws = week_start()
        
        def get_records(col):
            return [r.to_dict() for r in
                    db.collection('users').document(uid).collection(col)
                    .where('logged_at', '>=', ws).stream()]
        
        sleep_logs    = get_records('sleep_records')
        mood_logs     = get_records('mood_records')
        water_logs    = get_records('water_records')
        stress_logs   = get_records('stress_records')
        activity_logs = get_records('activity_records')
        steps_logs    = get_records('step_records')
        
        # Compute stats
        stats = {}
        
        # Sleep stats
        if sleep_logs:
            try:
                sleep_values = [float(r.get('total', '0').split()[0]) for r in sleep_logs if r.get('total')]
                if sleep_values:
                    avg_sleep = sum(sleep_values) / len(sleep_values)
                    stats['Avg Sleep'] = f"{avg_sleep:.1f} hrs"
            except:
                pass
        
        # Mood stats
        if mood_logs:
            try:
                mood_values = [float(r.get('mood', 0)) for r in mood_logs if r.get('mood')]
                if mood_values:
                    avg_mood = sum(mood_values) / len(mood_values)
                    stats['Avg Mood'] = f"{avg_mood:.1f}/5"
            except:
                pass
        
        # Water stats
        if water_logs:
            total_ml = sum(r.get('amount_ml', 0) for r in water_logs)
            stats['Total Water'] = f"{total_ml / 1000:.1f}L"
        
        # Activity stats
        if activity_logs:
            total_mins = sum(r.get('duration_mins', 0) for r in activity_logs)
            stats['Activity Time'] = f"{total_mins} mins"
        
        # Steps stats
        if steps_logs:
            total_steps = sum(r.get('steps', 0) for r in steps_logs)
            stats['Total Steps'] = f"{total_steps:,.0f}"
        
        # Generate suggestions
        suggestions = []
        
        # Sleep suggestions
        try:
            if sleep_logs:
                sleep_values = [float(r.get('total', '0').split()[0]) for r in sleep_logs if r.get('total')]
                if sleep_values:
                    avg_sleep = sum(sleep_values) / len(sleep_values)
                    baseline_sleep = baseline.get('sleep_hours', 7)
                    if avg_sleep < baseline_sleep - 1:
                        suggestions.append(f"Try to get closer to your {baseline_sleep}hr sleep goal. Avg this week: {avg_sleep:.1f}hrs")
        except:
            pass
        
        # Stress suggestions
        try:
            if stress_logs and len(stress_logs) >= 2:
                suggestions.append("Consider using stress management techniques. Check the resource library for help.")
        except:
            pass
        
        # Water suggestions
        try:
            if water_logs:
                total_ml = sum(r.get('amount_ml', 0) for r in water_logs)
                avg_daily = total_ml / 7 if water_logs else 0
                if avg_daily < 2000:
                    suggestions.append("Try to drink more water. Aim for at least 2L per day.")
        except:
            pass
        
        # Activity suggestions
        try:
            active_days = len(set(str(r.get('logged_at', '')).split(' ')[0] 
                                  for r in activity_logs if r.get('logged_at')))
            if active_days < 3:
                suggestions.append("Increase your physical activity. Aim for at least 3 days per week.")
        except:
            pass
        
        # Mood suggestions
        try:
            if mood_logs:
                mood_values = [float(r.get('mood', 0)) for r in mood_logs if r.get('mood')]
                if mood_values and sum(mood_values) / len(mood_values) < 2.5:
                    suggestions.append("Your mood seems low this week. Reach out to a counselor if needed.")
        except:
            pass
        
        if not suggestions:
            suggestions = ["Great job logging your health data this week! Keep it up."]
        
        return jsonify({'success': True, 'stats': stats, 'suggestions': suggestions})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400


@app.route('/api/profile', methods=['PUT'])
def api_profile_update():
    """Update editable profile fields."""
    try:
        uid, _, _ = verify_token(request, allowed_roles=['student'])
        body = request.get_json()

        allowed = {
            'displayName', 'dob', 'sex', 'height', 'weight',
            'baseline', 'goals', 'reminders'
        }
        updates = {k: v for k, v in body.items() if k in allowed}
        updates['updated_at'] = datetime.now(timezone.utc)

        db.collection('users').document(uid).update(updates)
        return jsonify({'success': True, 'message': 'Profile updated.'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

# ─── REMINDERS API ────────────────────────────────────────────────────────

@app.route('/api/reminders', methods=['GET'])
def api_reminders_get():
    """Get the student's reminder settings."""
    try:
        uid, _, _ = verify_token(request, allowed_roles=['student'])
        doc = db.collection('users').document(uid).get()
        if not doc.exists:
            return jsonify({'success': False, 'message': 'User not found'}), 404
        
        reminders = doc.to_dict().get('reminders', {})
        # Provide defaults if not set
        default_reminders = {
            'morning_checkin': {'enabled': True},
            'evening_mood_log': {'enabled': True},
            'hydration_nudge': {'enabled': True},
            'weekly_summary': {'enabled': True},
        }
        # Merge with user's settings
        for key in default_reminders:
            if key not in reminders:
                reminders[key] = default_reminders[key]
        
        return jsonify({'success': True, 'reminders': reminders})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400


@app.route('/api/reminders/update', methods=['POST'])
def api_reminders_update():
    """Update a specific reminder setting."""
    try:
        uid, _, _ = verify_token(request, allowed_roles=['student'])
        body = request.get_json(silent=True) or {}
        key = (body.get('key') or '').strip()
        enabled = body.get('enabled')
        
        if not key:
            return jsonify({'success': False, 'message': 'key is required'}), 400
        if enabled is None:
            return jsonify({'success': False, 'message': 'enabled is required'}), 400
        
        valid_keys = {'morning_checkin', 'evening_mood_log', 'hydration_nudge', 'weekly_summary'}
        if key not in valid_keys:
            return jsonify({'success': False, 'message': f'Invalid reminder key: {key}'}), 400
        
        # Get current reminders
        doc = db.collection('users').document(uid).get()
        reminders = doc.to_dict().get('reminders', {}) if doc.exists else {}
        
        # Update the specific reminder
        if key not in reminders:
            reminders[key] = {}
        reminders[key]['enabled'] = enabled
        
        # Save back to database
        db.collection('users').document(uid).set(
            {'reminders': reminders, 'updated_at': datetime.now(timezone.utc)},
            merge=True
        )
        
        return jsonify({'success': True, 'message': f'Reminder {key} {"enabled" if enabled else "disabled"}'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

# ─── ERROR HANDLERS ───────────────────────────────────────────────────────

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def server_error(error):
    """Handle 500 errors"""
    return jsonify({'error': 'Internal server error'}), 500

# ─── RUN APPLICATION ──────────────────────────────────────────────────────

if __name__ == '__main__':
    print(f"Starting Student Server on port {StudentConfig.PORT}...")
    app.run(host=StudentConfig.HOST, port=StudentConfig.PORT, debug=StudentConfig.DEBUG)