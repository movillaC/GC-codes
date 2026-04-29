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
        body = request.get_json()
        sleep_time = body.get('sleep_time')
        wake_time = body.get('wake_time')

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
        return jsonify({'success': True, 'total': total, 'message': 'Sleep record saved!'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@app.route('/api/water', methods=['POST'])
def api_water():
    """Log water intake"""
    try:
        uid, _, _ = verify_token(request, allowed_roles=['student'])
        body = request.get_json()
        amount_ml = int(body.get('amount_ml', 0))

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

        return jsonify({'success': True, 'total_liters': total_liters, 'percentage': percentage})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@app.route('/api/mood', methods=['POST'])
def api_mood():
    """Log mood data"""
    try:
        uid, _, _ = verify_token(request, allowed_roles=['student'])
        body = request.get_json()
        db.collection('users').document(uid).collection('mood_records').add({
            'mood': body.get('mood'),
            'note': body.get('note', ''),
            'logged_at': datetime.now(timezone.utc)
        })
        return jsonify({'success': True, 'message': 'Mood logged!'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@app.route('/api/stress', methods=['POST'])
def api_stress():
    """Log stress data"""
    try:
        uid, _, _ = verify_token(request, allowed_roles=['student'])
        body = request.get_json()
        db.collection('users').document(uid).collection('stress_records').add({
            'note': body.get('note'),
            'stressor': body.get('stressor'),
            'logged_at': datetime.now(timezone.utc)
        })
        return jsonify({'success': True, 'message': 'Stress note saved!'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@app.route('/api/activity', methods=['POST'])
def api_activity():
    """Log activity data"""
    try:
        uid, _, _ = verify_token(request, allowed_roles=['student'])
        body = request.get_json()
        duration_mins = int(body.get('duration_mins', 0))

        db.collection('users').document(uid).collection('activity_records').add({
            'activity': body.get('activity'),
            'duration_mins': duration_mins,
            'logged_at': datetime.now(timezone.utc)
        })

        # Calculate today's total
        records = db.collection('users').document(uid).collection('activity_records')\
                      .where('logged_at', '>=', today_start()).stream()
        total_mins = sum(r.to_dict().get('duration_mins', 0) for r in records)
        percentage = min(round((total_mins / 60) * 100), 100)

        return jsonify({'success': True, 'total_mins': total_mins, 'percentage': percentage})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@app.route('/api/steps', methods=['POST'])
def api_steps():
    """Log steps data"""
    try:
        uid, _, _ = verify_token(request, allowed_roles=['student'])
        body = request.get_json()
        steps = int(body.get('steps', 0))

        db.collection('users').document(uid).collection('step_records').add({
            'steps': steps,
            'logged_at': datetime.now(timezone.utc)
        })

        # Calculate today's total
        records = db.collection('users').document(uid).collection('step_records')\
                        .where('logged_at', '>=', today_start()).stream()
        total_steps = sum(r.to_dict().get('steps', 0) for r in records)
        percentage = min(round((total_steps / 10000) * 100), 100)

        return jsonify({'success': True, 'total_steps': total_steps, 'percentage': percentage})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

# ─── DASHBOARD SUMMARY APIS ───────────────────────────────────────────────

@app.route('/api/summary/today', methods=['GET'])
def today_summary():
    """Get today's summary"""
    try:
        uid, _, _ = verify_token(request, allowed_roles=['student'])
        ts = today_start()

        def latest(col):
            return [r.to_dict() for r in
                    db.collection('users').document(uid).collection(col)
                    .where('logged_at', '>=', ts).stream()]

        sleep = latest('sleep_records')
        mood = latest('mood_records')
        water = latest('water_records')
        stress = latest('stress_records')
        activity = latest('activity_records')
        steps = latest('step_records')

        return jsonify({
            'success': True,
            'summary': {
                'mood': mood[-1]['mood'] if mood else '--',
                'sleep': sleep[-1]['total'] if sleep else '0 hrs',
                'water_liters': round(sum(r.get('amount_ml', 0) for r in water) / 1000, 1),
                'stress': 'Logged' if stress else 'None',
                'activity_mins': sum(r.get('duration_mins', 0) for r in activity),
                'steps': sum(r.get('steps', 0) for r in steps)
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@app.route('/api/summary/weekly', methods=['GET'])
def weekly_summary_api():
    """Get weekly summary"""
    try:
        uid, _, _ = verify_token(request, allowed_roles=['student'])
        ws = week_start()

        def get_records(col):
            return [r.to_dict() for r in
                    db.collection('users').document(uid).collection(col)
                    .where('logged_at', '>=', ws).stream()]

        return jsonify({'success': True, 'summary': {
            'sleep': get_records('sleep_records'),
            'mood': get_records('mood_records'),
            'water': get_records('water_records'),
            'stress': get_records('stress_records'),
            'activity': get_records('activity_records'),
            'steps': get_records('step_records'),
        }})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

# ─── COUNSELING REQUEST API ───────────────────────────────────────────────

@app.route('/api/counseling/request', methods=['POST'])
def api_counseling_request():
    """Request counseling session"""
    try:
        uid, _, _ = verify_token(request, allowed_roles=['student'])
        body = request.get_json()
        db.collection('counseling_sessions').add({
            'student_uid': uid,
            'message': body.get('message'),
            'status': 'pending',
            'created_at': datetime.now(timezone.utc)
        })
        return jsonify({'success': True, 'message': 'Counseling request sent!'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@app.route('/api/counseling/message', methods=['POST'])
def api_counseling_message():
    """Send counseling message"""
    try:
        uid, decoded, role = verify_token(request, allowed_roles=['student'])
        body = request.get_json()
        session_id = body.get('session_id')
        db.collection('counseling_sessions').document(session_id)\
          .collection('messages').add({
            'sender': uid,
            'role': role,
            'text': body.get('text'),
            'timestamp': datetime.now(timezone.utc)
        })
        return jsonify({'success': True, 'message': 'Message sent!'})
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