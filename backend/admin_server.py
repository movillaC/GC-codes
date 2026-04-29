"""
ADMIN SERVER
Port: 5001

Handles admin login, signup, and all admin-specific routes and APIs
Only admins can access this server
"""
from flask import Flask, request, jsonify, render_template, redirect
from datetime import datetime
from config import AdminConfig
from db import (
    get_db, verify_token, get_user_role, user_exists, create_user,
    today_start, week_start
)
from firebase_admin import auth as firebase_auth

# ─── INITIALIZE APP ───────────────────────────────────────────────────────
app = Flask(__name__, template_folder='templates')
app.config.from_object(AdminConfig)

db = get_db()

# ─── AUTHENTICATION ROUTES ────────────────────────────────────────────────

@app.route('/')
def index():
    """Landing page"""
    return render_template('admin/Adminlanding.html')

@app.route('/login')
def login():
    """Admin login page"""
    return render_template('admin/Adminlogin.html')

@app.route('/signup')
def signup():
    """Admin signup page"""
    return render_template('admin/Adminsignup.html')

@app.route('/logout')
def logout():
    """Logout - redirect to login"""
    return redirect('/login')

# ─── ADMIN PAGE ROUTES ────────────────────────────────────────────────────

@app.route('/dashboard')
def dashboard():
    """Main admin dashboard"""
    return render_template('admin/AdminDashboard.html')

@app.route('/users')
def admin_users():
    """User management page"""
    return render_template('admin/Adminusers.html')

@app.route('/audit-logs')
def admin_audit_logs():
    """Audit logs page"""
    return render_template('admin/Adminauditlog.html')

@app.route('/system-config')
def admin_system_config():
    """System configuration page"""
    return render_template('admin/Adminsystemconfig.html')

@app.route('/backup')
def admin_backup():
    """Backup management page"""
    return render_template('admin/Adminbackup.html')

@app.route('/about')
def admin_about():
    """About page"""
    return render_template('admin/Adminabout.html')

@app.route('/contacts')
def admin_contacts():
    """Contacts page"""
    return render_template('admin/Admincontact.html')

# ─── ADMIN API ENDPOINTS ──────────────────────────────────────────────────

@app.route('/api/users/list', methods=['GET'])
def api_users_list():
    """Get all users (admin only)"""
    try:
        uid, _, _ = verify_token(request, allowed_roles=['admin'])
        
        # Fetch all users from database
        users = []
        docs = db.collection('users').stream()
        for doc in docs:
            user_data = doc.to_dict()
            users.append({
                'uid': user_data.get('uid'),
                'email': user_data.get('email'),
                'name': user_data.get('name', ''),
                'role': user_data.get('role', 'student'),
                'created_at': user_data.get('created_at'),
                'updated_at': user_data.get('updated_at')
            })
        
        return jsonify({'success': True, 'users': users})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@app.route('/api/users/<uid>', methods=['GET'])
def api_user_detail(uid):
    """Get user details (admin only)"""
    try:
        admin_uid, _, _ = verify_token(request, allowed_roles=['admin'])
        
        doc = db.collection('users').document(uid).get()
        if not doc.exists:
            return jsonify({'success': False, 'message': 'User not found'}), 404
        
        user_data = doc.to_dict()
        return jsonify({
            'success': True,
            'user': {
                'uid': user_data.get('uid'),
                'email': user_data.get('email'),
                'name': user_data.get('name', ''),
                'role': user_data.get('role', 'student'),
                'created_at': user_data.get('created_at'),
                'updated_at': user_data.get('updated_at')
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@app.route('/api/users/<uid>', methods=['DELETE'])
def api_user_delete(uid):
    """Delete a user (admin only)"""
    try:
        admin_uid, _, _ = verify_token(request, allowed_roles=['admin'])
        
        # Delete user from Firestore
        db.collection('users').document(uid).delete()
        
        # Log audit event
        db.collection('audit_logs').add({
            'admin_uid': admin_uid,
            'action': 'user_deleted',
            'target_uid': uid,
            'timestamp': datetime.now()
        })
        
        return jsonify({'success': True, 'message': 'User deleted successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@app.route('/api/audit-logs', methods=['GET'])
def api_audit_logs():
    """Get audit logs (admin only)"""
    try:
        uid, _, _ = verify_token(request, allowed_roles=['admin'])
        
        logs = []
        docs = db.collection('audit_logs').order_by('timestamp', direction='DESCENDING').limit(100).stream()
        for doc in docs:
            log_data = doc.to_dict()
            logs.append({
                'admin_uid': log_data.get('admin_uid'),
                'action': log_data.get('action'),
                'target_uid': log_data.get('target_uid', ''),
                'timestamp': log_data.get('timestamp')
            })
        
        return jsonify({'success': True, 'logs': logs})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@app.route('/api/system/config', methods=['GET'])
def api_system_config_get():
    """Get system configuration (admin only)"""
    try:
        uid, _, _ = verify_token(request, allowed_roles=['admin'])
        
        doc = db.collection('system_config').document('config').get()
        if doc.exists:
            return jsonify({'success': True, 'config': doc.to_dict()})
        
        return jsonify({'success': True, 'config': {}})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@app.route('/api/system/config', methods=['POST'])
def api_system_config_update():
    """Update system configuration (admin only)"""
    try:
        uid, _, _ = verify_token(request, allowed_roles=['admin'])
        body = request.get_json()
        
        db.collection('system_config').document('config').update({
            **body,
            'updated_at': datetime.now(),
            'updated_by': uid
        })
        
        # Log audit event
        db.collection('audit_logs').add({
            'admin_uid': uid,
            'action': 'system_config_updated',
            'timestamp': datetime.now()
        })
        
        return jsonify({'success': True, 'message': 'System configuration updated'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@app.route('/api/backup/create', methods=['POST'])
def api_backup_create():
    """Create backup (admin only)"""
    try:
        uid, _, _ = verify_token(request, allowed_roles=['admin'])
        
        # Record backup creation in audit logs
        db.collection('audit_logs').add({
            'admin_uid': uid,
            'action': 'backup_created',
            'timestamp': datetime.now()
        })
        
        db.collection('backups').add({
            'created_by': uid,
            'created_at': datetime.now(),
            'status': 'completed'
        })
        
        return jsonify({'success': True, 'message': 'Backup created successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@app.route('/api/backup/list', methods=['GET'])
def api_backup_list():
    """List backups (admin only)"""
    try:
        uid, _, _ = verify_token(request, allowed_roles=['admin'])
        
        backups = []
        docs = db.collection('backups').order_by('created_at', direction='DESCENDING').stream()
        for doc in docs:
            backup_data = doc.to_dict()
            backups.append({
                'id': doc.id,
                'created_by': backup_data.get('created_by'),
                'created_at': backup_data.get('created_at'),
                'status': backup_data.get('status')
            })
        
        return jsonify({'success': True, 'backups': backups})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400


@app.route('/api/stats', methods=['GET'])
def api_stats():
    """Get admin dashboard stats"""
    try:
        uid, _, _ = verify_token(request, allowed_roles=['admin'])
        users = list(db.collection('users').stream())
        students   = sum(1 for u in users if u.to_dict().get('role') == 'student')
        counselors = sum(1 for u in users if u.to_dict().get('role') == 'counselor')
        admins     = sum(1 for u in users if u.to_dict().get('role') == 'admin')
        sessions   = list(db.collection('counseling_sessions').stream())
        return jsonify({'success': True, 'stats': {
            'total_users': len(users),
            'students': students,
            'counselors': counselors,
            'admins': admins,
            'total_sessions': len(sessions)
        }})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@app.route('/api/users/create', methods=['POST'])
def api_users_create():
    """Create a new user (admin only)"""
    try:
        admin_uid, _, _ = verify_token(request, allowed_roles=['admin'])
        body = request.get_json()
        email    = body.get('email')
        password = body.get('password')
        role     = body.get('role', 'student')
        name     = body.get('name', '')
        user = firebase_auth.create_user(email=email, password=password, display_name=name)
        db.collection('users').document(user.uid).set({
            'uid': user.uid, 'email': email, 'displayName': name,
            'role': role, 'disabled': False,
            'createdAt': datetime.now(), 'updated_at': datetime.now()
        })
        db.collection('audit_logs').add({
            'admin_uid': admin_uid, 'action': 'user_created',
            'target_uid': user.uid, 'timestamp': datetime.now()
        })
        return jsonify({'success': True, 'message': 'User created successfully', 'uid': user.uid})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@app.route('/api/users/delete', methods=['POST'])
def api_users_delete():
    """Delete a user (admin only)"""
    try:
        admin_uid, _, _ = verify_token(request, allowed_roles=['admin'])
        uid = request.get_json().get('uid')
        firebase_auth.delete_user(uid)
        db.collection('users').document(uid).delete()
        db.collection('audit_logs').add({
            'admin_uid': admin_uid, 'action': 'user_deleted',
            'target_uid': uid, 'timestamp': datetime.now()
        })
        return jsonify({'success': True, 'message': 'User deleted successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@app.route('/api/users/ban', methods=['POST'])
def api_users_ban():
    """Ban or unban a user (admin only)"""
    try:
        admin_uid, _, _ = verify_token(request, allowed_roles=['admin'])
        body    = request.get_json()
        uid     = body.get('uid')
        disable = body.get('disable', True)
        firebase_auth.update_user(uid, disabled=disable)
        db.collection('users').document(uid).update({'disabled': disable, 'updated_at': datetime.now()})
        action = 'user_banned' if disable else 'user_unbanned'
        db.collection('audit_logs').add({
            'admin_uid': admin_uid, 'action': action,
            'target_uid': uid, 'timestamp': datetime.now()
        })
        return jsonify({'success': True, 'message': f"User {'banned' if disable else 'unbanned'} successfully"})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@app.route('/api/backup/restore', methods=['POST'])
def api_backup_restore():
    """Restore backup (admin only) - logs the action"""
    try:
        uid = verify_token(request, allowed_roles=['admin'])[0]
        backup_id = request.get_json().get('backup_id')
        db.collection('audit_logs').add({
            'admin_uid': uid, 'action': 'backup_restored',
            'target_uid': backup_id, 'timestamp': datetime.now()
        })
        return jsonify({'success': True, 'message': 'Restore request logged'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@app.route('/api/backup/schedule', methods=['POST'])
def api_backup_schedule():
    """Schedule a backup (admin only)"""
    try:
        uid  = verify_token(request, allowed_roles=['admin'])[0]
        body = request.get_json()
        db.collection('system_config').document('config').set(
            {'backup_schedule': body.get('schedule'), 'updated_by': uid, 'updated_at': datetime.now()},
            merge=True
        )
        return jsonify({'success': True, 'message': 'Backup schedule updated'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@app.route('/api/system/danger/<action>', methods=['POST'])
def api_system_danger(action):
    """Danger zone system actions (admin only)"""
    try:
        uid = verify_token(request, allowed_roles=['admin'])[0]
        db.collection('audit_logs').add({
            'admin_uid': uid, 'action': f'danger_zone_{action}',
            'timestamp': datetime.now()
        })
        return jsonify({'success': True, 'message': f'Action {action} logged'})
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
    print(f"Starting Admin Server on port {AdminConfig.PORT}...")
    app.run(host=AdminConfig.HOST, port=AdminConfig.PORT, debug=AdminConfig.DEBUG)