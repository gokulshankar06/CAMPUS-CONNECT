from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app, send_from_directory
from flask_login import login_required, current_user
import secrets
from datetime import datetime, timedelta
import re
import os

from werkzeug.utils import secure_filename
from models import get_db_connection
from utils.email_utils import send_email

teams_bp = Blueprint('teams', __name__, url_prefix='/teams')

def generate_team_code():
    """Generate a unique team invitation code"""
    return secrets.token_urlsafe(8)

def generate_invitation_token():
    """Generate a unique invitation token"""
    return secrets.token_urlsafe(32)

@teams_bp.route('/create/<int:event_id>', methods=['GET', 'POST'])
@login_required
def create_team(event_id):
    """Create a new team for an event"""
    if current_user.role != 'student':
        flash('Only students can create teams.', 'danger')
        return redirect(url_for('events.event_details', event_id=event_id))
    
    conn = get_db_connection()
    
    # Check if event exists and allows teams
    event = conn.execute("""
        SELECT * FROM events 
        WHERE id = ? AND is_team_event = 1 AND status IN ('upcoming', 'ongoing')
    """, (event_id,)).fetchone()
    
    if not event:
        flash('Event not found or does not allow team participation.', 'danger')
        conn.close()
        return redirect(url_for('events.browse_events'))
    
    # Check if user is already in a team for this event
    existing_team = conn.execute("""
        SELECT t.* FROM teams t
        JOIN team_members tm ON t.id = tm.team_id
        WHERE t.event_id = ? AND tm.user_id = ? AND tm.status = 'active'
    """, (event_id, current_user.id)).fetchone()
    
    if existing_team:
        flash('You are already part of a team for this event.', 'warning')
        conn.close()
        return redirect(url_for('teams.team_dashboard', team_id=existing_team['id']))
    
    if request.method == 'POST':
        team_name = request.form.get('team_name', '').strip()
        description = request.form.get('description', '').strip()
        max_members = int(request.form.get('max_members', event['max_team_size']))
        is_public = request.form.get('is_public') == 'on'
        
        if not team_name:
            flash('Team name is required.', 'danger')
            conn.close()
            return render_template('create_team.html', event=event, user=current_user)
        
        if len(team_name) < 3:
            flash('Team name must be at least 3 characters long.', 'danger')
            conn.close()
            return render_template('create_team.html', event=event, user=current_user)
        
        if max_members > event['max_team_size']:
            max_members = event['max_team_size']
        
        if max_members < event['min_team_size']:
            max_members = event['min_team_size']
        
        try:
            # Generate unique codes
            team_code = generate_team_code()
            invitation_code = generate_team_code()
            
            # Create team
            cursor = conn.execute("""
                INSERT INTO teams 
                (name, description, event_id, leader_id, max_members, team_code, 
                 invitation_code, is_public, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'forming')
            """, (team_name, description, event_id, current_user.id, max_members, 
                  team_code, invitation_code, is_public))
            
            team_id = cursor.lastrowid
            
            # Add creator as team leader
            conn.execute("""
                INSERT INTO team_members (team_id, user_id, role, status)
                VALUES (?, ?, 'leader', 'active')
            """, (team_id, current_user.id))
            
            # Log activity
            conn.execute("""
                INSERT INTO team_activity_logs 
                (team_id, user_id, activity_type, description)
                VALUES (?, ?, 'joined', 'Created the team and became team leader')
            """, (team_id, current_user.id))
            
            conn.commit()
            flash(f'Team "{team_name}" created successfully!', 'success')
            return redirect(url_for('teams.team_dashboard', team_id=team_id))
            
        except Exception as e:
            conn.rollback()
            flash(f'Error creating team: {str(e)}', 'danger')
        finally:
            conn.close()
    
    conn.close()
    return render_template('create_team.html', event=event, user=current_user)

@teams_bp.route('/dashboard/<int:team_id>')
@login_required
def team_dashboard(team_id):
    """Team dashboard for members"""
    conn = get_db_connection()
    
    # Get team details
    team = conn.execute("""
        SELECT t.*, e.title as event_title, e.event_type, e.start_date, e.end_date,
               u.username as leader_name, u.full_name as leader_full_name
        FROM teams t
        JOIN events e ON t.event_id = e.id
        JOIN users u ON t.leader_id = u.id
        WHERE t.id = ?
    """, (team_id,)).fetchone()
    
    if not team:
        flash('Team not found.', 'danger')
        conn.close()
        return redirect(url_for('events.browse_events'))
    
    # Check if user is a team member
    membership = conn.execute("""
        SELECT * FROM team_members 
        WHERE team_id = ? AND user_id = ? AND status = 'active'
    """, (team_id, current_user.id)).fetchone()
    
    if not membership:
        flash('You are not a member of this team.', 'danger')
        conn.close()
        return redirect(url_for('events.event_details', event_id=team['event_id']))
    
    # Get team members
    members = conn.execute("""
        SELECT tm.*, u.username, u.full_name, u.profile_picture, u.department
        FROM team_members tm
        JOIN users u ON tm.user_id = u.id
        WHERE tm.team_id = ? AND tm.status = 'active'
        ORDER BY tm.role DESC, tm.joined_at ASC
    """, (team_id,)).fetchall()
    
    # Get pending invitations
    pending_invitations = conn.execute("""
        SELECT ti.*, u.username as inviter_name
        FROM team_invitations ti
        JOIN users u ON ti.inviter_id = u.id
        WHERE ti.team_id = ? AND ti.status = 'pending'
        ORDER BY ti.created_at DESC
    """, (team_id,)).fetchall()
    
    # Get team activities
    activities = conn.execute("""
        SELECT tal.*, u.username, u.full_name
        FROM team_activity_logs tal
        JOIN users u ON tal.user_id = u.id
        WHERE tal.team_id = ?
        ORDER BY tal.created_at DESC
        LIMIT 20
    """, (team_id,)).fetchall()
    
    # Get abstract submission if applicable
    abstract_submission = None
    event_requirements = conn.execute("""
        SELECT * FROM event_requirements WHERE event_id = ?
    """, (team['event_id'],)).fetchone()
    
    if event_requirements and event_requirements['requires_abstract']:
        abstract_submission = conn.execute("""
            SELECT * FROM abstract_submissions 
            WHERE team_id = ? AND is_latest_version = 1
        """, (team_id,)).fetchone()
    
    # Get pending join requests count if user is leader
    pending_requests_count = 0
    if membership['role'] == 'leader':
        pending_requests_count = conn.execute("""
            SELECT COUNT(*) FROM team_join_requests 
            WHERE team_id = ? AND status = 'pending'
        """, (team_id,)).fetchone()[0]
    
    conn.close()
    
    is_leader = membership['role'] == 'leader'
    
    return render_template('team_dashboard.html', 
                         team=team, members=members, pending_invitations=pending_invitations,
                         activities=activities, abstract_submission=abstract_submission,
                         event_requirements=event_requirements, is_leader=is_leader, 
                         pending_requests_count=pending_requests_count, user=current_user)

@teams_bp.route('/invite/<int:team_id>', methods=['POST'])
@login_required
def invite_member(team_id):
    """Invite a member to join the team"""
    conn = get_db_connection()
    
    # Check if user is team leader
    team = conn.execute("""
        SELECT t.*, e.title as event_title
        FROM teams t
        JOIN events e ON t.event_id = e.id
        WHERE t.id = ? AND t.leader_id = ?
    """, (team_id, current_user.id)).fetchone()
    
    if not team:
        flash('Team not found or you are not the team leader.', 'danger')
        conn.close()
        return redirect(url_for('events.browse_events'))
    
    invitee_email = request.form.get('invitee_email', '').strip().lower()
    message = request.form.get('message', '').strip()
    
    if not invitee_email:
        flash('Email address is required.', 'danger')
        conn.close()
        return redirect(url_for('teams.team_dashboard', team_id=team_id))
    
    # Validate email format
    if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', invitee_email):
        flash('Invalid email address format.', 'danger')
        conn.close()
        return redirect(url_for('teams.team_dashboard', team_id=team_id))
    
    # Check if team is full
    current_members = conn.execute("""
        SELECT COUNT(*) as count FROM team_members 
        WHERE team_id = ? AND status = 'active'
    """, (team_id,)).fetchone()
    
    if current_members['count'] >= team['max_members']:
        flash('Team is already at maximum capacity.', 'danger')
        conn.close()
        return redirect(url_for('teams.team_dashboard', team_id=team_id))
    
    # Check if user exists
    invitee = conn.execute("""
        SELECT * FROM users WHERE email = ? AND role = 'student'
    """, (invitee_email,)).fetchone()
    
    if not invitee:
        flash('User not found or not a student.', 'danger')
        conn.close()
        return redirect(url_for('teams.team_dashboard', team_id=team_id))
    
    # Check if user is already a team member
    existing_member = conn.execute("""
        SELECT * FROM team_members 
        WHERE team_id = ? AND user_id = ? AND status = 'active'
    """, (team_id, invitee['id'])).fetchone()
    
    if existing_member:
        flash('User is already a team member.', 'warning')
        conn.close()
        return redirect(url_for('teams.team_dashboard', team_id=team_id))
    
    # Check if user is already in another team for this event
    existing_team_member = conn.execute("""
        SELECT t.name FROM teams t
        JOIN team_members tm ON t.id = tm.team_id
        WHERE t.event_id = ? AND tm.user_id = ? AND tm.status = 'active'
    """, (team['event_id'], invitee['id'])).fetchone()
    
    if existing_team_member:
        flash(f'User is already a member of team "{existing_team_member["name"]}" for this event.', 'warning')
        conn.close()
        return redirect(url_for('teams.team_dashboard', team_id=team_id))
    
    # Check if invitation already exists
    existing_invitation = conn.execute("""
        SELECT * FROM team_invitations 
        WHERE team_id = ? AND invitee_email = ? AND status = 'pending'
    """, (team_id, invitee_email)).fetchone()
    
    if existing_invitation:
        flash('Invitation already sent to this user.', 'warning')
        conn.close()
        return redirect(url_for('teams.team_dashboard', team_id=team_id))
    
    try:
        # Create invitation
        invitation_token = generate_invitation_token()
        expires_at = datetime.now() + timedelta(days=7)  # 7 days to respond
        
        conn.execute("""
            INSERT INTO team_invitations 
            (team_id, inviter_id, invitee_email, invitee_id, invitation_token, 
             message, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (team_id, current_user.id, invitee_email, invitee['id'], 
              invitation_token, message, expires_at))
        
        # Log activity
        conn.execute("""
            INSERT INTO team_activity_logs 
            (team_id, user_id, activity_type, description)
            VALUES (?, ?, 'invited', ?)
        """, (team_id, current_user.id, f'Invited {invitee["username"]} to join the team'))
        
        # Send notification to invitee
        conn.execute("""
            INSERT INTO notifications (user_id, type, title, message, link)
            VALUES (?, 'team_invitation', 'Team Invitation', ?, ?)
        """, (invitee['id'], 
              f'You have been invited to join team "{team["name"]}" for "{team["event_title"]}"',
              f'/teams/invitation/{invitation_token}'))
        
        conn.commit()
        
        # Send email notification (if email service is configured)
        try:
            invitation_link = url_for('teams.respond_invitation', token=invitation_token, _external=True)
            email_subject = f'Team Invitation: {team["name"]} - {team["event_title"]}'
            email_body = f"""
            Hi {invitee['full_name'] or invitee['username']},
            
            You have been invited by {current_user.full_name or current_user.username} to join the team "{team['name']}" for the event "{team['event_title']}".
            
            {f'Message from team leader: {message}' if message else ''}
            
            Click the link below to respond to this invitation:
            {invitation_link}
            
            This invitation expires in 7 days.
            
            Best regards,
            CampusConnect Team
            """
            
            send_email(invitee_email, email_subject, email_body)
        except Exception as email_error:
            print(f"Failed to send email notification: {email_error}")
        
        flash(f'Invitation sent to {invitee_email} successfully!', 'success')
        
    except Exception as e:
        conn.rollback()
        flash(f'Error sending invitation: {str(e)}', 'danger')
    finally:
        conn.close()
    
    return redirect(url_for('teams.team_dashboard', team_id=team_id))

@teams_bp.route('/invitation/<token>')
@login_required
def respond_invitation(token):
    """View team invitation"""
    conn = get_db_connection()
    
    invitation = conn.execute("""
        SELECT ti.*, t.name as team_name, t.description, t.max_members,
               e.title as event_title, e.event_type, e.start_date, e.end_date,
               u.username as inviter_name, u.full_name as inviter_full_name
        FROM team_invitations ti
        JOIN teams t ON ti.team_id = t.id
        JOIN events e ON t.event_id = e.id
        JOIN users u ON ti.inviter_id = u.id
        WHERE ti.invitation_token = ? AND ti.status = 'pending'
    """, (token,)).fetchone()
    
    if not invitation:
        flash('Invitation not found or has expired.', 'danger')
        conn.close()
        return redirect(url_for('events.browse_events'))
    
    # Check if invitation has expired
    if datetime.now() > datetime.fromisoformat(invitation['expires_at']):
        conn.execute("""
            UPDATE team_invitations SET status = 'expired' WHERE invitation_token = ?
        """, (token,))
        conn.commit()
        flash('This invitation has expired.', 'warning')
        conn.close()
        return redirect(url_for('events.browse_events'))
    
    # Check if user is the intended recipient
    if current_user.id != invitation['invitee_id']:
        flash('This invitation is not for you.', 'danger')
        conn.close()
        return redirect(url_for('events.browse_events'))
    
    # Get current team members
    members = conn.execute("""
        SELECT tm.*, u.username, u.full_name
        FROM team_members tm
        JOIN users u ON tm.user_id = u.id
        WHERE tm.team_id = ? AND tm.status = 'active'
        ORDER BY tm.role DESC, tm.joined_at ASC
    """, (invitation['team_id'],)).fetchall()
    
    conn.close()
    return render_template('team_invitation.html', invitation=invitation, members=members, user=current_user)

@teams_bp.route('/invitation/<token>/accept', methods=['POST'])
@login_required
def accept_invitation(token):
    """Accept team invitation"""
    conn = get_db_connection()
    
    invitation = conn.execute("""
        SELECT ti.*, t.event_id, t.max_members
        FROM team_invitations ti
        JOIN teams t ON ti.team_id = t.id
        WHERE ti.invitation_token = ? AND ti.status = 'pending' AND ti.invitee_id = ?
    """, (token, current_user.id)).fetchone()
    
    if not invitation:
        flash('Invitation not found or invalid.', 'danger')
        conn.close()
        return redirect(url_for('events.browse_events'))
    
    # Check if user is already in a team for this event
    existing_team = conn.execute("""
        SELECT t.name FROM teams t
        JOIN team_members tm ON t.id = tm.team_id
        WHERE t.event_id = ? AND tm.user_id = ? AND tm.status = 'active'
    """, (invitation['event_id'], current_user.id)).fetchone()
    
    if existing_team:
        flash(f'You are already a member of team "{existing_team["name"]}" for this event.', 'warning')
        conn.close()
        return redirect(url_for('events.browse_events'))
    
    # Check if team is full
    current_members = conn.execute("""
        SELECT COUNT(*) as count FROM team_members 
        WHERE team_id = ? AND status = 'active'
    """, (invitation['team_id'],)).fetchone()
    
    if current_members['count'] >= invitation['max_members']:
        flash('Team is already at maximum capacity.', 'warning')
        conn.close()
        return redirect(url_for('events.browse_events'))
    
    try:
        # Accept invitation
        conn.execute("""
            UPDATE team_invitations 
            SET status = 'accepted', responded_at = CURRENT_TIMESTAMP
            WHERE invitation_token = ?
        """, (token,))
        
        # Add user to team
        conn.execute("""
            INSERT INTO team_members (team_id, user_id, role, status)
            VALUES (?, ?, 'member', 'active')
        """, (invitation['team_id'], current_user.id))
        
        # Log activity
        conn.execute("""
            INSERT INTO team_activity_logs 
            (team_id, user_id, activity_type, description)
            VALUES (?, ?, 'joined', 'Accepted team invitation and joined the team')
        """, (invitation['team_id'], current_user.id))
        
        conn.commit()
        flash('You have successfully joined the team!', 'success')
        return redirect(url_for('teams.team_dashboard', team_id=invitation['team_id']))
        
    except Exception as e:
        conn.rollback()
        flash(f'Error accepting invitation: {str(e)}', 'danger')
    finally:
        conn.close()
    
    return redirect(url_for('events.browse_events'))

@teams_bp.route('/invitation/<token>/decline', methods=['POST'])
@login_required
def decline_invitation(token):
    """Decline a team invitation"""
    conn = get_db_connection()
    invitation = conn.execute(
        'SELECT * FROM team_invitations WHERE invitation_token = ?', (token,)
    ).fetchone()
    
    if not invitation:
        flash('Invitation not found or invalid.', 'danger')
        conn.close()
        return redirect(url_for('events.browse_events'))
    
    try:
        # Decline invitation
        conn.execute("""
            UPDATE team_invitations 
            SET status = 'declined', responded_at = CURRENT_TIMESTAMP
            WHERE invitation_token = ?
        """, (token,))
        
        # Log activity
        conn.execute("""
            INSERT INTO team_activity_logs 
            (team_id, user_id, activity_type, description)
            VALUES (?, ?, 'invitation_declined', ?)
        """, (invitation['team_id'], current_user.id, 
              f'{current_user.username} declined the team invitation'))
        
        conn.commit()
        flash('You have declined the team invitation.', 'info')
        
    except Exception as e:
        conn.rollback()
        flash(f'Error declining invitation: {str(e)}', 'danger')
    finally:
        conn.close()
    
    return redirect(url_for('events.browse_events'))

@teams_bp.route('/<int:team_id>/requests')
@login_required
def view_join_requests(team_id):
    """View join requests for a team"""
    conn = get_db_connection()
    
    # Get team details and verify user is the team leader
    team = conn.execute(
        'SELECT t.id, t.name, t.description, t.leader_id, t.event_id, t.status, '
        't.max_members, t.is_open, t.team_code, t.created_at, '
        'e.title as event_title FROM teams t '
        'JOIN events e ON t.event_id = e.id WHERE t.id = ?', (team_id,)
    ).fetchone()
    
    if not team:
        flash('Team not found.', 'danger')
        conn.close()
        return redirect(url_for('events.browse_events'))
        
    if team['leader_id'] != current_user.id:
        flash('Only team leaders can view join requests.', 'warning')
        conn.close()
        return redirect(url_for('teams.team_dashboard', team_id=team_id))
    
    # Get pending join requests
    requests = conn.execute("""
        SELECT r.*, u.username, u.email, u.full_name, u.profile_picture,
               strftime('%Y-%m-%d %H:%M', r.requested_at) as requested_at_formatted
        FROM team_join_requests r
        JOIN users u ON r.user_id = u.id
        WHERE r.team_id = ? AND r.status = 'pending'
        ORDER BY r.requested_at DESC
    """, (team_id,)).fetchall()
    
    # Get count of pending requests for the badge
    pending_count = len(requests)
    
    conn.close()
    
    return render_template('team_requests.html', 
                         team=dict(team),  # Convert Row to dict for template
                         requests=requests,
                         pending_requests_count=pending_count)

@teams_bp.route('/leave/<int:team_id>', methods=['POST'])
@login_required
def leave_team(team_id):
    """Leave a team"""
    conn = get_db_connection()
    
    # Check if user is a team member
    membership = conn.execute("""
        SELECT tm.*, t.leader_id, t.event_id
        FROM team_members tm
        JOIN teams t ON tm.team_id = t.id
        WHERE tm.team_id = ? AND tm.user_id = ? AND tm.status = 'active'
    """, (team_id, current_user.id)).fetchone()
    
    if not membership:
        flash('You are not a member of this team.', 'danger')
        conn.close()
        return redirect(url_for('events.browse_events'))
    
    # Check if user is the team leader
    if membership['leader_id'] == current_user.id:
        # Count other active members
        other_members = conn.execute("""
            SELECT COUNT(*) as count FROM team_members 
            WHERE team_id = ? AND user_id != ? AND status = 'active'
        """, (team_id, current_user.id)).fetchone()
        
        if other_members['count'] > 0:
            flash('As team leader, you must transfer leadership or remove all members before leaving.', 'warning')
            conn.close()
            return redirect(url_for('teams.team_dashboard', team_id=team_id))
    
    try:
        # Remove user from team
        conn.execute("""
            UPDATE team_members 
            SET status = 'removed', left_at = CURRENT_TIMESTAMP
            WHERE team_id = ? AND user_id = ?
        """, (team_id, current_user.id))
        
        # Log activity
        conn.execute("""
            INSERT INTO team_activity_logs 
            (team_id, user_id, activity_type, description)
            VALUES (?, ?, 'left', 'Left the team')
        """, (team_id, current_user.id))
        
        conn.commit()
        flash('You have left the team.', 'info')
        return redirect(url_for('events.event_details', event_id=membership['event_id']))
        
    except Exception as e:
        conn.rollback()
        flash(f'Error leaving team: {str(e)}', 'danger')
    finally:
        conn.close()
    
    return redirect(url_for('teams.team_dashboard', team_id=team_id))

@teams_bp.route('/<int:team_id>/files/upload', methods=['POST'])
@login_required
def upload_team_file(team_id):
    """Upload a file to the team workspace"""
    if current_user.role != 'student':
        flash('Only students can upload team files.', 'danger')
        return redirect(url_for('events.team_details', team_id=team_id))

    conn = get_db_connection()
    try:
        # Ensure user is an active team member
        membership = conn.execute(
            """
            SELECT * FROM team_members
            WHERE team_id = ? AND user_id = ? AND status = 'active'
            """,
            (team_id, current_user.id),
        ).fetchone()

        if not membership:
            flash('You must be a member of this team to upload files.', 'danger')
            return redirect(url_for('events.team_details', team_id=team_id))

        file = request.files.get('file')
        if not file or file.filename == '':
            flash('No file selected for upload.', 'danger')
            return redirect(url_for('events.team_details', team_id=team_id))

        filename = secure_filename(file.filename)
        if not filename:
            flash('Invalid file name.', 'danger')
            return redirect(url_for('events.team_details', team_id=team_id))

        base_folder = current_app.config.get('UPLOAD_FOLDER', 'uploads')
        team_folder = os.path.join(base_folder, 'teams', str(team_id))
        os.makedirs(team_folder, exist_ok=True)

        file_path = os.path.join(team_folder, filename)
        file.save(file_path)

        file_size = os.path.getsize(file_path)
        file_type = file.mimetype

        conn.execute(
            """
            INSERT INTO team_files (team_id, file_name, file_path, file_size, file_type, uploaded_by)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (team_id, filename, file_path, file_size, file_type, current_user.id),
        )

        conn.commit()
        flash('File uploaded to team workspace.', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Error uploading file: {str(e)}', 'danger')
    finally:
        conn.close()

    return redirect(url_for('events.team_details', team_id=team_id))

@teams_bp.route('/<int:team_id>/files/<int:file_id>/download')
@login_required
def download_team_file(team_id, file_id):
    """Download a team file if the user is a team member"""
    conn = get_db_connection()
    try:
        # Ensure user is a member of the team
        membership = conn.execute(
            """SELECT * FROM team_members
                   WHERE team_id = ? AND user_id = ? AND status = 'active'""",
            (team_id, current_user.id),
        ).fetchone()

        if not membership:
            flash('You must be a member of this team to access its files.', 'danger')
            return redirect(url_for('events.team_details', team_id=team_id))

        file_row = conn.execute(
            """SELECT * FROM team_files
                   WHERE id = ? AND team_id = ?""",
            (file_id, team_id),
        ).fetchone()

        if not file_row:
            flash('File not found.', 'danger')
            return redirect(url_for('events.team_details', team_id=team_id))

        file_path = file_row['file_path']
        directory, filename = os.path.split(file_path)

        # send_from_directory is relative to the Flask app root
        return send_from_directory(directory, filename, as_attachment=True)
    finally:
        conn.close()
