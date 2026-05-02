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

        users = []
        docs = db.collection('users').stream()
        for doc in docs:
            user_data = doc.to_dict()
            disabled = user_data.get('disabled', False)
            users.append({
                'uid': user_data.get('uid'),
                'email': user_data.get('email'),
                'name': user_data.get('displayName', user_data.get('name', '')),
                'role': user_data.get('role', 'student'),
                'created': str(user_data.get('createdAt', user_data.get('created_at', ''))),
                'updated_at': str(user_data.get('updated_at', '')),
                'disabled': disabled,
                'status': 'banned' if disabled else 'active',
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
        disabled = user_data.get('disabled', False)
        return jsonify({
            'success': True,
            'user': {
                'uid': user_data.get('uid'),
                'email': user_data.get('email'),
                'name': user_data.get('displayName', user_data.get('name', '')),
                'role': user_data.get('role', 'student'),
                'created': str(user_data.get('createdAt', user_data.get('created_at', ''))),
                'updated_at': str(user_data.get('updated_at', '')),
                'disabled': disabled,
                'status': 'banned' if disabled else 'active',
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400


@app.route('/api/users/<uid>', methods=['DELETE'])
def api_user_delete(uid):
    """Delete a user (admin only) — DELETE variant"""
    try:
        admin_uid, _, _ = verify_token(request, allowed_roles=['admin'])

        try:
            firebase_auth.delete_user(uid)
        except firebase_auth.UserNotFoundError:
            pass

        db.collection('users').document(uid).delete()

        db.collection('audit_logs').add({
            'admin_uid': admin_uid,
            'action': 'user_deleted',
            'target_uid': uid,
            'user': admin_uid,
            'target': uid,
            'severity': 'warning',
            'ip': request.remote_addr,
            'timestamp': datetime.now().isoformat(),
        })

        return jsonify({'success': True, 'message': 'User deleted successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400


@app.route('/api/audit-logs', methods=['GET'])
def api_audit_logs():
    """Get audit logs (admin only)"""
    try:
        uid, _, _ = verify_token(request, allowed_roles=['admin'])

        from google.cloud import firestore
        logs = []
        docs = (
            db.collection('audit_logs')
            .order_by('timestamp', direction=firestore.Query.DESCENDING)
            .limit(500)
            .stream()
        )
        for doc in docs:
            log_data = doc.to_dict()
            logs.append({
                'timestamp': log_data.get('timestamp', ''),
                'severity': log_data.get('severity', 'info'),
                'action': log_data.get('action', '—'),
                'user': log_data.get('user', log_data.get('admin_uid', '—')),
                'target': log_data.get('target', log_data.get('target_uid', '—')),
                'ip': log_data.get('ip', '—'),
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
        if not body:
            return jsonify({'success': False, 'message': 'No data provided'}), 400

        db.collection('system_config').document('config').set(
            {**body, 'updated_at': datetime.now().isoformat(), 'updated_by': uid},
            merge=True
        )

        db.collection('audit_logs').add({
            'admin_uid': uid,
            'action': 'system_config_updated',
            'user': uid,
            'severity': 'info',
            'ip': request.remote_addr,
            'timestamp': datetime.now().isoformat(),
        })

        return jsonify({'success': True, 'message': 'System configuration updated'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400


@app.route('/api/backup/create', methods=['POST'])
def api_backup_create():
    """Create backup (admin only)"""
    try:
        uid, _, _ = verify_token(request, allowed_roles=['admin'])

        db.collection('backups').add({
            'created_by': uid,
            'created_at': datetime.now().isoformat(),
            'status': 'completed',
        })

        db.collection('audit_logs').add({
            'admin_uid': uid,
            'action': 'backup_created',
            'user': uid,
            'severity': 'info',
            'ip': request.remote_addr,
            'timestamp': datetime.now().isoformat(),
        })

        return jsonify({
            'success': True,
            'message': 'Backup created successfully',
            'backup': {'status': 'completed', 'created_at': datetime.now().isoformat()},
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400


@app.route('/api/backup/list', methods=['GET'])
def api_backup_list():
    """List backups (admin only)"""
    try:
        uid, _, _ = verify_token(request, allowed_roles=['admin'])

        from google.cloud import firestore
        backups = []
        docs = (
            db.collection('backups')
            .order_by('created_at', direction=firestore.Query.DESCENDING)
            .stream()
        )
        for doc in docs:
            backup_data = doc.to_dict()
            backups.append({
                'id': doc.id,
                'created_by': backup_data.get('created_by'),
                'datetime': backup_data.get('created_at', ''),
                'created_at': backup_data.get('created_at', ''),
                'status': backup_data.get('status', 'success'),
                'type': backup_data.get('type', 'Full'),
                'size': backup_data.get('size', '—'),
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
        alerts     = sum(1 for u in users if u.to_dict().get('disabled', False))

        return jsonify({
            'success': True,
            'total_users': len(users),
            'students': students,
            'counselors': counselors,
            'admins': admins,
            'alerts': alerts,
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400


@app.route('/api/users/create', methods=['POST'])
def api_users_create():
    """Create a new user (admin only)"""
    try:
        admin_uid, _, _ = verify_token(request, allowed_roles=['admin'])
        body = request.get_json()
        if not body:
            return jsonify({'success': False, 'message': 'No data provided'}), 400

        email    = body.get('email')
        password = body.get('password')
        role     = body.get('role', 'student')
        name     = body.get('name', '')

        if not email or not password:
            return jsonify({'success': False, 'message': 'Email and password are required'}), 400

        user = firebase_auth.create_user(email=email, password=password, display_name=name)
        db.collection('users').document(user.uid).set({
            'uid': user.uid,
            'email': email,
            'displayName': name,
            'role': role,
            'disabled': False,
            'createdAt': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat(),
        })
        db.collection('audit_logs').add({
            'admin_uid': admin_uid,
            'action': 'user_created',
            'target_uid': user.uid,
            'user': admin_uid,
            'target': user.uid,
            'severity': 'info',
            'ip': request.remote_addr,
            'timestamp': datetime.now().isoformat(),
        })
        return jsonify({'success': True, 'message': 'User created successfully', 'uid': user.uid})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400


@app.route('/api/users/delete', methods=['POST'])
def api_users_delete():
    """Delete a user (admin only) — POST variant used by the frontend"""
    try:
        admin_uid, _, _ = verify_token(request, allowed_roles=['admin'])
        body = request.get_json()
        if not body:
            return jsonify({'success': False, 'message': 'No data provided'}), 400

        uid = body.get('uid')
        if not uid:
            return jsonify({'success': False, 'message': 'uid is required'}), 400

        try:
            firebase_auth.delete_user(uid)
        except firebase_auth.UserNotFoundError:
            pass

        db.collection('users').document(uid).delete()
        db.collection('audit_logs').add({
            'admin_uid': admin_uid,
            'action': 'user_deleted',
            'target_uid': uid,
            'user': admin_uid,
            'target': uid,
            'severity': 'warning',
            'ip': request.remote_addr,
            'timestamp': datetime.now().isoformat(),
        })
        return jsonify({'success': True, 'message': 'User deleted successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400


@app.route('/api/users/edit', methods=['POST'])
def api_users_edit():
    """Update a user's name and/or role (admin only)"""
    try:
        admin_uid, _, _ = verify_token(request, allowed_roles=['admin'])
        body = request.get_json()
        if not body:
            return jsonify({'success': False, 'message': 'No data provided'}), 400

        uid = body.get('uid', '').strip()
        if not uid:
            return jsonify({'success': False, 'message': 'uid is required'}), 400

        doc = db.collection('users').document(uid).get()
        if not doc.exists:
            return jsonify({'success': False, 'message': 'User not found'}), 404

        updates = {'updated_at': datetime.now().isoformat()}

        if 'role' in body:
            if body['role'] not in ('student', 'counselor', 'admin'):
                return jsonify({'success': False, 'message': 'Invalid role'}), 400
            updates['role'] = body['role']

        if 'name' in body:
            updates['displayName'] = (body['name'] or '').strip()
            try:
                firebase_auth.update_user(uid, display_name=updates['displayName'] or None)
            except Exception:
                pass

        db.collection('users').document(uid).update(updates)
        db.collection('audit_logs').add({
            'admin_uid': admin_uid,
            'action': 'user_edited',
            'target_uid': uid,
            'user': admin_uid,
            'target': uid,
            'severity': 'info',
            'ip': request.remote_addr,
            'timestamp': datetime.now().isoformat(),
        })
        return jsonify({'success': True, 'message': 'User updated successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400


@app.route('/api/users/ban', methods=['POST'])
def api_users_ban():
    """Ban or unban a user (admin only)"""
    try:
        admin_uid, _, _ = verify_token(request, allowed_roles=['admin'])
        body = request.get_json()
        if not body:
            return jsonify({'success': False, 'message': 'No data provided'}), 400

        uid     = body.get('uid')
        disable = body.get('disable', True)

        firebase_auth.update_user(uid, disabled=disable)
        db.collection('users').document(uid).update({
            'disabled': disable,
            'updated_at': datetime.now().isoformat(),
        })
        action = 'user_banned' if disable else 'user_unbanned'
        db.collection('audit_logs').add({
            'admin_uid': admin_uid,
            'action': action,
            'target_uid': uid,
            'user': admin_uid,
            'target': uid,
            'severity': 'warning',
            'ip': request.remote_addr,
            'timestamp': datetime.now().isoformat(),
        })
        return jsonify({'success': True, 'message': f"User {'banned' if disable else 'unbanned'} successfully"})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400


@app.route('/api/backup/restore', methods=['POST'])
def api_backup_restore():
    """Restore backup (admin only) - logs the action"""
    try:
        uid = verify_token(request, allowed_roles=['admin'])[0]
        body = request.get_json()
        backup_id = body.get('backup_id') if body else None
        db.collection('audit_logs').add({
            'admin_uid': uid,
            'action': 'backup_restored',
            'target_uid': backup_id,
            'user': uid,
            'target': backup_id or '—',
            'severity': 'warning',
            'ip': request.remote_addr,
            'timestamp': datetime.now().isoformat(),
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
            {
                'backup_schedule': body.get('schedule') if body else None,
                'updated_by': uid,
                'updated_at': datetime.now().isoformat(),
            },
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
            'admin_uid': uid,
            'action': f'danger_zone_{action}',
            'user': uid,
            'severity': 'critical',
            'ip': request.remote_addr,
            'timestamp': datetime.now().isoformat(),
        })
        return jsonify({'success': True, 'message': f'Action {action} logged'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400


# ─── ERROR HANDLERS ───────────────────────────────────────────────────────

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def server_error(error):
    return jsonify({'error': 'Internal server error'}), 500

# ─── RUN APPLICATION ──────────────────────────────────────────────────────

if __name__ == '__main__':
    print(f"Starting Admin Server on port {AdminConfig.PORT}...")
    app.run(host=AdminConfig.HOST, port=AdminConfig.PORT, debug=AdminConfig.DEBUG)