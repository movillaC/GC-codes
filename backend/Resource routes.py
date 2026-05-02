# ─── API: RESOURCE LIBRARY ───────────────────────────────────────────────
# Add these routes to your consultant_server.py
# Also add the page route:
#
#   @app.route('/resources')
#   def counselor_resources():
#       return render_template('counselor/CounselorResources.html')
#
# And for the student server, add:
#
#   @app.route('/resource-library')
#   def student_resource_library():
#       return render_template('student/StudentResourceLibrary.html')
#
# Both servers need the GET /api/resources route.
# Only the counselor server needs POST, PUT, DELETE.

@app.route('/api/resources', methods=['GET'])
def api_resources_list():
    """Return all resources. Accessible by both students and counselors."""
    try:
        verify_token(request)  # any authenticated user

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
                'created_by':  r.get('created_by', ''),
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

        if not title:
            return _err('title is required')
        if not category:
            return _err('category is required')
        if not description:
            return _err('description is required')

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