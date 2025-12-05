from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, Response, current_app
from flask_login import login_required, current_user
import secrets

from models import get_db_connection
from plagiarism_detector import check_plagiarism


faculty_bp = Blueprint('faculty', __name__, url_prefix='/faculty')


@faculty_bp.route('/assignments')
@login_required
def faculty_assignments():
    if current_user.role != 'faculty':
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('main.dashboard'))

    conn = get_db_connection()
    assignments = conn.execute(
        "SELECT * FROM assignments WHERE faculty_id = ?",
        (current_user.id,)
    ).fetchall()
    conn.close()
    return render_template('faculty_assignments_standalone.html', user=current_user, assignments=assignments)


@faculty_bp.route('/create_assignment', methods=['GET', 'POST'])
@login_required
def create_assignment():
    if current_user.role != 'faculty':
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        due_date = request.form.get('due_date')
        max_marks = request.form.get('max_marks', 100)
        category = request.form.get('category', 'General')
        instructions = request.form.get('instructions', '')

        if not title or len(title) < 3:
            flash('Title must be at least 3 characters long.', 'danger')
            return render_template('create_assignment.html', user=current_user)

        try:
            max_marks = int(max_marks)
            if max_marks <= 0:
                raise ValueError
        except (ValueError, TypeError):
            flash('Max marks must be a positive integer.', 'danger')
            return render_template('create_assignment.html', user=current_user)

        code = secrets.token_urlsafe(8)
        faculty_id = current_user.id

        conn = get_db_connection()
        try:
            conn.execute(
                "INSERT INTO assignments (title, description, code, faculty_id, due_date, max_marks, category, instructions) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (title, description, code, faculty_id, due_date, max_marks, category, instructions)
            )
            conn.commit()

            students = conn.execute("SELECT id FROM users WHERE role = 'student'").fetchall()
            for student in students:
                conn.execute(
                    "INSERT INTO notifications (user_id, title, message, type) VALUES (?, ?, ?, ?)",
                    (student['id'], 'New Assignment', f'New assignment "{title}" has been created.', 'info')
                )
            conn.commit()

            flash(f'Assignment "{title}" created successfully! Share code: {code}', 'success')
        except Exception:
            flash('Error creating assignment. Please try again.', 'danger')
        finally:
            conn.close()

        return redirect(url_for('faculty.faculty_assignments'))

    return render_template('create_assignment.html', user=current_user)


@faculty_bp.route('/assignments/<int:assignment_id>/submissions')
@login_required
def view_submissions(assignment_id):
    if current_user.role != 'faculty':
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('main.dashboard'))

    conn = get_db_connection()
    assignment = conn.execute(
        "SELECT * FROM assignments WHERE id = ? AND faculty_id = ?",
        (assignment_id, current_user.id)
    ).fetchone()

    if not assignment:
        flash('Assignment not found or you do not have permission to view it.', 'danger')
        conn.close()
        return redirect(url_for('faculty.faculty_assignments'))

    # Pagination and search
    page = request.args.get('page', default=1, type=int)
    per_page = 6
    q = request.args.get('q', default='', type=str).strip()

    # Build base query with optional search filter
    base_where = "WHERE s.assignment_id = ?"
    params = [assignment_id]
    if q:
        base_where += " AND (u.username LIKE ? OR s.content LIKE ?)"
        like = f"%{q}%"
        params.extend([like, like])

    # Count total for pagination
    total_row = conn.execute(
        f"SELECT COUNT(*) AS c FROM submissions s JOIN users u ON s.student_id = u.id {base_where}",
        tuple(params)
    ).fetchone()
    total = total_row['c'] if total_row else 0
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))
    offset = (page - 1) * per_page

    # Fetch current page submissions
    page_submissions = conn.execute(
        f"""
        SELECT s.*, u.username
        FROM submissions s
        JOIN users u ON s.student_id = u.id
        {base_where}
        ORDER BY s.submitted_at DESC, s.id DESC
        LIMIT ? OFFSET ?
        """,
        tuple(params + [per_page, offset])
    ).fetchall()

    # For plagiarism context, compare with all submissions of this assignment (not filtered by search/pagination)
    all_for_plagiarism = conn.execute(
        """
        SELECT s.id, s.content, u.username
        FROM submissions s
        JOIN users u ON s.student_id = u.id
        WHERE s.assignment_id = ?
        """,
        (assignment_id,)
    ).fetchall()

    submissions_with_reports = []
    if page_submissions and all_for_plagiarism:
        all_data = [{'id': sub['id'], 'content': sub['content'], 'username': sub['username']} for sub in all_for_plagiarism]
        for current_sub in page_submissions:
            document_to_check = current_sub['content']
            other_data = [sub for sub in all_data if sub['id'] != current_sub['id']]
            other_documents = [sub['content'] for sub in other_data]
            plagiarism_results = check_plagiarism(document_to_check, other_documents) if other_documents else []

            detailed_results = []
            if plagiarism_results:
                for j, result in enumerate(plagiarism_results):
                    detailed_results.append({
                        'similarity': result['similarity'],
                        'source_user': other_data[j]['username']
                    })

            overall_similarity = 0
            if plagiarism_results:
                scores = [float(res['similarity'].strip('%')) / 100 for res in plagiarism_results]
                if scores:
                    overall_similarity = max(scores)

            submissions_with_reports.append({
                'submission': current_sub,
                'plagiarism_report': detailed_results,
                'overall_similarity': int(overall_similarity * 100)
            })

    conn.close()
    return render_template(
        'view_submissions_standalone.html',
        user=current_user,
        assignment=assignment,
        submissions_with_reports=submissions_with_reports,
        page=page,
        total_pages=total_pages,
        total=total,
        q=q,
    )


@faculty_bp.route('/grade_submission/<int:submission_id>', methods=['POST'])
@login_required
def grade_submission(submission_id):
    if current_user.role != 'faculty':
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('main.dashboard'))

    grade = request.form.get('grade')
    feedback = request.form.get('feedback', '')

    try:
        grade = int(grade)
        if grade < 0 or grade > 100:
            raise ValueError
    except (ValueError, TypeError):
        flash('Grade must be a number between 0 and 100.', 'danger')
        return redirect(request.referrer)

    conn = get_db_connection()
    try:
        submission = conn.execute(
            "SELECT s.*, a.faculty_id FROM submissions s JOIN assignments a ON s.assignment_id = a.id WHERE s.id = ?",
            (submission_id,)
        ).fetchone()

        if not submission or submission['faculty_id'] != current_user.id:
            flash('Unauthorized access to this submission.', 'danger')
            return redirect(url_for('faculty.faculty_assignments'))

        conn.execute(
            "UPDATE submissions SET grade = ?, feedback = ?, status = 'graded' WHERE id = ?",
            (grade, feedback, submission_id)
        )

        conn.execute(
            "INSERT INTO notifications (user_id, title, message, type) VALUES (?, ?, ?, ?)",
            (submission['student_id'], 'Assignment Graded', f'Your assignment has been graded: {grade}/100', 'success')
        )

        conn.commit()
        flash('Submission graded successfully!', 'success')
    except Exception:
        flash('Error grading submission. Please try again.', 'danger')
    finally:
        conn.close()

    return redirect(request.referrer)



# -------------------- New Faculty Pages --------------------
@faculty_bp.route('/analytics')
@login_required
def analytics():
    if current_user.role != 'faculty':
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('main.dashboard'))

    conn = get_db_connection()
    try:
        total_assignments = conn.execute(
            "SELECT COUNT(*) AS c FROM assignments WHERE faculty_id = ?",
            (current_user.id,)
        ).fetchone()['c']

        total_submissions = conn.execute(
            """
            SELECT COUNT(*) AS c
            FROM submissions s
            JOIN assignments a ON s.assignment_id = a.id
            WHERE a.faculty_id = ?
            """,
            (current_user.id,)
        ).fetchone()['c']

        graded_submissions = conn.execute(
            """
            SELECT COUNT(*) AS c
            FROM submissions s
            JOIN assignments a ON s.assignment_id = a.id
            WHERE a.faculty_id = ? AND s.grade IS NOT NULL
            """,
            (current_user.id,)
        ).fetchone()['c']

        pending_reviews = max(0, total_submissions - graded_submissions)

        avg_grade_row = conn.execute(
            """
            SELECT AVG(s.grade) AS avg_grade
            FROM submissions s
            JOIN assignments a ON s.assignment_id = a.id
            WHERE a.faculty_id = ? AND s.grade IS NOT NULL
            """,
            (current_user.id,)
        ).fetchone()
        avg_grade = round(avg_grade_row['avg_grade'], 2) if avg_grade_row and avg_grade_row['avg_grade'] is not None else None

        # Top assignments by submissions
        top_assignments = conn.execute(
            """
            SELECT a.id, a.title, COUNT(s.id) AS submission_count
            FROM assignments a
            LEFT JOIN submissions s ON s.assignment_id = a.id
            WHERE a.faculty_id = ?
            GROUP BY a.id, a.title
            ORDER BY submission_count DESC
            LIMIT 5
            """,
            (current_user.id,)
        ).fetchall()

    finally:
        conn.close()

    return render_template(
        'faculty_analytics.html',
        user=current_user,
        total_assignments=total_assignments,
        total_submissions=total_submissions,
        graded_submissions=graded_submissions,
        pending_reviews=pending_reviews,
        avg_grade=avg_grade,
        top_assignments=top_assignments,
    )


@faculty_bp.route('/students')
@login_required
def students():
    if current_user.role != 'faculty':
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('main.dashboard'))

    conn = get_db_connection()
    try:
        # List students with counts of submissions to this faculty's assignments
        students = conn.execute(
            """
            SELECT u.id, u.username, u.email,
                   COUNT(DISTINCT s.id) AS submissions_count,
                   SUM(CASE WHEN s.grade IS NOT NULL THEN 1 ELSE 0 END) AS graded_count
            FROM users u
            LEFT JOIN submissions s ON s.student_id = u.id AND s.assignment_id IN (
                SELECT id FROM assignments WHERE faculty_id = ?
            )
            WHERE u.role = 'student'
            GROUP BY u.id, u.username, u.email
            ORDER BY submissions_count DESC, u.username ASC
            """,
            (current_user.id,)
        ).fetchall()
    finally:
        conn.close()

    return render_template('faculty_students.html', user=current_user, students=students)


@faculty_bp.route('/submission/<int:submission_id>')
@login_required
def submission_detail(submission_id):
    if current_user.role != 'faculty':
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('main.dashboard'))

    conn = get_db_connection()
    try:
        submission = conn.execute(
            """
            SELECT s.*, u.username AS student_username, a.title AS assignment_title, a.faculty_id, a.id AS assignment_id
            FROM submissions s
            JOIN users u ON s.student_id = u.id
            JOIN assignments a ON s.assignment_id = a.id
            WHERE s.id = ?
            """,
            (submission_id,)
        ).fetchone()

        if not submission or submission['faculty_id'] != current_user.id:
            flash('Unauthorized access to this submission.', 'danger')
            return redirect(url_for('faculty.faculty_assignments'))

        # Build plagiarism report for this submission vs others in same assignment
        others = conn.execute(
            """
            SELECT s.content, u.username
            FROM submissions s
            JOIN users u ON s.student_id = u.id
            WHERE s.assignment_id = ? AND s.id != ?
            """,
            (submission['assignment_id'], submission_id)
        ).fetchall()

        other_contents = [row['content'] for row in others]
        plagiarism_results = check_plagiarism(submission['content'], other_contents) if other_contents else []

        detailed_results = []
        if plagiarism_results:
            for idx, res in enumerate(plagiarism_results):
                detailed_results.append({
                    'similarity': res['similarity'],
                    'source_user': others[idx]['username']
                })

        overall_similarity = 0
        if plagiarism_results:
            scores = [float(r['similarity'].strip('%')) / 100 for r in plagiarism_results]
            if scores:
                overall_similarity = int(max(scores) * 100)

    finally:
        conn.close()

    return render_template(
        'submission_detail_standalone.html',
        user=current_user,
        submission=submission,
        plagiarism_report=detailed_results,
        overall_similarity=overall_similarity,
    )


@faculty_bp.route('/submission/<int:submission_id>/download')
@login_required
def download_submission(submission_id):
    if current_user.role != 'faculty':
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('main.dashboard'))

    conn = get_db_connection()
    try:
        row = conn.execute(
            """
            SELECT s.*, a.faculty_id, u.username
            FROM submissions s
            JOIN assignments a ON s.assignment_id = a.id
            JOIN users u ON s.student_id = u.id
            WHERE s.id = ?
            """,
            (submission_id,)
        ).fetchone()
        if not row or row['faculty_id'] != current_user.id:
            flash('Unauthorized access to this submission.', 'danger')
            return redirect(url_for('faculty.faculty_assignments'))

        # Try serving original uploaded file if available
        filename = row['file_name']
        if filename:
            import os
            base = current_app.config['UPLOAD_FOLDER']
            file_path = os.path.join(base, 'assignments', str(row['assignment_id']), 'students', str(row['student_id']), filename)
            if os.path.exists(file_path):
                return send_file(file_path, as_attachment=True, download_name=filename, mimetype=row['file_type'] or 'application/octet-stream')

        # Fallback to serving extracted text content
        content = row['content'] or ''
        filename = f"submission_{row['id']}_{row['username']}.txt"
    finally:
        conn.close()

    resp = Response(content, mimetype='text/plain; charset=utf-8')
    resp.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
    return resp


@faculty_bp.route('/submission/<int:submission_id>/file')
@login_required
def view_submission_file(submission_id):
    if current_user.role != 'faculty':
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('main.dashboard'))

    conn = get_db_connection()
    try:
        row = conn.execute(
            """
            SELECT s.*, a.faculty_id, u.username
            FROM submissions s
            JOIN assignments a ON s.assignment_id = a.id
            JOIN users u ON s.student_id = u.id
            WHERE s.id = ?
            """,
            (submission_id,)
        ).fetchone()

        if not row or row['faculty_id'] != current_user.id:
            flash('Unauthorized access to this submission.', 'danger')
            return redirect(url_for('faculty.faculty_assignments'))

        filename = row['file_name']
        if not filename:
            flash('No file uploaded with this submission.', 'warning')
            return redirect(url_for('faculty.submission_detail', submission_id=submission_id))

        import os
        base = current_app.config['UPLOAD_FOLDER']
        file_path = os.path.join(base, 'assignments', str(row['assignment_id']), 'students', str(row['student_id']), filename)
        if not os.path.exists(file_path):
            flash('File not found on server.', 'danger')
            return redirect(url_for('faculty.submission_detail', submission_id=submission_id))

        return send_file(file_path, as_attachment=False, download_name=filename, mimetype=row['file_type'] or 'application/octet-stream')
    finally:
        conn.close()

