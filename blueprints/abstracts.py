from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
import os
import secrets
from datetime import datetime
import re

from models import get_db_connection
from plagiarism_checker import check_abstract_plagiarism, update_submission_plagiarism_score

abstracts_bp = Blueprint('abstracts', __name__, url_prefix='/abstracts')

UPLOAD_FOLDER = os.path.join('static', 'uploads', 'abstracts')
ALLOWED_EXTENSIONS = {'pdf', 'docx', 'txt'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def count_words(text):
    """Count words in text, excluding extra whitespace"""
    return len(re.findall(r'\b\w+\b', text))

def validate_abstract(text, min_words=150, max_words=500):
    """Validate abstract text against word count requirements"""
    word_count = count_words(text)
    if word_count < min_words:
        return False, f"Abstract must be at least {min_words} words. Current: {word_count} words."
    if word_count > max_words:
        return False, f"Abstract must be no more than {max_words} words. Current: {word_count} words."
    return True, word_count

@abstracts_bp.route('/submit/<int:event_id>', methods=['GET', 'POST'])
@login_required
def submit_abstract(event_id):
    """Submit abstract for an event"""
    if current_user.role != 'student':
        flash('Only students can submit abstracts.', 'danger')
        return redirect(url_for('events.browse_events'))
    
    conn = get_db_connection()
    
    event = conn.execute("""
        SELECT e.*, er.requires_abstract, er.abstract_min_words, er.abstract_max_words,
               er.abstract_deadline, er.allowed_file_types, er.max_file_size_mb
        FROM events e
        LEFT JOIN event_requirements er ON e.id = er.event_id
        WHERE e.id = ?
    """, (event_id,)).fetchone()
    
    if not event:
        flash('Event not found.', 'danger')
        conn.close()
        return redirect(url_for('events.browse_events'))
    
    if not event['requires_abstract']:
        flash('This event does not require abstract submission.', 'info')
        conn.close()
        return redirect(url_for('events.event_details', event_id=event_id))
    
    registration = conn.execute("""
        SELECT * FROM event_registrations 
        WHERE event_id = ? AND user_id = ?
    """, (event_id, current_user.id)).fetchone()
    
    if not registration:
        flash('You must register for this event before submitting an abstract.', 'warning')
        conn.close()
        return redirect(url_for('events.event_details', event_id=event_id))
    
    if registration['registration_status'] != 'approved':
        flash(f'Your registration is {registration["registration_status"]}. You need approved registration to submit abstracts.', 'info')
        conn.close()
        return redirect(url_for('events.event_details', event_id=event_id))
    
    if event['abstract_deadline']:
        deadline = datetime.fromisoformat(event['abstract_deadline'].replace('Z', '+00:00'))
        if datetime.now() > deadline:
            flash('Abstract submission deadline has passed.', 'danger')
            conn.close()
            return redirect(url_for('events.event_details', event_id=event_id))
    
    existing_submission = conn.execute("""
        SELECT * FROM abstract_submissions 
        WHERE event_id = ? AND user_id = ? AND is_latest_version = 1
    """, (event_id, current_user.id)).fetchone()
    
    team = conn.execute("""
        SELECT t.* FROM teams t
        JOIN team_members tm ON t.id = tm.team_id
        WHERE t.event_id = ? AND tm.user_id = ? AND tm.status = 'active'
    """, (event_id, current_user.id)).fetchone()
    
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        abstract_text = request.form.get('abstract_text', '').strip()
        
        if not title or not abstract_text:
            flash('Title and abstract text are required.', 'danger')
            conn.close()
            return render_template('submit_abstract.html', event=event, existing_submission=existing_submission, team=team)
        
        min_words = event['abstract_min_words'] or 150
        max_words = event['abstract_max_words'] or 500
        is_valid, result = validate_abstract(abstract_text, min_words, max_words)
        
        if not is_valid:
            flash(result, 'danger')
            conn.close()
            return render_template('submit_abstract.html', event=event, existing_submission=existing_submission, team=team)
        
        word_count = result
        
        file_path = None
        file_name = None
        file_size = None
        
        if 'abstract_file' in request.files:
            file = request.files['abstract_file']
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                unique_filename = f"{secrets.token_hex(8)}_{filename}"
                os.makedirs(UPLOAD_FOLDER, exist_ok=True)
                
                file_path = os.path.join(UPLOAD_FOLDER, unique_filename)
                file.save(file_path)
                file_name = filename
                file_size = os.path.getsize(file_path)
                max_size = (event['max_file_size_mb'] or 5) * 1024 * 1024
                if file_size > max_size:
                    os.remove(file_path)
                    flash(f'File size exceeds {event["max_file_size_mb"] or 5}MB limit.', 'danger')
                    conn.close()
                    return render_template('submit_abstract.html', event=event, existing_submission=existing_submission, team=team)
        
        try:
            if existing_submission:
                new_version = existing_submission['version'] + 1
                conn.execute("""
                    UPDATE abstract_submissions 
                    SET is_latest_version = 0 
                    WHERE id = ?
                """, (existing_submission['id'],))
                conn.execute("""
                    INSERT INTO abstract_submissions 
                    (event_id, team_id, user_id, title, abstract_text, file_path, file_name, 
                     file_size, word_count, status, version, is_latest_version)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'draft', ?, 1)
                """, (event_id, team['id'] if team else None, current_user.id, title, 
                      abstract_text, file_path, file_name, file_size, word_count, new_version))
                submission_id = conn.lastrowid
                conn.execute("""
                    INSERT INTO abstract_submission_history 
                    (submission_id, version, title, abstract_text, file_path, word_count, 
                     changes_summary, created_by)
                    VALUES (?, ?, ?, ?, ?, ?, 'Updated abstract submission', ?)
                """, (submission_id, new_version, title, abstract_text, file_path, word_count, current_user.id))
                
                flash('Abstract updated successfully! You can continue editing until you submit.', 'success')
            else:
                conn.execute("""
                    INSERT INTO abstract_submissions 
                    (event_id, team_id, user_id, title, abstract_text, file_path, file_name, 
                     file_size, word_count, status, version, is_latest_version)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'draft', 1, 1)
                """, (event_id, team['id'] if team else None, current_user.id, title, 
                      abstract_text, file_path, file_name, file_size, word_count))
                
                flash('Abstract saved as draft! You can continue editing until you submit.', 'success')
            
            conn.commit()
            
        except Exception as e:
            conn.rollback()
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
            flash(f'Error saving abstract: {str(e)}', 'danger')
        finally:
            conn.close()
        
        return redirect(url_for('abstracts.submit_abstract', event_id=event_id))
    
    conn.close()
    return render_template('submit_abstract.html', event=event, existing_submission=existing_submission, team=team)

@abstracts_bp.route('/finalize/<int:submission_id>', methods=['POST'])
@login_required
def finalize_submission(submission_id):
    """Finalize abstract submission (no more edits allowed)"""
    conn = get_db_connection()
    submission = conn.execute("""
        SELECT * FROM abstract_submissions 
        WHERE id = ? AND user_id = ? AND status = 'draft'
    """, (submission_id, current_user.id)).fetchone()
    
    if not submission:
        flash('Submission not found or already finalized.', 'danger')
        conn.close()
        return redirect(url_for('events.browse_events'))
    
    try:
        abstract_text = conn.execute("""
            SELECT abstract_text FROM abstract_submissions WHERE id = ?
        """, (submission_id,)).fetchone()['abstract_text']
        plagiarism_report = check_abstract_plagiarism(
            abstract_text,
            submission['event_id'],
            submission_id
        )

        # Convert overall plagiarism score (0-1) to percentage for comparison/display
        plagiarism_percent = round(plagiarism_report['overall_score'] * 100, 1)

        # Get event-specific threshold in percent (fallback to 80 if not configured)
        event_req = conn.execute(
            "SELECT plagiarism_threshold FROM event_requirements WHERE event_id = ?",
            (submission['event_id'],),
        ).fetchone()
        threshold_percent = 80.0
        if event_req and event_req['plagiarism_threshold'] is not None:
            try:
                threshold_percent = float(event_req['plagiarism_threshold'])
            except (TypeError, ValueError):
                threshold_percent = 80.0

        # If plagiarism exceeds or equals threshold, do NOT finalize submission
        if plagiarism_percent >= threshold_percent:
            conn.execute(
                """
                UPDATE abstract_submissions
                SET plagiarism_score = ?, plagiarism_status = 'flagged'
                WHERE id = ?
                """,
                (plagiarism_report['overall_score'], submission_id),
            )
            conn.commit()

            flash(
                f'Plagiarism score is {plagiarism_percent}% which is above the allowed threshold of '
                f'{threshold_percent}%. Please revise your abstract and try again.',
                'danger',
            )

            return redirect(url_for('abstracts.submit_abstract', event_id=submission['event_id']))

        # Below threshold: finalize submission as submitted
        conn.execute(
            """
            UPDATE abstract_submissions
            SET status = 'submitted', submitted_at = CURRENT_TIMESTAMP,
                plagiarism_score = ?, plagiarism_status = ?
            WHERE id = ?
            """,
            (
                plagiarism_report['overall_score'],
                'flagged' if plagiarism_report['is_suspicious'] else 'clean',
                submission_id,
            ),
        )

        if submission['team_id']:
            conn.execute(
                """
                UPDATE teams
                SET has_submitted_abstract = 1, abstract_status = 'submitted'
                WHERE id = ?
                """,
                (submission['team_id'],),
            )

        event = conn.execute(
            "SELECT * FROM events WHERE id = ?",
            (submission['event_id'],),
        ).fetchone()

        # Include plagiarism percentage and risk level in manager notification
        notification_message = (
            f'New abstract submitted for "{event["title"]}" by {current_user.username} '
            f'(Plagiarism: {plagiarism_percent}% - {plagiarism_report["risk_level"]} risk)'
        )

        conn.execute(
            """
            INSERT INTO notifications (user_id, type, title, message, link)
            VALUES (?, 'abstract_submission', 'New Abstract Submission', ?, ?)
            """,
            (event['manager_id'], notification_message, f'/event_manager/abstracts/{event["id"]}'),
        )

        conn.commit()

        if plagiarism_report['is_suspicious']:
            flash(
                f'Abstract submitted successfully! Plagiarism score: {plagiarism_percent}% '
                f'(risk: {plagiarism_report["risk_level"]}). Please ensure all content is original.',
                'warning',
            )
        else:
            flash(
                f'Abstract submitted successfully! Plagiarism score: {plagiarism_percent}%. '
                'No further edits are allowed.',
                'success',
            )

    except Exception as e:
        conn.rollback()
        flash(f'Error finalizing submission: {str(e)}', 'danger')
    finally:
        conn.close()
    
    return redirect(url_for('events.event_details', event_id=submission['event_id']))

@abstracts_bp.route('/my_submissions')
@login_required
def my_submissions():
    """View user's abstract submissions"""
    if current_user.role != 'student':
        flash('Access denied.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    conn = get_db_connection()
    
    submissions = conn.execute("""
        SELECT a.*, e.title as event_title, e.event_type, t.name as team_name
        FROM abstract_submissions a
        JOIN events e ON a.event_id = e.id
        LEFT JOIN teams t ON a.team_id = t.id
        WHERE a.user_id = ? AND a.is_latest_version = 1
        ORDER BY a.created_at DESC
    """, (current_user.id,)).fetchall()
    
    conn.close()
    return render_template('my_abstract_submissions.html', submissions=submissions, user=current_user)

@abstracts_bp.route('/view/<int:submission_id>')
@login_required
def view_submission(submission_id):
    """View abstract submission details"""
    conn = get_db_connection()
    
    submission = conn.execute("""
        SELECT a.*, e.title as event_title, e.event_type, t.name as team_name,
               u.username as submitted_by, r.username as reviewed_by_name
        FROM abstract_submissions a
        JOIN events e ON a.event_id = e.id
        JOIN users u ON a.user_id = u.id
        LEFT JOIN teams t ON a.team_id = t.id
        LEFT JOIN users r ON a.reviewed_by = r.id
        WHERE a.id = ?
    """, (submission_id,)).fetchone()
    
    if not submission:
        flash('Submission not found.', 'danger')
        conn.close()
        return redirect(url_for('events.browse_events'))
    can_view = (current_user.id == submission['user_id'] or 
                current_user.role == 'event_manager' or 
                current_user.role == 'admin')
    
    if not can_view:
        flash('Access denied.', 'danger')
        conn.close()
        return redirect(url_for('events.browse_events'))
    history = conn.execute("""
        SELECT * FROM abstract_submission_history 
        WHERE submission_id = ? 
        ORDER BY version DESC
    """, (submission_id,)).fetchall()
    
    conn.close()
    return render_template('view_abstract_submission.html', submission=submission, history=history, user=current_user)
