"""
CONSULTANT/COUNSELOR SERVER
Port: 5002

Handles counselor login, signup, and all counselor-specific routes and APIs
Only counselors can access this server
"""
from flask import Flask, request, jsonify, render_template, redirect
from datetime import datetime
from config import ConsultantConfig
from db import (
    get_db, verify_token, get_user_role, user_exists, create_user,
    today_start, week_start
)
from firebase_admin import auth as firebase_auth

# ─── INITIALIZE APP ───────────────────────────────────────────────────────
app = Flask(__name__, template_folder='templates')
app.config.from_object(ConsultantConfig)

db = get_db()

# ─── AUTHENTICATION ROUTES ────────────────────────────────────────────────

@app.route('/')
def index():
    """Landing page"""
    return render_template('counselor/Counselorlanding.html')

@app.route('/login')
def login():
    """Counselor login page"""
    return render_template('counselor/Counselorlogin.html')

@app.route('/signup')
def signup():
    """Counselor signup page"""
    return render_template('counselor/Counselorsignup.html')

@app.route('/logout')
def logout():
    """Logout - redirect to login"""
    return redirect('/login')

# ─── COUNSELOR PAGE ROUTES ────────────────────────────────────────────────

@app.route('/dashboard')
def dashboard():
    """Main counselor dashboard"""
    return render_template('counselor/CounselorDashboard.html')

@app.route('/students')
def counselor_students():
    """Student management page"""
    return render_template('counselor/Counselorstudents.html')

@app.route('/requests')
def counselor_requests():
    """Counseling requests page"""
    return render_template('counselor/Counselorrequest.html')

@app.route('/sessions')
def counselor_sessions():
    """Counseling sessions page"""
    return render_template('counselor/Counselorsessions.html')

@app.route('/case-notes')
def counselor_case_notes():
    """Case notes page"""
    return render_template('counselor/Counselorcasenote.html')

@app.route('/risk-alerts')
def counselor_risk_alerts():
    """Risk alerts page"""
    return render_template('counselor/Counselorriskalert.html')

@app.route('/about')
def counselor_about():
    """About page"""
    return render_template('counselor/Counselorabout.html')

@app.route('/contacts')
def counselor_contacts():
    """Contacts page"""
    return render_template('counselor/Counselorcontact.html')

# ─── COUNSELOR API ENDPOINTS ──────────────────────────────────────────────

@app.route('/api/students', methods=['GET'])
def api_students_list():
    """Get all students assigned to counselor"""
    try:
        counselor_uid, _, _ = verify_token(request, allowed_roles=['consultant'])
        
        # Get counselor's assigned students
        students = []
        docs = db.collection('counselor_assignments').where('counselor_uid', '==', counselor_uid).stream()
        
        for doc in docs:
            assignment = doc.to_dict()
            student_uid = assignment.get('student_uid')
            
            # Fetch student details
            student_doc = db.collection('users').document(student_uid).get()
            if student_doc.exists:
                student_data = student_doc.to_dict()
                students.append({
                    'uid': student_data.get('uid'),
                    'email': student_data.get('email'),
                    'name': student_data.get('name', ''),
                    'assigned_at': assignment.get('assigned_at')
                })
        
        return jsonify({'success': True, 'students': students})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@app.route('/api/requests', methods=['GET'])
def api_counseling_requests():
    """Get pending counseling requests"""
    try:
        counselor_uid, _, _ = verify_token(request, allowed_roles=['consultant'])
        
        requests = []
        docs = db.collection('counseling_sessions').where('status', '==', 'pending').stream()
        
        for doc in docs:
            session = doc.to_dict()
            requests.append({
                'session_id': doc.id,
                'student_uid': session.get('student_uid'),
                'message': session.get('message'),
                'created_at': session.get('created_at')
            })
        
        return jsonify({'success': True, 'requests': requests})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@app.route('/api/sessions', methods=['GET'])
def api_sessions_list():
    """Get all active counseling sessions"""
    try:
        counselor_uid, _, _ = verify_token(request, allowed_roles=['consultant'])
        
        sessions = []
        docs = db.collection('counseling_sessions').where('status', '==', 'active').stream()
        
        for doc in docs:
            session = doc.to_dict()
            sessions.append({
                'session_id': doc.id,
                'student_uid': session.get('student_uid'),
                'status': session.get('status'),
                'created_at': session.get('created_at')
            })
        
        return jsonify({'success': True, 'sessions': sessions})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@app.route('/api/session/<session_id>/messages', methods=['GET'])
def api_session_messages(session_id):
    """Get messages from a counseling session"""
    try:
        counselor_uid, _, _ = verify_token(request, allowed_roles=['consultant'])
        
        messages = []
        docs = db.collection('counseling_sessions').document(session_id)\
                 .collection('messages').order_by('timestamp').stream()
        
        for doc in docs:
            msg = doc.to_dict()
            messages.append({
                'sender': msg.get('sender'),
                'role': msg.get('role'),
                'text': msg.get('text'),
                'timestamp': msg.get('timestamp')
            })
        
        return jsonify({'success': True, 'messages': messages})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@app.route('/api/session/<session_id>/accept', methods=['POST'])
def api_session_accept(session_id):
    """Accept a counseling request"""
    try:
        counselor_uid, _, _ = verify_token(request, allowed_roles=['consultant'])
        
        db.collection('counseling_sessions').document(session_id).update({
            'status': 'active',
            'counselor_uid': counselor_uid,
            'accepted_at': datetime.now()
        })
        
        return jsonify({'success': True, 'message': 'Session accepted'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@app.route('/api/session/<session_id>/close', methods=['POST'])
def api_session_close(session_id):
    """Close a counseling session"""
    try:
        counselor_uid, _, _ = verify_token(request, allowed_roles=['consultant'])
        
        db.collection('counseling_sessions').document(session_id).update({
            'status': 'closed',
            'closed_at': datetime.now()
        })
        
        return jsonify({'success': True, 'message': 'Session closed'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@app.route('/api/case-note', methods=['POST'])
def api_case_note_create():
    """Create a case note"""
    try:
        counselor_uid, _, _ = verify_token(request, allowed_roles=['consultant'])
        body = request.get_json()
        
        db.collection('case_notes').add({
            'counselor_uid': counselor_uid,
            'student_uid': body.get('student_uid'),
            'note': body.get('note'),
            'created_at': datetime.now()
        })
        
        return jsonify({'success': True, 'message': 'Case note saved'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@app.route('/api/case-notes/<student_uid>', methods=['GET'])
def api_case_notes_list(student_uid):
    """Get all case notes for a student"""
    try:
        counselor_uid, _, _ = verify_token(request, allowed_roles=['consultant'])
        
        notes = []
        docs = db.collection('case_notes').where('student_uid', '==', student_uid).stream()
        
        for doc in docs:
            note = doc.to_dict()
            notes.append({
                'id': doc.id,
                'counselor_uid': note.get('counselor_uid'),
                'note': note.get('note'),
                'created_at': note.get('created_at')
            })
        
        return jsonify({'success': True, 'notes': notes})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@app.route('/api/risk-alert', methods=['POST'])
def api_risk_alert_create():
    """Create a risk alert for a student"""
    try:
        counselor_uid, _, _ = verify_token(request, allowed_roles=['consultant'])
        body = request.get_json()
        
        db.collection('risk_alerts').add({
            'counselor_uid': counselor_uid,
            'student_uid': body.get('student_uid'),
            'level': body.get('level'),  # low, medium, high
            'description': body.get('description'),
            'created_at': datetime.now()
        })
        
        return jsonify({'success': True, 'message': 'Risk alert created'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@app.route('/api/risk-alerts', methods=['GET'])
def api_risk_alerts_list():
    """Get all active risk alerts"""
    try:
        counselor_uid, _, _ = verify_token(request, allowed_roles=['consultant'])
        
        alerts = []
        docs = db.collection('risk_alerts').where('resolved', '==', False).stream()
        
        for doc in docs:
            alert = doc.to_dict()
            alerts.append({
                'id': doc.id,
                'student_uid': alert.get('student_uid'),
                'level': alert.get('level'),
                'description': alert.get('description'),
                'created_at': alert.get('created_at')
            })
        
        return jsonify({'success': True, 'alerts': alerts})
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
    print(f"Starting Consultant Server on port {ConsultantConfig.PORT}...")
    app.run(host=ConsultantConfig.HOST, port=ConsultantConfig.PORT, debug=ConsultantConfig.DEBUG)
