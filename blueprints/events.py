from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
import secrets

from models import get_db_connection, Event, EventRegistration, Team

events_bp = Blueprint('events', __name__, url_prefix='/events')

@events_bp.route('/')
@login_required
def browse_events():
    """Browse all available events for students"""
    conn = get_db_connection()
    
    # Get filter parameters
    event_type = request.args.get('type', 'all')
    status = request.args.get('status', 'upcoming')
    
    query = """SELECT e.*, u.full_name as manager_name,
               (SELECT COUNT(*) FROM event_registrations WHERE event_id = e.id) as registration_count
               FROM events e
               JOIN users u ON e.manager_id = u.id
               WHERE 1=1"""
    
    params = []
    if event_type != 'all':
        query += " AND e.event_type = ?"
        params.append(event_type)
    
    if status != 'all':
        query += " AND e.status = ?"
        params.append(status)
    
    query += " ORDER BY e.start_date ASC"
    
    events = conn.execute(query, params).fetchall()
    
    # Check which events the current user has registered for
    registered_events = []
    if current_user.role == 'student':
        reg_query = conn.execute(
            "SELECT event_id FROM event_registrations WHERE user_id = ?",
            (current_user.id,)
        ).fetchall()
        registered_events = [r['event_id'] for r in reg_query]
    
    conn.close()
    
    return render_template('browse_events.html', 
                         user=current_user,
                         events=events,
                         registered_events=registered_events,
                         current_type=event_type,
                         current_status=status)

@events_bp.route('/<int:event_id>')
@login_required
def event_details(event_id):
    """View detailed information about an event"""
    conn = get_db_connection()
    
    event = conn.execute(
        """SELECT e.*, u.full_name as manager_name, u.email as manager_email,
                  er.requires_abstract, er.abstract_min_words, er.abstract_max_words,
                  er.abstract_deadline, er.allowed_file_types, er.max_file_size_mb
           FROM events e
           JOIN users u ON e.manager_id = u.id
           LEFT JOIN event_requirements er ON e.id = er.event_id
           WHERE e.id = ?""",
        (event_id,)
    ).fetchone()
    
    if not event:
        flash('Event not found.', 'danger')
        conn.close()
        return redirect(url_for('events.browse_events'))
    
    # Check if user is registered
    registration = None
    if current_user.role == 'student':
        registration = conn.execute(
            "SELECT * FROM event_registrations WHERE event_id = ? AND user_id = ?",
            (event_id, current_user.id)
        ).fetchone()
    
    # Get teams for this event
    teams = conn.execute(
        """SELECT t.*, u.username as leader_name,
           (SELECT COUNT(*) FROM team_members WHERE team_id = t.id AND status = 'active') as member_count
           FROM teams t
           JOIN users u ON t.leader_id = u.id
           WHERE t.event_id = ?
           ORDER BY t.created_at DESC""",
        (event_id,)
    ).fetchall()
    
    # Get user's team if they have one
    user_team = None
    user_abstract = None
    if current_user.role == 'student':
        user_team = conn.execute(
            """SELECT t.*, tm.role as member_role
               FROM teams t
               JOIN team_members tm ON t.id = tm.team_id
               WHERE t.event_id = ? AND tm.user_id = ? AND tm.status = 'active'""",
            (event_id, current_user.id)
        ).fetchone()
        
        # Check if user has submitted an abstract for this event
        if event['requires_abstract']:
            user_abstract = conn.execute(
                """SELECT * FROM abstract_submissions 
                   WHERE event_id = ? AND user_id = ? AND is_latest_version = 1""",
                (event_id, current_user.id)
            ).fetchone()
    
    # Get event statistics
    total_registrations = conn.execute(
        "SELECT COUNT(*) as c FROM event_registrations WHERE event_id = ?",
        (event_id,)
    ).fetchone()['c']
    
    conn.close()
    
    return render_template('event_details.html',
                         user=current_user,
                         event=event,
                         registration=registration,
                         teams=teams,
                         user_team=user_team,
                         user_abstract=user_abstract,
                         total_registrations=total_registrations)

@events_bp.route('/<int:event_id>/register', methods=['POST'])
@login_required
def register_for_event(event_id):
    """Register for an event"""
    if current_user.role != 'student':
        flash('Only students can register for events.', 'danger')
        return redirect(url_for('events.event_details', event_id=event_id))
    
    conn = get_db_connection()
    
    # Check if event exists and is open for registration
    event = conn.execute(
        "SELECT * FROM events WHERE id = ? AND status IN ('upcoming', 'ongoing')",
        (event_id,)
    ).fetchone()
    
    if not event:
        flash('Event not found or registration closed.', 'danger')
        conn.close()
        return redirect(url_for('events.browse_events'))
    
    # Check if already registered
    existing = conn.execute(
        "SELECT * FROM event_registrations WHERE event_id = ? AND user_id = ?",
        (event_id, current_user.id)
    ).fetchone()
    
    if existing:
        flash('You are already registered for this event.', 'warning')
        conn.close()
        return redirect(url_for('events.event_details', event_id=event_id))
    
    try:
        # Register for event
        conn.execute(
            "INSERT INTO event_registrations (event_id, user_id) VALUES (?, ?)",
            (event_id, current_user.id)
        )
        
        # Notify event manager
        conn.execute(
            "INSERT INTO notifications (user_id, title, message, type) VALUES (?, ?, ?, ?)",
            (event['manager_id'], 'New Registration',
             f'Student {current_user.username} has registered for "{event["title"]}"', 'info')
        )
        
        conn.commit()
        flash('Successfully registered for the event!', 'success')
    except Exception as e:
        flash(f'Error registering for event: {str(e)}', 'danger')
    finally:
        conn.close()
    
    return redirect(url_for('events.event_details', event_id=event_id))

@events_bp.route('/<int:event_id>/unregister', methods=['POST'])
@login_required
def unregister_from_event(event_id):
    """Unregister from an event"""
    if current_user.role != 'student':
        flash('Invalid action.', 'danger')
        return redirect(url_for('events.event_details', event_id=event_id))
    
    conn = get_db_connection()
    
    try:
        # Delete registration
        conn.execute(
            "DELETE FROM event_registrations WHERE event_id = ? AND user_id = ?",
            (event_id, current_user.id)
        )
        
        # Also leave any teams for this event
        conn.execute(
            """DELETE FROM team_members 
               WHERE user_id = ? AND team_id IN (SELECT id FROM teams WHERE event_id = ?)""",
            (current_user.id, event_id)
        )
        
        conn.commit()
        flash('Successfully unregistered from the event.', 'success')
    except Exception as e:
        flash(f'Error unregistering: {str(e)}', 'danger')
    finally:
        conn.close()
    
    return redirect(url_for('events.browse_events'))

@events_bp.route('/my-events')
@login_required
def my_events():
    """View events the user has registered for"""
    if current_user.role != 'student':
        flash('This page is for students only.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    conn = get_db_connection()
    
    events = conn.execute(
        """SELECT e.*, er.registration_status, er.registered_at, u.full_name as manager_name
           FROM event_registrations er
           JOIN events e ON er.event_id = e.id
           JOIN users u ON e.manager_id = u.id
           WHERE er.user_id = ?
           ORDER BY e.start_date ASC""",
        (current_user.id,)
    ).fetchall()
    
    # Get team information for each event
    teams = {}
    for event in events:
        team = conn.execute(
            """SELECT t.*, tm.role as member_role
               FROM teams t
               JOIN team_members tm ON t.id = tm.team_id
               WHERE t.event_id = ? AND tm.user_id = ? AND tm.status = 'active'""",
            (event['id'], current_user.id)
        ).fetchone()
        teams[event['id']] = team
    
    conn.close()
    
    return render_template('my_events.html',
                         user=current_user,
                         events=events,
                         teams=teams)

@events_bp.route('/team/<int:team_id>')
@login_required
def team_details(team_id):
    """View team details"""
    conn = get_db_connection()
    
    team = conn.execute(
        """SELECT t.*, e.title as event_title, u.username as leader_name
           FROM teams t
           JOIN events e ON t.event_id = e.id
           JOIN users u ON t.leader_id = u.id
           WHERE t.id = ?""",
        (team_id,)
    ).fetchone()
    
    if not team:
        flash('Team not found.', 'danger')
        conn.close()
        return redirect(url_for('events.browse_events'))
    
    # Get team members
    members = conn.execute(
        """SELECT tm.*, u.username, u.email, u.full_name
           FROM team_members tm
           JOIN users u ON tm.user_id = u.id
           WHERE tm.team_id = ? AND tm.status = 'active'
           ORDER BY tm.joined_at ASC""",
        (team_id,)
    ).fetchall()
    
    # Check if current user is a member
    is_member = False
    user_role = None
    if current_user.role == 'student':
        member_check = conn.execute(
            "SELECT role FROM team_members WHERE team_id = ? AND user_id = ? AND status = 'active'",
            (team_id, current_user.id)
        ).fetchone()
        if member_check:
            is_member = True
            user_role = member_check['role']
    
    # Get pending join requests (for team leader only)
    pending_requests = []
    is_leader = False
    if team['leader_id'] == current_user.id:
        is_leader = True
        pending_requests = conn.execute(
            """SELECT tm.*, u.username, u.email, u.full_name
               FROM team_members tm
               JOIN users u ON tm.user_id = u.id
               WHERE tm.team_id = ? AND tm.status = 'pending'
               ORDER BY tm.joined_at DESC""",
            (team_id,)
        ).fetchall()

    # Get team files for this team
    team_files = conn.execute(
        """SELECT tf.*, u.full_name AS uploader_name, u.username AS uploader_username
               FROM team_files tf
               JOIN users u ON tf.uploaded_by = u.id
               WHERE tf.team_id = ?
               ORDER BY tf.uploaded_at DESC""",
        (team_id,)
    ).fetchall()

    conn.close()

    return render_template('team_details.html',
                         user=current_user,
                         team=team,
                         members=members,
                         is_member=is_member,
                         user_role=user_role,
                         pending_requests=pending_requests,
                         is_leader=is_leader,
                         team_files=team_files)

@events_bp.route('/team/<int:team_id>/join', methods=['POST'])
@login_required
def join_team(team_id):
    """Request to join a team"""
    if current_user.role != 'student':
        flash('Only students can join teams.', 'danger')
        return redirect(url_for('events.team_details', team_id=team_id))
    
    conn = get_db_connection()
    
    try:
        # Check if team exists and is open
        team = conn.execute(
            "SELECT * FROM teams WHERE id = ? AND is_open = 1",
            (team_id,)
        ).fetchone()
        
        if not team:
            flash('Team not found or not accepting members.', 'danger')
            conn.close()
            return redirect(url_for('events.browse_events'))
        
        # Check if already a member
        existing = conn.execute(
            "SELECT * FROM team_members WHERE team_id = ? AND user_id = ?",
            (team_id, current_user.id)
        ).fetchone()
        
        if existing:
            flash('You are already associated with this team.', 'warning')
            conn.close()
            return redirect(url_for('events.team_details', team_id=team_id))
        
        # Add as pending member
        conn.execute(
            "INSERT INTO team_members (team_id, user_id, status) VALUES (?, ?, 'pending')",
            (team_id, current_user.id)
        )
        
        # Notify team leader
        conn.execute(
            "INSERT INTO notifications (user_id, title, message, type) VALUES (?, ?, ?, ?)",
            (team['leader_id'], 'Team Join Request',
             f'{current_user.username} wants to join your team "{team["name"]}"', 'info')
        )
        
        conn.commit()
        flash('Join request sent to team leader!', 'success')
    except Exception as e:
        flash(f'Error joining team: {str(e)}', 'danger')
    finally:
        conn.close()
    
    return redirect(url_for('events.team_details', team_id=team_id))

@events_bp.route('/team/<int:team_id>/accept/<int:user_id>', methods=['POST'])
@login_required
def accept_team_request(team_id, user_id):
    """Accept a team join request"""
    conn = get_db_connection()
    
    # Verify current user is team leader
    team = conn.execute(
        "SELECT leader_id, name FROM teams WHERE id = ?", (team_id,)
    ).fetchone()
    
    if not team or team['leader_id'] != current_user.id:
        flash('Only team leaders can accept requests.', 'danger')
        conn.close()
        return redirect(url_for('events.team_details', team_id=team_id))
    
    try:
        # Update member status to active
        result = conn.execute(
            """UPDATE team_members 
               SET status = 'active', joined_at = CURRENT_TIMESTAMP
               WHERE team_id = ? AND user_id = ? AND status = 'pending'""",
            (team_id, user_id)
        )
        
        if result.rowcount > 0:
            # Create notification for accepted user
            conn.execute(
                """INSERT INTO notifications (user_id, title, message, type, link, created_at)
                   VALUES (?, ?, ?, 'success', ?, CURRENT_TIMESTAMP)""",
                (user_id, 'Team Request Accepted', 
                 f'Your request to join {team["name"]} has been accepted!',
                 f'/events/team/{team_id}')
            )
            
            conn.commit()
            flash('Team member accepted successfully!', 'success')
        else:
            flash('Request not found or already processed.', 'warning')
    except Exception as e:
        conn.rollback()
        flash(f'Error accepting member: {str(e)}', 'danger')
    finally:
        conn.close()
    
    return redirect(url_for('events.team_details', team_id=team_id))

@events_bp.route('/team/<int:team_id>/reject/<int:user_id>', methods=['POST'])
@login_required
def reject_team_request(team_id, user_id):
    """Reject a team join request"""
    conn = get_db_connection()
    
    # Verify current user is team leader
    team = conn.execute(
        "SELECT leader_id, name FROM teams WHERE id = ?", (team_id,)
    ).fetchone()
    
    if not team or team['leader_id'] != current_user.id:
        flash('Only team leaders can reject requests.', 'danger')
        conn.close()
        return redirect(url_for('events.team_details', team_id=team_id))
    
    try:
        # Remove pending member
        result = conn.execute(
            """DELETE FROM team_members 
               WHERE team_id = ? AND user_id = ? AND status = 'pending'""",
            (team_id, user_id)
        )
        
        if result.rowcount > 0:
            # Create notification for rejected user
            conn.execute(
                """INSERT INTO notifications (user_id, title, message, type, created_at)
                   VALUES (?, ?, ?, 'warning', CURRENT_TIMESTAMP)""",
                (user_id, 'Team Request Declined', 
                 f'Your request to join {team["name"]} has been declined.')
            )
            
            conn.commit()
            flash('Team request rejected.', 'info')
        else:
            flash('Request not found or already processed.', 'warning')
    except Exception as e:
        conn.rollback()
        flash(f'Error rejecting request: {str(e)}', 'danger')
    finally:
        conn.close()
    
    return redirect(url_for('events.team_details', team_id=team_id))
