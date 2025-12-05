from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from datetime import datetime
import csv
import io

from models import get_db_connection

prize_management_bp = Blueprint('prize_management', __name__, url_prefix='/event_manager')

@prize_management_bp.route('/event/<int:event_id>/winners')
@login_required
def view_winners(event_id):
    """View prize winners for an event"""
    if current_user.role not in ['event_manager', 'admin']:
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    conn = get_db_connection()
    
    # Get event details
    event = conn.execute("""
        SELECT * FROM events 
        WHERE id = ? AND (manager_id = ? OR ? = 'admin')
    """, (event_id, current_user.id, current_user.role)).fetchone()
    
    if not event:
        flash('Event not found or access denied.', 'danger')
        conn.close()
        return redirect(url_for('event_manager.events'))
    
    # Get winners
    winners = conn.execute("""
        SELECT w.*, 
               t.name as team_name, 
               u.username, u.full_name, u.email,
               announcer.username as announced_by_name
        FROM event_winners w
        LEFT JOIN teams t ON w.team_id = t.id
        JOIN users u ON w.user_id = u.id
        LEFT JOIN users announcer ON w.announced_by = announcer.id
        WHERE w.event_id = ?
        ORDER BY w.position ASC
    """, (event_id,)).fetchall()
    
    # Get teams that participated (for adding winners)
    teams = conn.execute("""
        SELECT DISTINCT t.id, t.name, t.leader_id,
               GROUP_CONCAT(u.username, ', ') as members
        FROM teams t
        JOIN team_members tm ON t.id = tm.team_id
        JOIN users u ON tm.user_id = u.id
        WHERE t.event_id = ? AND tm.status = 'active'
        GROUP BY t.id
        ORDER BY t.name
    """, (event_id,)).fetchall()
    
    # Get individual participants (for non-team events)
    participants = conn.execute("""
        SELECT u.id, u.username, u.full_name, u.email
        FROM event_registrations er
        JOIN users u ON er.user_id = u.id
        WHERE er.event_id = ? AND er.registration_status = 'approved'
        ORDER BY u.full_name
    """, (event_id,)).fetchall()
    
    conn.close()
    return render_template('event_winners.html', event=event, winners=winners, 
                           teams=teams, participants=participants, user=current_user)

@prize_management_bp.route('/event/<int:event_id>/winners/add', methods=['POST'])
@login_required
def add_winner(event_id):
    """Add a prize winner for an event"""
    if current_user.role != 'event_manager':
        flash('Only event managers can announce winners.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    conn = get_db_connection()
    
    # Verify event ownership
    event = conn.execute("""
        SELECT * FROM events WHERE id = ? AND manager_id = ?
    """, (event_id, current_user.id)).fetchone()
    
    if not event:
        flash('Event not found or access denied.', 'danger')
        conn.close()
        return redirect(url_for('event_manager.events'))
    
    # Get form data
    winner_type = request.form.get('winner_type')  # 'team' or 'individual'
    position = int(request.form.get('position', 1))
    prize_title = request.form.get('prize_title', '').strip()
    prize_amount = request.form.get('prize_amount', '').strip()
    prize_description = request.form.get('prize_description', '').strip()
    certificate_url = request.form.get('certificate_url', '').strip()
    
    if not prize_title:
        flash('Prize title is required.', 'danger')
        conn.close()
        return redirect(url_for('prize_management.view_winners', event_id=event_id))
    
    try:
        if winner_type == 'team':
            team_id = request.form.get('team_id')
            if not team_id:
                flash('Please select a team.', 'danger')
                conn.close()
                return redirect(url_for('prize_management.view_winners', event_id=event_id))
            
            # Get team leader as primary winner
            team = conn.execute("""
                SELECT leader_id FROM teams WHERE id = ?
            """, (team_id,)).fetchone()
            
            if not team:
                flash('Team not found.', 'danger')
                conn.close()
                return redirect(url_for('prize_management.view_winners', event_id=event_id))
            
            user_id = team['leader_id']
            
            # Add winner entry
            conn.execute("""
                INSERT INTO event_winners 
                (event_id, team_id, user_id, position, prize_title, prize_amount, 
                 prize_description, certificate_url, announced_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (event_id, team_id, user_id, position, prize_title, prize_amount,
                  prize_description, certificate_url, current_user.id))
            
            # Notify all team members
            team_members = conn.execute("""
                SELECT user_id FROM team_members 
                WHERE team_id = ? AND status = 'active'
            """, (team_id,)).fetchall()
            
            for member in team_members:
                conn.execute("""
                    INSERT INTO notifications (user_id, type, title, message, link)
                    VALUES (?, 'prize_announcement', 'Congratulations!', ?, ?)
                """, (member['user_id'],
                      f'Your team has won {prize_title} in {event["title"]}!',
                      f'/events/{event_id}/winners'))
        else:
            # Individual winner
            user_id = request.form.get('user_id')
            if not user_id:
                flash('Please select a participant.', 'danger')
                conn.close()
                return redirect(url_for('prize_management.view_winners', event_id=event_id))
            
            conn.execute("""
                INSERT INTO event_winners 
                (event_id, user_id, position, prize_title, prize_amount, 
                 prize_description, certificate_url, announced_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (event_id, user_id, position, prize_title, prize_amount,
                  prize_description, certificate_url, current_user.id))
            
            # Notify winner
            conn.execute("""
                INSERT INTO notifications (user_id, type, title, message, link)
                VALUES (?, 'prize_announcement', 'Congratulations!', ?, ?)
            """, (user_id,
                  f'You have won {prize_title} in {event["title"]}!',
                  f'/events/{event_id}/winners'))
        
        conn.commit()
        flash(f'Winner announced successfully for {prize_title}!', 'success')
        
    except Exception as e:
        conn.rollback()
        flash(f'Error adding winner: {str(e)}', 'danger')
    finally:
        conn.close()
    
    return redirect(url_for('prize_management.view_winners', event_id=event_id))

@prize_management_bp.route('/event/<int:event_id>/winners/remove/<int:winner_id>', methods=['POST'])
@login_required
def remove_winner(event_id, winner_id):
    """Remove a prize winner"""
    if current_user.role != 'event_manager':
        flash('Only event managers can modify winners.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    conn = get_db_connection()
    
    # Verify ownership
    winner = conn.execute("""
        SELECT w.* FROM event_winners w
        JOIN events e ON w.event_id = e.id
        WHERE w.id = ? AND e.id = ? AND e.manager_id = ?
    """, (winner_id, event_id, current_user.id)).fetchone()
    
    if not winner:
        flash('Winner not found or access denied.', 'danger')
        conn.close()
        return redirect(url_for('prize_management.view_winners', event_id=event_id))
    
    try:
        conn.execute("DELETE FROM event_winners WHERE id = ?", (winner_id,))
        conn.commit()
        flash('Winner removed successfully.', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Error removing winner: {str(e)}', 'danger')
    finally:
        conn.close()
    
    return redirect(url_for('prize_management.view_winners', event_id=event_id))

@prize_management_bp.route('/event/<int:event_id>/winners/publish', methods=['POST'])
@login_required
def publish_winners(event_id):
    """Publish winners publicly"""
    if current_user.role != 'event_manager':
        flash('Only event managers can publish winners.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    conn = get_db_connection()
    
    # Verify ownership
    event = conn.execute("""
        SELECT * FROM events WHERE id = ? AND manager_id = ?
    """, (event_id, current_user.id)).fetchone()
    
    if not event:
        flash('Event not found or access denied.', 'danger')
        conn.close()
        return redirect(url_for('event_manager.events'))
    
    try:
        # Update event status to completed if not already
        if event['status'] != 'completed':
            conn.execute("""
                UPDATE events SET status = 'completed' WHERE id = ?
            """, (event_id,))
        
        # Notify all participants about winners announcement
        participants = conn.execute("""
            SELECT DISTINCT user_id FROM event_registrations
            WHERE event_id = ? AND registration_status = 'approved'
        """, (event_id,)).fetchall()
        
        for participant in participants:
            conn.execute("""
                INSERT INTO notifications (user_id, type, title, message, link)
                VALUES (?, 'event_update', 'Winners Announced!', ?, ?)
            """, (participant['user_id'],
                  f'Winners for {event["title"]} have been announced!',
                  f'/events/{event_id}/winners'))
        
        conn.commit()
        flash('Winners published successfully! All participants have been notified.', 'success')
        
    except Exception as e:
        conn.rollback()
        flash(f'Error publishing winners: {str(e)}', 'danger')
    finally:
        conn.close()
    
    return redirect(url_for('prize_management.view_winners', event_id=event_id))

@prize_management_bp.route('/event/<int:event_id>/winners/export')
@login_required
def export_winners(event_id):
    """Export winners list as CSV"""
    if current_user.role not in ['event_manager', 'admin']:
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    conn = get_db_connection()
    
    # Verify access
    event = conn.execute("""
        SELECT title FROM events 
        WHERE id = ? AND (manager_id = ? OR ? = 'admin')
    """, (event_id, current_user.id, current_user.role)).fetchone()
    
    if not event:
        flash('Event not found or access denied.', 'danger')
        conn.close()
        return redirect(url_for('event_manager.events'))
    
    # Get winners data
    winners = conn.execute("""
        SELECT 
            w.position as Position,
            w.prize_title as 'Prize Title',
            w.prize_amount as 'Prize Amount',
            COALESCE(t.name, 'Individual') as 'Team/Individual',
            u.full_name as 'Winner Name',
            u.username as Username,
            u.email as Email,
            u.department as Department,
            w.announced_at as 'Announced Date'
        FROM event_winners w
        LEFT JOIN teams t ON w.team_id = t.id
        JOIN users u ON w.user_id = u.id
        WHERE w.event_id = ?
        ORDER BY w.position ASC
    """, (event_id,)).fetchall()
    
    conn.close()
    
    # Create CSV
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=[
        'Position', 'Prize Title', 'Prize Amount', 'Team/Individual', 
        'Winner Name', 'Username', 'Email', 'Department', 'Announced Date'
    ])
    
    writer.writeheader()
    for winner in winners:
        writer.writerow(dict(winner))
    
    # Return as downloadable file
    from flask import Response
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={
            'Content-Disposition': f'attachment; filename={event["title"]}_winners.csv'
        }
    )
