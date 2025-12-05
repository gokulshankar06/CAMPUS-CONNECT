from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
import docx
import PyPDF2
import os

from models import get_db_connection
from plagiarism_detector import check_plagiarism
from utils import allowed_file


student_bp = Blueprint('student', __name__, url_prefix='/student')


@student_bp.route('/assignments')
@login_required
def student_assignments():
    if current_user.role != 'student':
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('main.dashboard'))

    conn = get_db_connection()
    assignments = conn.execute(
        "SELECT a.*, u.username AS faculty_name FROM assignments a JOIN users u ON a.faculty_id = u.id"
    ).fetchall()
    conn.close()
    return render_template('student_assignments_standalone.html', user=current_user, assignments=assignments)


@student_bp.route('/assignment/<int:assignment_id>', methods=['GET', 'POST'])
@login_required
def assignment_submission(assignment_id):
    if current_user.role != 'student':
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('main.dashboard'))

    conn = get_db_connection()
    assignment = conn.execute("SELECT * FROM assignments WHERE id = ?", (assignment_id,)).fetchone()

    if not assignment:
        flash('Invalid assignment.', 'danger')
        conn.close()
        return redirect(url_for('student.student_assignments'))

    existing_submission = conn.execute(
        "SELECT * FROM submissions WHERE assignment_id = ? AND student_id = ?",
        (assignment_id, current_user.id)
    ).fetchone()

    if request.method == 'POST':
        submission_text = request.form.get('submission_text', '')
        uploaded_file = request.files.get('submission_file')

        file_content = ""
        file_name = None
        file_size = None
        file_type = None

        if uploaded_file and uploaded_file.filename != '' and allowed_file(uploaded_file.filename):
            try:
                uploaded_file.seek(0, os.SEEK_END)
                file_size = uploaded_file.tell()
                uploaded_file.seek(0)

                # Enforce max upload size using Flask config
                if file_size > (current_app.config.get('MAX_CONTENT_LENGTH') or 16 * 1024 * 1024):
                    flash('File size exceeds maximum limit (16MB).', 'danger')
                    conn.close()
                    return redirect(url_for('student.assignment_submission', assignment_id=assignment_id))

                file_extension = uploaded_file.filename.split('.')[-1].lower()

                if file_extension == 'txt':
                    file_content = uploaded_file.read().decode('utf-8')
                elif file_extension == 'docx':
                    doc = docx.Document(uploaded_file)
                    file_content = '\n'.join([para.text for para in doc.paragraphs])
                elif file_extension == 'pdf':
                    pdf_reader = PyPDF2.PdfReader(uploaded_file)
                    file_content = '\n'.join([page.extract_text() or '' for page in pdf_reader.pages])

                file_name = secure_filename(uploaded_file.filename)
                file_type = uploaded_file.content_type

                # Save original file to disk for faculty viewing/downloading
                base = current_app.config['UPLOAD_FOLDER']
                save_dir = os.path.join(base, 'assignments', str(assignment_id), 'students', str(current_user.id))
                os.makedirs(save_dir, exist_ok=True)

                uploaded_file.seek(0)
                uploaded_file.save(os.path.join(save_dir, file_name))

            except Exception as e:
                flash(f"Error processing file: {e}", 'danger')
                conn.close()
                return redirect(url_for('student.assignment_submission', assignment_id=assignment_id))

        if not submission_text and not file_content and not file_name:
            flash("Please provide text or upload a file for your submission.", 'danger')
            conn.close()
            return redirect(url_for('student.assignment_submission', assignment_id=assignment_id))

        # If there is no extracted text (e.g., image, ppt, etc.), keep a placeholder so DB 'content' is not null
        final_submission_text = submission_text if submission_text else (file_content if file_content else (f"[File uploaded: {file_name}]" if file_name else ''))

        other_submissions = conn.execute(
            "SELECT content FROM submissions WHERE assignment_id = ? AND student_id != ?",
            (assignment_id, current_user.id)
        ).fetchall()

        source_documents = [sub['content'] for sub in other_submissions]
        plagiarism_results = check_plagiarism(final_submission_text, source_documents)

        overall_similarity = 0
        if plagiarism_results:
            scores = [float(res['similarity'].strip('%')) / 100 for res in plagiarism_results]
            if scores:
                overall_similarity = max(scores)

        if overall_similarity > current_app.config['PLAGIARISM_THRESHOLD']:
            flash(f'High plagiarism detected ({overall_similarity * 100:.2f}%)! Submission not accepted.', 'danger')
            conn.close()
            return redirect(url_for('student.assignment_submission', assignment_id=assignment_id))
        else:
            try:
                if existing_submission:
                    conn.execute(
                        "UPDATE submissions SET content = ?, file_name = ?, file_size = ?, file_type = ?, plagiarism_score = ?, submitted_at = CURRENT_TIMESTAMP WHERE id = ?",
                        (final_submission_text, file_name, file_size, file_type, overall_similarity, existing_submission['id'])
                    )
                    flash('Your previous submission has been successfully replaced!', 'success')
                else:
                    conn.execute(
                        "INSERT INTO submissions (content, student_id, assignment_id, file_name, file_size, file_type, plagiarism_score) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (final_submission_text, current_user.id, assignment_id, file_name, file_size, file_type, overall_similarity)
                    )
                    flash('Submission successful!', 'success')

                faculty_id = conn.execute("SELECT faculty_id FROM assignments WHERE id = ?", (assignment_id,)).fetchone()['faculty_id']
                conn.execute(
                    "INSERT INTO notifications (user_id, title, message, type) VALUES (?, ?, ?, ?)",
                    (faculty_id, 'New Submission', f'Student {current_user.username} submitted assignment.', 'info')
                )

                conn.commit()
            except Exception:
                flash('Error saving submission. Please try again.', 'danger')
            finally:
                conn.close()

            return redirect(url_for('student.student_assignments'))

    conn.close()
    return render_template(
        'assignment_submission_standalone.html',
        assignment=assignment,
        user=current_user,
        existing_submission=existing_submission
    )


@student_bp.route('/grades')
@login_required
def student_grades():
    if current_user.role != 'student':
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('main.dashboard'))

    conn = get_db_connection()
    grades = conn.execute(
        "SELECT s.*, a.title, a.max_marks FROM submissions s JOIN assignments a ON s.assignment_id = a.id WHERE s.student_id = ? AND s.grade IS NOT NULL ORDER BY s.submitted_at DESC",
        (current_user.id,)
    ).fetchall()
    conn.close()

    return render_template('student_grades_standalone.html', user=current_user, grades=grades)


@student_bp.route('/progress')
@login_required
def progress():
    if current_user.role != 'student':
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('main.dashboard'))

    conn = get_db_connection()
    total_assignments = conn.execute(
        "SELECT COUNT(*) AS count FROM assignments WHERE is_active = 1"
    ).fetchone()['count']
    completed = conn.execute(
        "SELECT COUNT(*) AS count FROM submissions WHERE student_id = ?",
        (current_user.id,)
    ).fetchone()['count']
    pending = max(total_assignments - completed, 0)

    grade_row = conn.execute(
        "SELECT AVG(grade) AS avg_grade FROM submissions WHERE student_id = ? AND grade IS NOT NULL",
        (current_user.id,)
    ).fetchone()
    grade_average = round(grade_row['avg_grade'], 2) if grade_row and grade_row['avg_grade'] is not None else None

    recent_graded = conn.execute(
        "SELECT a.title AS title, s.grade AS grade FROM submissions s JOIN assignments a ON s.assignment_id = a.id WHERE s.student_id = ? AND s.grade IS NOT NULL ORDER BY s.submitted_at DESC LIMIT 10",
        (current_user.id,)
    ).fetchall()

    # Grade distribution buckets
    buckets = [
        ('90-100', 90, 100),
        ('80-89', 80, 89),
        ('70-79', 70, 79),
        ('60-69', 60, 69),
        ('<60', 0, 59),
    ]
    dist_labels = []
    dist_values = []
    for label, low, high in buckets:
        count = conn.execute(
            "SELECT COUNT(*) AS c FROM submissions WHERE student_id = ? AND grade IS NOT NULL AND grade BETWEEN ? AND ?",
            (current_user.id, low, high)
        ).fetchone()['c']
        dist_labels.append(label)
        dist_values.append(count)

    conn.close()

    return render_template(
        'student_progress.html',
        user=current_user,
        total_assignments=total_assignments,
        completed_assignments=completed,
        pending_assignments=pending,
        grade_average=grade_average,
        grades_labels=[row['title'] for row in recent_graded] if recent_graded else [],
        grades_values=[row['grade'] for row in recent_graded] if recent_graded else [],
        dist_labels=dist_labels,
        dist_values=dist_values,
    )


