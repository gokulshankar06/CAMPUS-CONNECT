from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from models import get_db_connection

# Create main blueprint with explicit name and URL prefix
main_bp = Blueprint(
    name='main',  # Using 'main' as the name for consistency with templates
    import_name=__name__,
    template_folder='../templates',  # Point to the main templates directory
    static_folder='../static',      # Point to the main static directory
    url_prefix=''  # No URL prefix - routes will be at the root
)

# Debug information
print(f"[DEBUG] Initializing main blueprint: name={main_bp.name}, import_name={main_bp.import_name}")
print(f"[DEBUG] Template folder: {main_bp.template_folder}")
print(f"[DEBUG] Static folder: {main_bp.static_folder}")
print(f"[DEBUG] URL prefix: {main_bp.url_prefix}")

@main_bp.route('/about')
def about():
    """About page route"""
    return render_template('about.html', title='About Us')

@main_bp.route('/contact')
def contact():
    """Contact page route"""
    return render_template('contact.html', title='Contact Us')

@main_bp.route('/faq')
def faq():
    """FAQ page route"""
    return render_template('faq.html', title='Frequently Asked Questions')

@main_bp.route('/dashboard')
@login_required
def dashboard():
    conn = get_db_connection()
    
    if current_user.role == 'admin':
        # Admin dashboard - overview of entire platform
        total_users = conn.execute(
            "SELECT COUNT(*) as count FROM users"
        ).fetchone()['count']
        
        total_events = conn.execute(
            "SELECT COUNT(*) as count FROM events"
        ).fetchone()['count']
        
        total_event_managers = conn.execute(
            "SELECT COUNT(*) as count FROM users WHERE role = 'event_manager'"
        ).fetchone()['count']
        
        total_students = conn.execute(
            "SELECT COUNT(*) as count FROM users WHERE role = 'student'"
        ).fetchone()['count']
        
        total_registrations = conn.execute(
            "SELECT COUNT(*) as count FROM event_registrations"
        ).fetchone()['count']
        
        # Get recent events across all managers
        recent_events = conn.execute(
            """SELECT e.*, u.full_name as manager_name
               FROM events e
               JOIN users u ON e.manager_id = u.id
               ORDER BY e.created_at DESC LIMIT 10"""
        ).fetchall()
        
        # Get platform statistics
        active_events = conn.execute(
            "SELECT COUNT(*) as count FROM events WHERE status IN ('upcoming', 'ongoing')"
        ).fetchone()['count']
        
        conn.close()
        return render_template(
            'admin_dashboard.html',
            user=current_user,
            total_users=total_users,
            total_events=total_events,
            total_event_managers=total_event_managers,
            total_students=total_students,
            total_registrations=total_registrations,
            active_events=active_events,
            recent_events=recent_events,
        )
    
    elif current_user.role == 'event_manager':
        # Get event manager statistics
        total_events = conn.execute(
            "SELECT COUNT(*) as count FROM events WHERE manager_id = ?",
            (current_user.id,)
        ).fetchone()['count']
        
        upcoming_events = conn.execute(
            """SELECT COUNT(*) as count 
               FROM events 
               WHERE manager_id = ? AND status = 'upcoming'""",
            (current_user.id,)
        ).fetchone()['count']
        
        total_registrations = conn.execute(
            """SELECT COUNT(*) as count 
               FROM event_registrations er
               JOIN events e ON er.event_id = e.id 
               WHERE e.manager_id = ?""",
            (current_user.id,)
        ).fetchone()['count']
        
        # Get recent events for this manager
        recent_events = conn.execute(
            """SELECT e.*, 
                      (SELECT COUNT(*) FROM event_registrations WHERE event_id = e.id) as registration_count
               FROM events e
               WHERE e.manager_id = ?
               ORDER BY e.created_at DESC LIMIT 5""",
            (current_user.id,)
        ).fetchall()
        
        # Get recent registrations for this manager's events
        recent_registrations = conn.execute(
            """SELECT er.*, e.title as event_title, u.username as user_name
               FROM event_registrations er
               JOIN events e ON er.event_id = e.id
               JOIN users u ON er.user_id = u.id
               WHERE e.manager_id = ?
               ORDER BY er.registered_at DESC LIMIT 5""",
            (current_user.id,)
        ).fetchall()
        
        conn.close()
        return render_template(
            'manager_dashboard.html',
            user=current_user,
            total_events=total_events,
            upcoming_events=upcoming_events,
            total_registrations=total_registrations,
            recent_events=recent_events,
            recent_registrations=recent_registrations
        )
    
    else:  # Student role
        # Get student's registered events
        registered_events = conn.execute(
            """SELECT e.*, u.full_name as manager_name
               FROM events e
               JOIN event_registrations er ON e.id = er.event_id
               JOIN users u ON e.manager_id = u.id
               WHERE er.user_id = ?
               ORDER BY e.start_date""",
            (current_user.id,)
        ).fetchall()
        
        # Get upcoming events (not registered yet)
        upcoming_events = conn.execute(
            """SELECT e.*, u.full_name as manager_name
               FROM events e
               JOIN users u ON e.manager_id = u.id
               WHERE e.status = 'upcoming'
               AND e.id NOT IN (
                   SELECT event_id FROM event_registrations WHERE user_id = ?
               )
               ORDER BY e.start_date""",
            (current_user.id,)
        ).fetchall()
        
        # Get recommended events based on interests (simplified)
        recommended_events = conn.execute(
            """SELECT DISTINCT e.*, u.full_name as manager_name
               FROM events e
               JOIN users u ON e.manager_id = u.id
               WHERE e.status = 'upcoming'
               AND e.id NOT IN (
                   SELECT event_id FROM event_registrations WHERE user_id = ?
               )
               ORDER BY RANDOM()
               LIMIT 3""",
            (current_user.id,)
        ).fetchall()
        
        conn.close()
        return render_template(
            'student_dashboard_standalone.html',
            user=current_user,
            registered_events=registered_events,
            upcoming_events=upcoming_events,
            recommended_events=recommended_events
        )
