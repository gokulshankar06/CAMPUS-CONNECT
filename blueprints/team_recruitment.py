from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from datetime import datetime
import json

from models import get_db_connection

team_recruitment_bp = Blueprint('team_recruitment', __name__, url_prefix='/teams')

@team_recruitment_bp.route('/<int:team_id>/vacancies')
@login_required
def view_vacancies(team_id):
    """View all vacancies for a team"""
    conn = get_db_connection()
    
    team = conn.execute("""
        SELECT t.*, e.title as event_title
        FROM teams t
        JOIN events e ON t.event_id = e.id
        WHERE t.id = ?
    """, (team_id,)).fetchone()
    
    if not team:
        flash('Team not found.', 'danger')
        conn.close()
        return redirect(url_for('events.browse_events'))
    
    # Get team vacancies
    vacancies = conn.execute("""
        SELECT v.*, u.username as created_by_name
        FROM team_vacancies v
        JOIN users u ON v.created_by = u.id
        WHERE v.team_id = ? AND v.status = 'open'
        ORDER BY v.created_at DESC
    """, (team_id,)).fetchall()
    
    # Check if user is team leader
    is_leader = False
    if current_user.id:
        leader_check = conn.execute("""
            SELECT 1 FROM team_members 
            WHERE team_id = ? AND user_id = ? AND role = 'leader' AND status = 'active'
        """, (team_id, current_user.id)).fetchone()
        is_leader = leader_check is not None
    
    conn.close()
    return render_template('team_vacancies.html', team=team, vacancies=vacancies, 
                           is_leader=is_leader, user=current_user)

@team_recruitment_bp.route('/<int:team_id>/vacancy/create', methods=['GET', 'POST'])
@login_required
def create_vacancy(team_id):
    """Create a new team vacancy"""
    if current_user.role != 'student':
        flash('Only students can create team vacancies.', 'danger')
        return redirect(url_for('teams.team_dashboard', team_id=team_id))
    
    conn = get_db_connection()
    
    # Check if user is team leader
    team_leader = conn.execute("""
        SELECT t.*, tm.role FROM teams t
        JOIN team_members tm ON t.id = tm.team_id
        WHERE t.id = ? AND tm.user_id = ? AND tm.role = 'leader' AND tm.status = 'active'
    """, (team_id, current_user.id)).fetchone()
    
    if not team_leader:
        flash('Only team leaders can create vacancies.', 'danger')
        conn.close()
        return redirect(url_for('teams.team_dashboard', team_id=team_id))
    
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        role = request.form.get('role', '').strip()
        required_skills = request.form.get('required_skills', '').strip()
        preferred_skills = request.form.get('preferred_skills', '').strip()
        slots_available = int(request.form.get('slots_available', 1))
        
        if not title or not description or not role:
            flash('Title, description, and role are required.', 'danger')
            conn.close()
            return render_template('create_vacancy.html', team=team_leader, user=current_user)
        
        try:
            conn.execute("""
                INSERT INTO team_vacancies 
                (team_id, title, description, role, required_skills, preferred_skills, 
                 slots_available, created_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (team_id, title, description, role, required_skills, preferred_skills,
                  slots_available, current_user.id))
            
            conn.commit()
            flash('Vacancy created successfully!', 'success')
            
        except Exception as e:
            conn.rollback()
            flash(f'Error creating vacancy: {str(e)}', 'danger')
        finally:
            conn.close()
        
        return redirect(url_for('team_recruitment.view_vacancies', team_id=team_id))
    
    # Get all available skills for the form
    skills = conn.execute("SELECT * FROM skills ORDER BY category, name").fetchall()
    conn.close()
    
    return render_template('create_vacancy.html', team=team_leader, skills=skills, user=current_user)

@team_recruitment_bp.route('/browse_teams/<int:event_id>')
@login_required
def browse_teams(event_id):
    """Browse teams with open vacancies for an event"""
    if current_user.role != 'student':
        flash('Only students can browse teams.', 'danger')
        return redirect(url_for('events.event_details', event_id=event_id))
    
    conn = get_db_connection()
    
    # Get event details
    event = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    
    if not event:
        flash('Event not found.', 'danger')
        conn.close()
        return redirect(url_for('events.browse_events'))
    
    # Get teams with open vacancies
    teams_with_vacancies = conn.execute("""
        SELECT t.*, 
               COUNT(DISTINCT tm.user_id) as current_members,
               COUNT(DISTINCT v.id) as open_vacancies,
               u.username as leader_name,
               u.full_name as leader_full_name
        FROM teams t
        LEFT JOIN team_members tm ON t.id = tm.team_id AND tm.status = 'active'
        LEFT JOIN team_vacancies v ON t.id = v.team_id AND v.status = 'open'
        JOIN users u ON t.leader_id = u.id
        WHERE t.event_id = ? AND t.is_public = 1 AND t.status = 'forming'
        GROUP BY t.id
        HAVING open_vacancies > 0 OR current_members < t.max_members
        ORDER BY open_vacancies DESC, t.created_at DESC
    """, (event_id,)).fetchall()
    
    # Check which teams user has already applied to
    user_applications = {}
    if current_user.id:
        applications = conn.execute("""
            SELECT team_id, status FROM team_join_requests
            WHERE user_id = ?
        """, (current_user.id,)).fetchall()
        user_applications = {app['team_id']: app['status'] for app in applications}
    
    conn.close()
    return render_template('browse_teams.html', event=event, teams=teams_with_vacancies,
                           user_applications=user_applications, user=current_user)

@team_recruitment_bp.route('/<int:team_id>/apply', methods=['GET', 'POST'])
@login_required
def apply_to_team(team_id):
    """Apply to join a team"""
    if current_user.role != 'student':
        flash('Only students can apply to join teams.', 'danger')
        return redirect(url_for('teams.team_dashboard', team_id=team_id))
    
    conn = get_db_connection()
    
    # Get team details
    team = conn.execute("""
        SELECT t.*, e.title as event_title
        FROM teams t
        JOIN events e ON t.event_id = e.id
        WHERE t.id = ?
    """, (team_id,)).fetchone()
    
    if not team:
        flash('Team not found.', 'danger')
        conn.close()
        return redirect(url_for('events.browse_events'))
    
    # Check if user is already in a team for this event
    existing_team = conn.execute("""
        SELECT t.name FROM teams t
        JOIN team_members tm ON t.id = tm.team_id
        WHERE t.event_id = ? AND tm.user_id = ? AND tm.status = 'active'
    """, (team['event_id'], current_user.id)).fetchone()
    
    if existing_team:
        flash(f'You are already in team "{existing_team["name"]}" for this event.', 'warning')
        conn.close()
        return redirect(url_for('teams.team_dashboard', team_id=team_id))
    
    # Check for existing application
    existing_application = conn.execute("""
        SELECT status FROM team_join_requests
        WHERE team_id = ? AND user_id = ?
    """, (team_id, current_user.id)).fetchone()
    
    if existing_application:
        if existing_application['status'] == 'pending':
            flash('You have already applied to this team. Application is pending review.', 'info')
        elif existing_application['status'] == 'approved':
            flash('Your application has been approved. Please check your notifications.', 'success')
        elif existing_application['status'] == 'rejected':
            flash('Your previous application was rejected.', 'warning')
        conn.close()
        return redirect(url_for('teams.team_dashboard', team_id=team_id))
    
    if request.method == 'POST':
        vacancy_id = request.form.get('vacancy_id')
        message = request.form.get('message', '').strip()
        
        # Get user's skills
        user_skills = conn.execute("""
            SELECT s.name FROM user_skills us
            JOIN skills s ON us.skill_id = s.id
            WHERE us.user_id = ?
        """, (current_user.id,)).fetchall()
        skills_list = [skill['name'] for skill in user_skills]
        skills_match = ', '.join(skills_list) if skills_list else 'No skills listed'
        
        try:
            conn.execute("""
                INSERT INTO team_join_requests 
                (team_id, vacancy_id, user_id, message, skills_match)
                VALUES (?, ?, ?, ?, ?)
            """, (team_id, vacancy_id if vacancy_id else None, current_user.id, 
                  message, skills_match))
            
            # Notify team leader
            conn.execute("""
                INSERT INTO notifications (user_id, type, title, message, link)
                VALUES (?, 'team_application', 'New Team Application', ?, ?)
            """, (team['leader_id'], 
                  f'{current_user.username} has applied to join your team "{team["name"]}"',
                  f'/teams/{team_id}/applications'))
            
            conn.commit()
            flash('Application submitted successfully! The team leader will review it soon.', 'success')
            
        except Exception as e:
            conn.rollback()
            flash(f'Error submitting application: {str(e)}', 'danger')
        finally:
            conn.close()
        
        return redirect(url_for('team_recruitment.browse_teams', event_id=team['event_id']))
    
    # Get team vacancies
    vacancies = conn.execute("""
        SELECT * FROM team_vacancies
        WHERE team_id = ? AND status = 'open'
        ORDER BY created_at DESC
    """, (team_id,)).fetchall()
    
    # Get user's skills
    user_skills = conn.execute("""
        SELECT s.* FROM user_skills us
        JOIN skills s ON us.skill_id = s.id
        WHERE us.user_id = ?
        ORDER BY s.category, s.name
    """, (current_user.id)).fetchall()
    
    conn.close()
    return render_template('apply_to_team.html', team=team, vacancies=vacancies, 
                           user_skills=user_skills, user=current_user)

@team_recruitment_bp.route('/<int:team_id>/applications')
@login_required
def manage_applications(team_id):
    """Manage join requests for a team"""
    conn = get_db_connection()
    
    # Check if user is team leader
    team = conn.execute("""
        SELECT t.*, tm.role, e.title as event_title
        FROM teams t
        JOIN team_members tm ON t.id = tm.team_id
        JOIN events e ON t.event_id = e.id
        WHERE t.id = ? AND tm.user_id = ? AND tm.role = 'leader' AND tm.status = 'active'
    """, (team_id, current_user.id)).fetchone()
    
    if not team:
        flash('Only team leaders can manage applications.', 'danger')
        conn.close()
        return redirect(url_for('teams.team_dashboard', team_id=team_id))
    
    # Get pending applications
    applications = conn.execute("""
        SELECT jr.*, u.username, u.full_name, u.email, u.department, u.year,
               v.title as vacancy_title, v.role as vacancy_role
        FROM team_join_requests jr
        JOIN users u ON jr.user_id = u.id
        LEFT JOIN team_vacancies v ON jr.vacancy_id = v.id
        WHERE jr.team_id = ? AND jr.status = 'pending'
        ORDER BY jr.requested_at DESC
    """, (team_id,)).fetchall()
    
    # Get current team size
    current_members = conn.execute("""
        SELECT COUNT(*) as count FROM team_members
        WHERE team_id = ? AND status = 'active'
    """, (team_id,)).fetchone()['count']
    
    conn.close()
    return render_template('manage_applications.html', team=team, applications=applications,
                           current_members=current_members, user=current_user)

@team_recruitment_bp.route('/application/<int:application_id>/<action>', methods=['POST'])
@login_required
def process_application(application_id, action):
    """Process a team join request"""
    if action not in ['approve', 'reject']:
        flash('Invalid action.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    conn = get_db_connection()
    
    # Get application details
    application = conn.execute("""
        SELECT jr.*, t.name as team_name, t.leader_id, t.max_members, t.event_id,
               u.username, u.email, v.slots_filled, v.slots_available
        FROM team_join_requests jr
        JOIN teams t ON jr.team_id = t.id
        JOIN users u ON jr.user_id = u.id
        LEFT JOIN team_vacancies v ON jr.vacancy_id = v.id
        WHERE jr.id = ? AND jr.status = 'pending'
    """, (application_id,)).fetchone()
    
    if not application:
        flash('Application not found or already processed.', 'warning')
        conn.close()
        return redirect(url_for('main.dashboard'))
    
    # Check if current user is team leader
    if application['leader_id'] != current_user.id:
        flash('Only team leaders can process applications.', 'danger')
        conn.close()
        return redirect(url_for('main.dashboard'))
    
    try:
        if action == 'approve':
            # Check team capacity
            current_members = conn.execute("""
                SELECT COUNT(*) as count FROM team_members
                WHERE team_id = ? AND status = 'active'
            """, (application['team_id'],)).fetchone()['count']
            
            if current_members >= application['max_members']:
                flash('Team is already at maximum capacity.', 'warning')
                conn.close()
                return redirect(url_for('team_recruitment.manage_applications', 
                                        team_id=application['team_id']))
            
            # Approve application
            conn.execute("""
                UPDATE team_join_requests 
                SET status = 'approved', reviewed_at = CURRENT_TIMESTAMP, reviewed_by = ?
                WHERE id = ?
            """, (current_user.id, application_id))
            
            # Add user to team
            conn.execute("""
                INSERT INTO team_members (team_id, user_id, role, status)
                VALUES (?, ?, 'member', 'active')
            """, (application['team_id'], application['user_id']))
            
            # Update vacancy if applicable
            if application['vacancy_id']:
                conn.execute("""
                    UPDATE team_vacancies 
                    SET slots_filled = slots_filled + 1
                    WHERE id = ?
                """, (application['vacancy_id'],))
                
                # Check if vacancy should be closed
                vacancy = conn.execute("""
                    SELECT slots_filled, slots_available FROM team_vacancies
                    WHERE id = ?
                """, (application['vacancy_id'],)).fetchone()
                
                if vacancy and vacancy['slots_filled'] >= vacancy['slots_available']:
                    conn.execute("""
                        UPDATE team_vacancies SET status = 'filled' WHERE id = ?
                    """, (application['vacancy_id'],))
            
            # Send notification
            conn.execute("""
                INSERT INTO notifications (user_id, type, title, message, link)
                VALUES (?, 'team_application', 'Application Approved', ?, ?)
            """, (application['user_id'],
                  f'Your application to join team "{application["team_name"]}" has been approved!',
                  f'/teams/{application["team_id"]}/dashboard'))
            
            flash(f'{application["username"]} has been added to the team!', 'success')
            
        else:  # reject
            rejection_reason = request.form.get('rejection_reason', '').strip()
            
            conn.execute("""
                UPDATE team_join_requests 
                SET status = 'rejected', reviewed_at = CURRENT_TIMESTAMP, 
                    reviewed_by = ?, rejection_reason = ?
                WHERE id = ?
            """, (current_user.id, rejection_reason, application_id))
            
            # Send notification
            message = f'Your application to join team "{application["team_name"]}" has been declined.'
            if rejection_reason:
                message += f' Reason: {rejection_reason}'
            
            conn.execute("""
                INSERT INTO notifications (user_id, type, title, message, link)
                VALUES (?, 'team_application', 'Application Declined', ?, NULL)
            """, (application['user_id'], message))
            
            flash(f'Application from {application["username"]} has been rejected.', 'info')
        
        conn.commit()
        
    except Exception as e:
        conn.rollback()
        flash(f'Error processing application: {str(e)}', 'danger')
    finally:
        conn.close()
    
    return redirect(url_for('team_recruitment.manage_applications', team_id=application['team_id']))
