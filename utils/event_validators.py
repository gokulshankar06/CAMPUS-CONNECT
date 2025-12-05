"""
Event validation utilities for the CampusConnect application.
Handles all business logic validations for event registration and management.
"""
from datetime import datetime
import os
from werkzeug.utils import secure_filename
from models import get_db_connection

class EventValidationError(Exception):
    """Custom exception for event validation errors"""
    pass

def validate_event_registration(user_id, event_id):
    """
    Validate if a user can register for an event
    
    Args:
        user_id (int): ID of the user attempting to register
        event_id (int): ID of the event to register for
        
    Returns:
        tuple: (is_valid, message)
    """
    conn = get_db_connection()
    try:
        # Check if event exists and is open for registration
        event = conn.execute(
            """SELECT e.*, er.* 
               FROM events e 
               LEFT JOIN event_requirements er ON e.id = er.event_id 
               WHERE e.id = ?""", 
            (event_id,)
        ).fetchone()
        
        if not event:
            return False, "Event not found."
            
        # Check if registration deadline has passed
        if event['registration_deadline']:
            reg_deadline = event['registration_deadline']
            try:
                if isinstance(reg_deadline, str):
                    # Stored as text in SQLite (e.g. 'YYYY-MM-DD HH:MM:SS')
                    try:
                        reg_deadline_dt = datetime.strptime(reg_deadline, '%Y-%m-%d %H:%M:%S')
                    except ValueError:
                        reg_deadline_dt = datetime.fromisoformat(reg_deadline.replace('Z', '+00:00'))
                else:
                    reg_deadline_dt = reg_deadline
            except Exception:
                reg_deadline_dt = None

            if reg_deadline_dt and reg_deadline_dt < datetime.now():
                return False, "Registration deadline has passed."
            
        # Check if user is already registered
        existing_reg = conn.execute(
            "SELECT * FROM event_registrations WHERE user_id = ? AND event_id = ?",
            (user_id, event_id)
        ).fetchone()
        
        if existing_reg:
            return False, "You are already registered for this event."
            
        # If team event, check if user is already in a team
        if event['is_team_event']:
            team_member = conn.execute(
                """SELECT t.* FROM teams t 
                   JOIN team_members tm ON t.id = tm.team_id 
                   WHERE t.event_id = ? AND tm.user_id = ? AND tm.status = 'active'""",
                (event_id, user_id)
            ).fetchone()
            
            if team_member:
                return False, f"You are already part of team '{team_member['name']}' for this event."
        
        return True, ""
        
    except Exception as e:
        return False, f"Validation error: {str(e)}"
    finally:
        conn.close()

def validate_team_creation(user_id, event_id, team_data):
    """
    Validate if a team can be created
    
    Args:
        user_id (int): ID of the user creating the team
        event_id (int): ID of the event
        team_data (dict): Team data including name, description, etc.
        
    Returns:
        tuple: (is_valid, message)
    """
    conn = get_db_connection()
    try:
        # Check if event exists and allows teams
        event = conn.execute(
            "SELECT * FROM events WHERE id = ? AND is_team_event = 1",
            (event_id,)
        ).fetchone()
        
        if not event:
            return False, "Event not found or does not allow teams."
            
        # Check if user is already in a team for this event
        existing_team = conn.execute(
            """SELECT t.* FROM teams t 
               JOIN team_members tm ON t.id = tm.team_id 
               WHERE t.event_id = ? AND tm.user_id = ? AND tm.status = 'active'""",
            (event_id, user_id)
        ).fetchone()
        
        if existing_team:
            return False, f"You are already part of team '{existing_team['name']}' for this event."
            
        # Validate team name
        if not team_data.get('name') or len(team_data['name']) < 3:
            return False, "Team name must be at least 3 characters long."
            
        # Validate team size
        max_team_size = team_data.get('max_members', event['max_team_size'])
        if max_team_size > event['max_team_size']:
            return False, f"Maximum team size for this event is {event['max_team_size']}."
            
        return True, ""
        
    except Exception as e:
        return False, f"Validation error: {str(e)}"
    finally:
        conn.close()

def validate_abstract_submission(team_id, file=None, text=None):
    """
    Validate an abstract submission
    
    Args:
        team_id (int): ID of the team submitting the abstract
        file: Uploaded file (if any)
        text (str): Abstract text (if any)
        
    Returns:
        tuple: (is_valid, message, word_count, file_info)
    """
    conn = get_db_connection()
    try:
        # Get team and event requirements
        team = conn.execute(
            """SELECT t.*, er.* 
               FROM teams t 
               LEFT JOIN events e ON t.event_id = e.id 
               LEFT JOIN event_requirements er ON e.id = er.event_id 
               WHERE t.id = ?""",
            (team_id,)
        ).fetchone()
        
        if not team:
            return False, "Team not found.", 0, None
            
        # Determine abstract-related settings from requirements
        requires_abstract = bool(
            'requires_abstract' in team.keys() and team['requires_abstract']
        )
        if not requires_abstract:
            return False, "This event does not require an abstract.", 0, None
            
        # Check if file is provided and valid
        file_info = None
        if file:
            # Validate file type
            allowed_types = (
                team['allowed_file_types']
                if 'allowed_file_types' in team.keys() and team['allowed_file_types']
                else 'pdf,docx,txt'
            )
            allowed_extensions = allowed_types.lower().split(',')
            filename = secure_filename(file.filename)
            file_ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
            
            if file_ext not in allowed_extensions:
                return False, f"Invalid file type. Allowed types: {', '.join(allowed_extensions)}", 0, None
                
            # Validate file size (in MB)
            max_size_mb = (
                team['max_file_size_mb']
                if 'max_file_size_mb' in team.keys() and team['max_file_size_mb'] is not None
                else 5
            )
            file.seek(0, os.SEEK_END)
            file_size_mb = file.tell() / (1024 * 1024)
            file.seek(0)
            
            if file_size_mb > max_size_mb:
                return False, f"File too large. Maximum size: {max_size_mb}MB", 0, None
                
            file_info = {
                'filename': filename,
                'extension': file_ext,
                'size_mb': round(file_size_mb, 2)
            }
        
        # Validate text if provided
        word_count = 0
        if text:
            word_count = len(text.split())
            min_words = (
                team['abstract_min_words']
                if 'abstract_min_words' in team.keys() and team['abstract_min_words'] is not None
                else 150
            )
            max_words = (
                team['abstract_max_words']
                if 'abstract_max_words' in team.keys() and team['abstract_max_words'] is not None
                else 500
            )
            
            if word_count < min_words:
                return False, f"Abstract too short. Minimum {min_words} words required.", word_count, file_info
                
            if word_count > max_words:
                return False, f"Abstract too long. Maximum {max_words} words allowed.", word_count, file_info
        
        return True, "", word_count, file_info
        
    except Exception as e:
        return False, f"Validation error: {str(e)}", 0, None
    finally:
        conn.close()
