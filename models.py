from flask_login import UserMixin
import sqlite3

def get_db_connection():
    """Get database connection with proper error handling"""
    try:
        conn = sqlite3.connect('database.db')
        conn.row_factory = sqlite3.Row
        # Enable foreign key constraints
        conn.execute("PRAGMA foreign_keys = ON")
        return conn
    except sqlite3.Error as e:
        print(f"Database connection error: {e}")
        raise

class User(UserMixin):
    ...
    def __init__(self, id, username, email, password, role, is_verified, otp, last_login=None, profile_picture=None, full_name=None):
        self.id = id
        self.username = username
        self.email = email
        self.password = password
        self.role = role
        self.is_verified = is_verified
        self.otp = otp
        self.last_login = last_login
        self.profile_picture = profile_picture
        self.full_name = full_name

    def is_active(self):
        """Return True if the user account is active."""
        return self.is_verified

    def get_id(self):
        """Return the user id as a string."""
        return str(self.id)

    @property
    def is_authenticated(self):
        """Return True if the user is authenticated."""
        return True

    @property
    def is_anonymous(self):
        """Return False for regular users."""
        return False

    @staticmethod
    def get(user_id):
        conn = get_db_connection()
        user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        conn.close()
        if not user:
            return None
        return User(
            id=user['id'],
            username=user['username'],
            email=user['email'],
            password=user['password'],
            role=user['role'],
            is_verified=user['is_verified'],
            otp=user['otp'],
            last_login=user['last_login'] if 'last_login' in user.keys() else None,
            profile_picture=user['profile_picture'] if 'profile_picture' in user.keys() else None,
            full_name=user['full_name'] if 'full_name' in user.keys() else None
        )

    @staticmethod
    def get_by_username(username):
        conn = get_db_connection()
        user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        conn.close()
        if not user:
            return None
        return User(
            id=user['id'],
            username=user['username'],
            email=user['email'],
            password=user['password'],
            role=user['role'],
            is_verified=user['is_verified'],
            otp=user['otp'],
            last_login=user['last_login'] if 'last_login' in user.keys() else None,
            profile_picture=user['profile_picture'] if 'profile_picture' in user.keys() else None,
            full_name=user['full_name'] if 'full_name' in user.keys() else None
        )

class Event:
    def __init__(self, id, title, description, event_type, event_code, manager_id, start_date, end_date, 
                 registration_deadline, venue=None, max_participants=None, max_team_size=5, min_team_size=1,
                 is_team_event=True, status='upcoming', banner_image=None, resources_link=None, prize_pool=None,
                 created_at=None, updated_at=None):
        self.id = id
        self.title = title
        self.description = description
        self.event_type = event_type
        self.event_code = event_code
        self.manager_id = manager_id
        self.start_date = start_date
        self.end_date = end_date
        self.registration_deadline = registration_deadline
        self.venue = venue
        self.max_participants = max_participants
        self.max_team_size = max_team_size
        self.min_team_size = min_team_size
        self.is_team_event = is_team_event
        self.status = status
        self.banner_image = banner_image
        self.resources_link = resources_link
        self.prize_pool = prize_pool
        self.created_at = created_at
        self.updated_at = updated_at

    @staticmethod
    def get_by_code(event_code):
        conn = get_db_connection()
        event = conn.execute("SELECT * FROM events WHERE event_code = ?", (event_code,)).fetchone()
        conn.close()
        if not event:
            return None
        return Event(
            id=event['id'],
            title=event['title'],
            description=event['description'],
            event_type=event['event_type'],
            event_code=event['event_code'],
            manager_id=event['manager_id'],
            start_date=event['start_date'],
            end_date=event['end_date'],
            registration_deadline=event['registration_deadline'],
            venue=event['venue'] if 'venue' in event.keys() else None,
            max_participants=event['max_participants'] if 'max_participants' in event.keys() else None,
            max_team_size=event['max_team_size'] if 'max_team_size' in event.keys() else 5,
            min_team_size=event['min_team_size'] if 'min_team_size' in event.keys() else 1,
            is_team_event=event['is_team_event'] if 'is_team_event' in event.keys() else True,
            status=event['status'] if 'status' in event.keys() else 'upcoming',
            banner_image=event['banner_image'] if 'banner_image' in event.keys() else None,
            resources_link=event['resources_link'] if 'resources_link' in event.keys() else None,
            prize_pool=event['prize_pool'] if 'prize_pool' in event.keys() else None,
            created_at=event['created_at'] if 'created_at' in event.keys() else None,
            updated_at=event['updated_at'] if 'updated_at' in event.keys() else None
        )

class EventRegistration:
    def __init__(self, id, event_id, user_id, team_id=None, registration_status='pending', 
                 registered_at=None, approved_at=None, notes=None):
        self.id = id
        self.event_id = event_id
        self.user_id = user_id
        self.team_id = team_id
        self.registration_status = registration_status
        self.registered_at = registered_at
        self.approved_at = approved_at
        self.notes = notes

class Team:
    def __init__(self, id, name, description, event_id, leader_id, status='forming', 
                 max_members=5, is_open=True, team_code=None, created_at=None, updated_at=None,
                 has_submitted_abstract=False, abstract_status='not_required', invitation_code=None, is_public=False):
        self.id = id
        self.name = name
        self.description = description
        self.event_id = event_id
        self.leader_id = leader_id
        self.status = status
        self.max_members = max_members
        self.is_open = is_open
        self.team_code = team_code
        self.created_at = created_at
        self.updated_at = updated_at
        self.has_submitted_abstract = has_submitted_abstract
        self.abstract_status = abstract_status
        self.invitation_code = invitation_code
        self.is_public = is_public

class AbstractSubmission:
    def __init__(self, id, event_id, team_id, user_id, title, abstract_text, file_path=None, 
                 file_name=None, file_size=None, word_count=0, status='draft', plagiarism_score=0.0,
                 plagiarism_status='pending', submitted_at=None, reviewed_by=None, reviewed_at=None,
                 feedback=None, revision_notes=None, version=1, is_latest_version=True,
                 created_at=None, updated_at=None):
        self.id = id
        self.event_id = event_id
        self.team_id = team_id
        self.user_id = user_id
        self.title = title
        self.abstract_text = abstract_text
        self.file_path = file_path
        self.file_name = file_name
        self.file_size = file_size
        self.word_count = word_count
        self.status = status
        self.plagiarism_score = plagiarism_score
        self.plagiarism_status = plagiarism_status
        self.submitted_at = submitted_at
        self.reviewed_by = reviewed_by
        self.reviewed_at = reviewed_at
        self.feedback = feedback
        self.revision_notes = revision_notes
        self.version = version
        self.is_latest_version = is_latest_version
        self.created_at = created_at
        self.updated_at = updated_at

class TeamInvitation:
    def __init__(self, id, team_id, inviter_id, invitee_email, invitee_id=None, 
                 invitation_token=None, message=None, status='pending', created_at=None,
                 expires_at=None, responded_at=None):
        self.id = id
        self.team_id = team_id
        self.inviter_id = inviter_id
        self.invitee_email = invitee_email
        self.invitee_id = invitee_id
        self.invitation_token = invitation_token
        self.message = message
        self.status = status
        self.created_at = created_at
        self.expires_at = expires_at
        self.responded_at = responded_at

class EventRequirement:
    def __init__(self, id, event_id, requires_abstract=False, abstract_min_words=150,
                 abstract_max_words=500, abstract_deadline=None, allowed_file_types='pdf,docx,txt',
                 max_file_size_mb=5, plagiarism_threshold=0.25, auto_approve_threshold=0.10,
                 created_at=None, updated_at=None):
        self.id = id
        self.event_id = event_id
        self.requires_abstract = requires_abstract
        self.abstract_min_words = abstract_min_words
        self.abstract_max_words = abstract_max_words
        self.abstract_deadline = abstract_deadline
        self.allowed_file_types = allowed_file_types
        self.max_file_size_mb = max_file_size_mb
        self.plagiarism_threshold = plagiarism_threshold
        self.auto_approve_threshold = auto_approve_threshold
        self.created_at = created_at
        self.updated_at = updated_at      