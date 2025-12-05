from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app, send_from_directory, Response
from flask_login import login_required, current_user
import secrets
from datetime import datetime
import os
from io import StringIO
import csv

from models import get_db_connection
from utils.event_validators import validate_event_registration, validate_team_creation, validate_abstract_submission

event_manager_bp = Blueprint('event_manager', __name__, url_prefix='/event_manager')

@event_manager_bp.route('/events')
@login_required
def events():
    if current_user.role != 'event_manager':
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    conn = get_db_connection()
    manager_events = conn.execute(
        "SELECT * FROM events WHERE manager_id = ? ORDER BY created_at DESC",
        (current_user.id,)
    ).fetchall()
    conn.close()
    return render_template('manager_events.html', user=current_user, events=manager_events)

@event_manager_bp.route('/create_event', methods=['GET', 'POST'])
@login_required
def create_event():
    if current_user.role != 'event_manager':
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        event_type = request.form.get('event_type', '').strip()
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        registration_deadline = request.form.get('registration_deadline')
        venue = request.form.get('venue', '').strip()
        prize_pool = request.form.get('prize_pool', '').strip()
        resources_link = request.form.get('resources_link', '').strip()
        is_team_event = 'is_team_event' in request.form
        join_policy = request.form.get('join_policy', 'manual')
        requires_abstract = 'requires_abstract' in request.form
        
        if not title or len(title) < 3:
            flash('Title must be at least 3 characters long.', 'danger')
            return render_template('create_event.html', user=current_user)
        
        if not event_type:
            flash('Event type is required.', 'danger')
            return render_template('create_event.html', user=current_user)

        try:
            max_participants = int(request.form.get('max_participants')) if request.form.get('max_participants') else None
            max_team_size = int(request.form.get('max_team_size', 5))
            min_team_size = int(request.form.get('min_team_size', 1))
            abstract_min_words = int(request.form.get('abstract_min_words', 150))
            abstract_max_words = int(request.form.get('abstract_max_words', 500))
            max_file_size_mb = float(request.form.get('max_file_size_mb', 5.0))
            plagiarism_threshold = float(request.form.get('plagiarism_threshold', 25.0))
            auto_approve_threshold = float(request.form.get('auto_approve_threshold', 10.0))
            auto_approve_timeout_hours = int(request.form.get('auto_approve_timeout_hours', 72))
        except (ValueError, TypeError):
            flash('Invalid number format for participants, team size, or abstract settings.', 'danger')
            return render_template('create_event.html', user=current_user)

        abstract_deadline = request.form.get('abstract_deadline')
        if requires_abstract and not abstract_deadline:
            abstract_deadline = registration_deadline
        allowed_file_types = request.form.get('allowed_file_types', 'pdf,docx,txt').strip()
        event_code = secrets.token_urlsafe(8)
        
        conn = get_db_connection()
        try:
            with conn:
                cursor = conn.execute(
                    """INSERT INTO events (title, description, event_type, event_code, manager_id, 
                       start_date, end_date, registration_deadline, venue, max_participants, 
                       max_team_size, min_team_size, is_team_event, prize_pool, resources_link, 
                       status, join_policy) 
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (title, description, event_type, event_code, current_user.id, 
                     start_date, end_date, registration_deadline, venue, max_participants,
                     max_team_size, min_team_size, is_team_event, prize_pool, resources_link, 
                     'upcoming', join_policy)
                )
                event_id = cursor.lastrowid
                
                conn.execute(
                    """INSERT INTO event_requirements (event_id, requires_abstract, abstract_min_words, 
                       abstract_max_words, abstract_deadline, allowed_file_types, max_file_size_mb, 
                       plagiarism_threshold, auto_approve_threshold, auto_approve_timeout_hours) 
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (event_id, requires_abstract, abstract_min_words, abstract_max_words, 
                     abstract_deadline if requires_abstract else None, allowed_file_types, 
                     max_file_size_mb, plagiarism_threshold, auto_approve_threshold, 
                     auto_approve_timeout_hours)
                )
                
                students = conn.execute("SELECT id FROM users WHERE role = 'student'").fetchall()
                for student in students:
                    conn.execute(
                        "INSERT INTO notifications (user_id, title, message, type) VALUES (?, ?, ?, ?)",
                        (student['id'], 'New Event', f'New event "{title}" is now open for registration!', 'info')
                    )
            
            flash(f'Event "{title}" created successfully! Event code: {event_code}', 'success')
            return redirect(url_for('event_manager.events'))
            
        except Exception as e:
            current_app.logger.error(f"Error creating event: {str(e)}", exc_info=True)
            flash(f'Error creating event: {str(e)}', 'danger')
        finally:
            if conn:
                conn.close()
        
    return render_template('create_event.html', user=current_user)

@event_manager_bp.route('/event/<int:event_id>/registrations')
@login_required
def event_registrations(event_id):
    if current_user.role != 'event_manager':
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    conn = get_db_connection()
    event = conn.execute(
        "SELECT * FROM events WHERE id = ? AND manager_id = ?", (event_id, current_user.id)
    ).fetchone()

    if not event:
        flash('Event not found or access denied.', 'danger')
        conn.close()
        return redirect(url_for('event_manager.events'))

    registrations = conn.execute(
        """SELECT er.*, u.username, u.full_name, t.name as team_name
           FROM event_registrations er
           JOIN users u ON er.user_id = u.id
           LEFT JOIN teams t ON er.team_id = t.id
           WHERE er.event_id = ? ORDER BY er.registered_at DESC""",
        (event_id,)
    ).fetchall()
    conn.close()

    return render_template(
        'event_registrations.html',
        user=current_user,
        event=event,
        registrations=registrations
    )

@event_manager_bp.route('/registration/<int:registration_id>/approve', methods=['POST'])
@login_required
def approve_registration(registration_id):
    if current_user.role != 'event_manager':
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('main.dashboard'))

    conn = get_db_connection()
    event_id_to_redirect = None
    try:
        registration_to_approve = conn.execute(
            """SELECT er.event_id, e.manager_id, e.title, u.id as student_id
               FROM event_registrations er
               JOIN events e ON er.event_id = e.id
               JOIN users u ON er.user_id = u.id
               WHERE er.id = ?""",
            (registration_id,)
        ).fetchone()

        if not registration_to_approve:
            flash('Registration not found.', 'danger')
            return redirect(url_for('event_manager.events'))

        event_id_to_redirect = registration_to_approve['event_id']

        if registration_to_approve['manager_id'] != current_user.id:
            flash('You do not have permission to approve this registration.', 'danger')
            return redirect(url_for('event_manager.event_registrations', event_id=event_id_to_redirect))

        conn.execute(
            "UPDATE event_registrations SET registration_status = 'approved', approved_at = CURRENT_TIMESTAMP WHERE id = ?",
            (registration_id,)
        )
        
        conn.execute(
            "INSERT INTO notifications (user_id, title, message, type) VALUES (?, ?, ?, ?)",
            (registration_to_approve['student_id'], 'Registration Approved', 
             f'Your registration for "{registration_to_approve["title"]}" has been approved!', 'success')
        )
        
        conn.commit()
        flash('Registration approved successfully!', 'success')

    except Exception as e:
        current_app.logger.error(f"Error approving registration {registration_id}: {e}")
        flash(f'Error approving registration: {str(e)}', 'danger')
    finally:
        if conn:
            conn.close()

    if event_id_to_redirect:
        return redirect(url_for('event_manager.event_registrations', event_id=event_id_to_redirect))
    else:
        return redirect(url_for('event_manager.events'))

@event_manager_bp.route('/abstracts/<int:event_id>')
@login_required
def manage_abstracts(event_id):
    if current_user.role != 'event_manager':
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    conn = get_db_connection()
    try:
        event = conn.execute("""
            SELECT e.*, er.requires_abstract, er.abstract_min_words, er.abstract_max_words,
                   er.plagiarism_threshold
            FROM events e
            LEFT JOIN event_requirements er ON e.id = er.event_id
            WHERE e.id = ? AND e.manager_id = ?
        """, (event_id, current_user.id)).fetchone()

        if not event:
            flash('Event not found or access denied.', 'danger')
            return redirect(url_for('event_manager.events'))

        if not event['requires_abstract']:
            flash('This event does not require abstract submissions.', 'info')
            return redirect(url_for('event_manager.event_registrations', event_id=event_id))

        status_filter = request.args.get('status', 'all')
        search_query = request.args.get('search', '').strip()

        stats = conn.execute(
            """
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN status = 'draft' THEN 1 ELSE 0 END) AS draft,
                SUM(CASE WHEN status = 'submitted' THEN 1 ELSE 0 END) AS submitted,
                SUM(CASE WHEN status = 'under_review' THEN 1 ELSE 0 END) AS under_review,
                SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) AS approved,
                SUM(CASE WHEN status = 'rejected' THEN 1 ELSE 0 END) AS rejected,
                SUM(CASE WHEN status = 'revision_required' THEN 1 ELSE 0 END) AS revision_required
            FROM abstract_submissions
            WHERE event_id = ? AND is_latest_version = 1
            """,
            (event_id,),
        ).fetchone()

        query = """
            SELECT a.*, u.username, u.full_name, u.email,
                   t.name AS team_name, er.plagiarism_threshold
            FROM abstract_submissions a
            JOIN users u ON a.user_id = u.id
            LEFT JOIN teams t ON a.team_id = t.id
            LEFT JOIN event_requirements er ON a.event_id = er.event_id
            WHERE a.event_id = ? AND a.is_latest_version = 1
        """
        params = [event_id]

        if status_filter != 'all':
            query += " AND a.status = ?"
            params.append(status_filter)

        if search_query:
            like = f"%{search_query}%"
            query += """
                AND (
                    u.username LIKE ? OR
                    u.full_name LIKE ? OR
                    u.email LIKE ? OR
                    a.title LIKE ?
                )
            """
            params.extend([like, like, like, like])

        query += " ORDER BY a.created_at DESC"

        submissions = conn.execute(query, params).fetchall()

    finally:
        conn.close()

    return render_template(
        'manage_abstracts.html',
        user=current_user,
        event=event,
        submissions=submissions,
        stats=stats,
        status_filter=status_filter,
        search_query=search_query,
    )

@event_manager_bp.route('/abstracts/<int:event_id>/bulk', methods=['POST'])
@login_required
def bulk_abstract_action(event_id):
    if current_user.role != 'event_manager':
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('main.dashboard'))

    bulk_action = request.form.get('bulk_action')
    raw_ids = request.form.getlist('submission_ids')

    if not raw_ids:
        flash('No submissions selected.', 'warning')
        return redirect(url_for('event_manager.manage_abstracts', event_id=event_id))

    if bulk_action not in ['approve', 'reject', 'mark_under_review']:
        flash('Invalid bulk action.', 'danger')
        return redirect(url_for('event_manager.manage_abstracts', event_id=event_id))

    try:
        submission_ids = [int(s_id) for s_id in raw_ids]
    except ValueError:
        flash('Invalid submission selection.', 'danger')
        return redirect(url_for('event_manager.manage_abstracts', event_id=event_id))

    conn = get_db_connection()
    try:
        event = conn.execute(
            "SELECT id, manager_id, title FROM events WHERE id = ?",
            (event_id,),
        ).fetchone()

        if not event or event['manager_id'] != current_user.id:
            flash('Event not found or access denied.', 'danger')
            return redirect(url_for('event_manager.events'))

        placeholders = ",".join("?" for _ in submission_ids)
        params = [event_id] + submission_ids
        submissions = conn.execute(
            f"""
            SELECT id, event_id, user_id, team_id, status
            FROM abstract_submissions
            WHERE event_id = ? AND is_latest_version = 1
              AND id IN ({placeholders})
            """,
            params,
        ).fetchall()

        if not submissions:
            flash('No matching submissions found for this event.', 'warning')
            return redirect(url_for('event_manager.manage_abstracts', event_id=event_id))

        if bulk_action == 'approve':
            new_status = 'approved'
        elif bulk_action == 'reject':
            new_status = 'rejected'
        else:
            new_status = 'under_review'

        for submission in submissions:
            conn.execute(
                """
                UPDATE abstract_submissions
                SET status = ?, reviewed_by = ?, reviewed_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (new_status, current_user.id, submission['id']),
            )

            if submission['team_id']:
                team_status = 'approved' if new_status == 'approved' else 'needs_revision'
                conn.execute(
                    "UPDATE teams SET abstract_status = ? WHERE id = ?",
                    (team_status, submission['team_id']),
                )

            notification_title = f"Abstract {new_status.replace('_', ' ').title()}"
            notification_message = (
                f'Your abstract for "{event["title"]}" has been updated to: '
                f'{new_status.replace("_", " ")}.'
            )
            conn.execute(
                """
                INSERT INTO notifications (user_id, type, title, message, link)
                VALUES (?, 'abstract_review', ?, ?, ?)
                """,
                (
                    submission['user_id'],
                    notification_title,
                    notification_message,
                    f'/abstracts/view/{submission["id"]}',
                ),
            )

        conn.commit()
        flash(
            f'Bulk action "{bulk_action.replace("_", " ")}" applied to {len(submissions)} submission(s).',
            'success',
        )
    except Exception as e:
        conn.rollback()
        flash(f'Error applying bulk action: {str(e)}', 'danger')
    finally:
        conn.close()

    return redirect(url_for('event_manager.manage_abstracts', event_id=event_id))

@event_manager_bp.route('/abstracts/<int:event_id>/export')
@login_required
def export_abstracts(event_id):
    if current_user.role != 'event_manager':
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('main.dashboard'))

    conn = get_db_connection()
    try:
        event = conn.execute(
            "SELECT id, manager_id, title FROM events WHERE id = ?",
            (event_id,),
        ).fetchone()

        if not event or event['manager_id'] != current_user.id:
            flash('Event not found or access denied.', 'danger')
            return redirect(url_for('event_manager.events'))

        submissions = conn.execute(
            """
            SELECT a.*, u.username, u.full_name, u.email,
                   t.name AS team_name
            FROM abstract_submissions a
            JOIN users u ON a.user_id = u.id
            LEFT JOIN teams t ON a.team_id = t.id
            WHERE a.event_id = ? AND a.is_latest_version = 1
            ORDER BY a.created_at DESC
            """,
            (event_id,),
        ).fetchall()
    finally:
        conn.close()

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            'Submission ID',
            'Student Username',
            'Student Name',
            'Student Email',
            'Team Name',
            'Title',
            'Status',
            'Word Count',
            'Plagiarism Score (%)',
            'Submitted At',
            'Reviewed At',
        ]
    )

    for submission in submissions:
        plagiarism_percent = (
            round(submission['plagiarism_score'] * 100, 1)
            if submission['plagiarism_score'] is not None
            else ''
        )
        writer.writerow(
            [
                submission['id'],
                submission['username'],
                submission['full_name'] or submission['username'],
                submission['email'],
                submission['team_name'] or '',
                submission['title'],
                submission['status'],
                submission['word_count'],
                plagiarism_percent,
                submission['submitted_at'] or '',
                submission['reviewed_at'] or '',
            ]
        )

    csv_data = output.getvalue()
    filename = f'abstracts_event_{event_id}.csv'
    return Response(
        csv_data,
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename={filename}'},
    )

@event_manager_bp.route('/analytics')
@login_required
def analytics():
    if current_user.role != 'event_manager':
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('main.dashboard'))

    conn = get_db_connection()
    try:
        stats = conn.execute(
            """
            SELECT COUNT(*) AS total_events,
                   SUM(CASE WHEN status = 'upcoming' THEN 1 ELSE 0 END) AS upcoming_events,
                   SUM(CASE WHEN status = 'ongoing' THEN 1 ELSE 0 END) AS ongoing_events,
                   SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS completed_events,
                   (SELECT COUNT(*)
                      FROM event_registrations er
                      JOIN events e2 ON er.event_id = e2.id
                      WHERE e2.manager_id = ?) AS total_registrations,
                   (SELECT COUNT(DISTINCT user_id)
                      FROM event_registrations er
                      JOIN events e2 ON er.event_id = e2.id
                      WHERE e2.manager_id = ?) AS unique_participants
            FROM events
            WHERE manager_id = ?
            """,
            (current_user.id, current_user.id, current_user.id)
        ).fetchone()

        participation_data = conn.execute(
            """
            SELECT e.id, e.title, e.status, e.start_date, e.end_date,
                   COUNT(er.id) AS registration_count,
                   COUNT(DISTINCT er.user_id) AS unique_participants
            FROM events e
            LEFT JOIN event_registrations er ON e.id = er.event_id
            WHERE e.manager_id = ?
            GROUP BY e.id
            ORDER BY e.start_date DESC
            LIMIT 10
            """,
            (current_user.id,)
        ).fetchall()

        registration_trends = conn.execute(
            """
            SELECT strftime('%Y-%m', er.registered_at) AS month,
                   COUNT(*) AS registrations
            FROM event_registrations er
            JOIN events e ON er.event_id = e.id
            WHERE e.manager_id = ?
            GROUP BY strftime('%Y-%m', er.registered_at)
            ORDER BY month
            """,
            (current_user.id,)
        ).fetchall()

        event_types = conn.execute(
            """
            SELECT e.event_type,
                   COUNT(*) AS event_count,
                   COUNT(er.id) AS registration_count
            FROM events e
            LEFT JOIN event_registrations er ON e.id = er.event_id
            WHERE e.manager_id = ?
            GROUP BY e.event_type
            ORDER BY registration_count DESC
            """,
            (current_user.id,)
        ).fetchall()

    finally:
        conn.close()

    return render_template(
        'analytics.html',
        user=current_user,
        stats=stats,
        participation_data=participation_data,
        registration_trends=registration_trends,
        event_types=event_types
    )

@event_manager_bp.route('/abstract/<int:submission_id>/review', methods=['GET', 'POST'])
@login_required
def review_abstract(submission_id):
    if current_user.role != 'event_manager':
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('main.dashboard'))

    conn = get_db_connection()
    submission = conn.execute("""
        SELECT a.*, e.title as event_title, e.manager_id, u.username, u.full_name, u.email,
               t.name as team_name, er.plagiarism_threshold
        FROM abstract_submissions a
        JOIN events e ON a.event_id = e.id
        JOIN users u ON a.user_id = u.id
        LEFT JOIN teams t ON a.team_id = t.id
        LEFT JOIN event_requirements er ON e.id = er.event_id
        WHERE a.id = ?
    """, (submission_id,)).fetchone()

    if not submission:
        flash('Submission not found.', 'danger')
        conn.close()
        return redirect(url_for('event_manager.events'))

    if submission['manager_id'] != current_user.id:
        flash('Access denied.', 'danger')
        conn.close()
        return redirect(url_for('event_manager.events'))

    if request.method == 'POST':
        action = request.form.get('action')
        feedback = request.form.get('feedback', '').strip()

        if action not in ['approve', 'reject', 'request_revision']:
            flash('Invalid action.', 'danger')
            conn.close()
            return redirect(url_for('event_manager.review_abstract', submission_id=submission_id))

        try:
            if action == 'approve':
                new_status = 'approved'
            elif action == 'reject':
                new_status = 'rejected'
            else:
                new_status = 'revision_required'

            conn.execute(
                "UPDATE abstract_submissions SET status = ?, reviewed_by = ?, reviewed_at = CURRENT_TIMESTAMP, feedback = ? WHERE id = ?",
                (new_status, current_user.id, feedback, submission_id)
            )

            if submission['team_id']:
                team_status = 'approved' if new_status == 'approved' else 'needs_revision'
                conn.execute("UPDATE teams SET abstract_status = ? WHERE id = ?", (team_status, submission['team_id']))
            
            notification_title = f"Abstract {new_status.replace('_', ' ').title()}"
            notification_message = f"Your abstract for \"{submission['event_title']}\" has been updated to: {new_status.replace('_', ' ')}."
            conn.execute(
                "INSERT INTO notifications (user_id, type, title, message, link) VALUES (?, 'abstract_review', ?, ?, ?)",
                (submission['user_id'], notification_title, notification_message, f'/abstracts/view/{submission_id}')
            )
            
            conn.commit()
            flash(f'Abstract status updated to {new_status.replace("_", " ")}!', 'success')
            return redirect(url_for('event_manager.manage_abstracts', event_id=submission['event_id']))
            
        except Exception as e:
            conn.rollback()
            flash(f'Error processing review: {str(e)}', 'danger')