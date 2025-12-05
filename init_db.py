#!/usr/bin/env python3
"""
Initialize CampusConnect+ Database
Event Management and Team Collaboration Platform
"""

import sqlite3
import os
import sys
from werkzeug.security import generate_password_hash

def init_database():
    """Initialize the CampusConnect+ database with all required tables"""
    
    # Remove existing database if it exists
    if os.path.exists('database.db'):
        print("Existing database found. Backing up...")
        if os.path.exists('database_backup.db'):
            os.remove('database_backup.db')
        os.rename('database.db', 'database_backup.db')
    
    # Create new database
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Enable foreign keys
    cursor.execute("PRAGMA foreign_keys = ON")
    
    print("Creating CampusConnect+ tables...")
    
    # Users table (Students and Event Managers)
    cursor.execute('''
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            email TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            full_name TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('student', 'event_manager', 'admin')),
            is_verified BOOLEAN DEFAULT 0,
            otp TEXT,
            profile_picture TEXT,
            bio TEXT,
            department TEXT,
            year INTEGER,
            last_login TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Skills table
    cursor.execute('''
        CREATE TABLE skills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            category TEXT NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # User skills junction table
    cursor.execute('''
        CREATE TABLE user_skills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            skill_id INTEGER NOT NULL,
            proficiency_level TEXT DEFAULT 'beginner' CHECK(proficiency_level IN ('beginner', 'intermediate', 'advanced', 'expert')),
            endorsed_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (skill_id) REFERENCES skills(id) ON DELETE CASCADE,
            UNIQUE(user_id, skill_id)
        )
    ''')
    
    # Events table (replacing assignments)
    cursor.execute('''
        CREATE TABLE events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            event_type TEXT NOT NULL CHECK(event_type IN (
                'hackathon', 'competition', 'workshop', 'seminar', 'project',
                'research', 'conference', 'symposium', 'meetup', 'training', 'other'
            )),
            event_code TEXT UNIQUE NOT NULL,
            manager_id INTEGER NOT NULL,
            start_date TIMESTAMP NOT NULL,
            end_date TIMESTAMP NOT NULL,
            registration_deadline TIMESTAMP NOT NULL,
            venue TEXT,
            max_participants INTEGER,
            max_team_size INTEGER DEFAULT 5,
            min_team_size INTEGER DEFAULT 1,
            is_team_event BOOLEAN DEFAULT 1,
            status TEXT DEFAULT 'upcoming' CHECK(status IN ('draft', 'upcoming', 'ongoing', 'completed', 'cancelled')),
            banner_image TEXT,
            resources_link TEXT,
            prize_pool TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (manager_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')
    
    # Event registrations
    cursor.execute('''
        CREATE TABLE event_registrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            team_id INTEGER,
            registration_status TEXT DEFAULT 'pending' CHECK(registration_status IN ('pending', 'approved', 'rejected', 'waitlist')),
            registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            approved_at TIMESTAMP,
            notes TEXT,
            FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE SET NULL,
            UNIQUE(event_id, user_id)
        )
    ''')

    # Event requirements (per-event abstract configuration)
    cursor.execute('''
        CREATE TABLE event_requirements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL UNIQUE,
            requires_abstract BOOLEAN DEFAULT 0,
            abstract_min_words INTEGER,
            abstract_max_words INTEGER,
            abstract_deadline TIMESTAMP,
            allowed_file_types TEXT,
            max_file_size_mb REAL,
            plagiarism_threshold REAL,
            auto_approve_threshold REAL,
            auto_approve_timeout_hours INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE
        )
    ''')

    # Abstract submissions (latest version per submission stored in this table)
    cursor.execute('''
        CREATE TABLE abstract_submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            team_id INTEGER,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            abstract_text TEXT NOT NULL,
            file_path TEXT,
            file_name TEXT,
            file_size INTEGER,
            word_count INTEGER DEFAULT 0,
            status TEXT DEFAULT 'draft',
            plagiarism_score REAL,
            plagiarism_status TEXT DEFAULT 'pending',
            submitted_at TIMESTAMP,
            reviewed_by INTEGER,
            reviewed_at TIMESTAMP,
            feedback TEXT,
            revision_notes TEXT,
            version INTEGER DEFAULT 1,
            is_latest_version BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE,
            FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE SET NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (reviewed_by) REFERENCES users(id) ON DELETE SET NULL
        )
    ''')

    # Abstract submission history (all versions)
    cursor.execute('''
        CREATE TABLE abstract_submission_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            submission_id INTEGER NOT NULL,
            version INTEGER NOT NULL,
            title TEXT NOT NULL,
            abstract_text TEXT NOT NULL,
            file_path TEXT,
            word_count INTEGER,
            changes_summary TEXT,
            created_by INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (submission_id) REFERENCES abstract_submissions(id) ON DELETE CASCADE,
            FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE CASCADE,
            UNIQUE(submission_id, version)
        )
    ''')

    # Teams table
    cursor.execute('''
        CREATE TABLE teams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            event_id INTEGER NOT NULL,
            leader_id INTEGER NOT NULL,
            status TEXT DEFAULT 'forming' CHECK(status IN ('forming', 'active', 'inactive', 'completed')),
            max_members INTEGER DEFAULT 5,
            is_open BOOLEAN DEFAULT 1,
            is_public BOOLEAN DEFAULT 0,
            team_code TEXT UNIQUE,
            invitation_code TEXT,
            has_submitted_abstract BOOLEAN DEFAULT 0,
            abstract_status TEXT DEFAULT 'not_required',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE,
            FOREIGN KEY (leader_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')
    
    # Team members
    cursor.execute('''
        CREATE TABLE team_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            role TEXT DEFAULT 'member',
            status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'active', 'inactive', 'removed')),
            contribution_score INTEGER DEFAULT 0,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            left_at TIMESTAMP,
            FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            UNIQUE(team_id, user_id)
        )
    ''')
    
    # Team requests (for skill-based matching)
    cursor.execute('''
        CREATE TABLE team_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            required_skills TEXT,
            status TEXT DEFAULT 'open' CHECK(status IN ('open', 'closed', 'fulfilled')),
            created_by INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE,
            FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')
    
    # Team applications
    cursor.execute('''
        CREATE TABLE team_applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            message TEXT,
            status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'approved', 'rejected')),
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            reviewed_at TIMESTAMP,
            reviewed_by INTEGER,
            FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (reviewed_by) REFERENCES users(id) ON DELETE SET NULL,
            UNIQUE(team_id, user_id)
        )
    ''')
    
    # Team tasks
    cursor.execute('''
        CREATE TABLE team_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            assigned_to INTEGER,
            priority TEXT DEFAULT 'medium' CHECK(priority IN ('low', 'medium', 'high', 'critical')),
            status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'in_progress', 'review', 'completed', 'cancelled')),
            due_date TIMESTAMP,
            created_by INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE,
            FOREIGN KEY (assigned_to) REFERENCES users(id) ON DELETE SET NULL,
            FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')
    
    # Team files
    cursor.execute('''
        CREATE TABLE team_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER NOT NULL,
            file_name TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_size INTEGER,
            file_type TEXT,
            description TEXT,
            uploaded_by INTEGER NOT NULL,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE,
            FOREIGN KEY (uploaded_by) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')

    # Team activity logs
    cursor.execute('''
        CREATE TABLE team_activity_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            activity_type TEXT NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')

    # Team messages
    cursor.execute('''
        CREATE TABLE team_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER NOT NULL,
            sender_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            is_announcement BOOLEAN DEFAULT 0,
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            edited_at TIMESTAMP,
            FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE,
            FOREIGN KEY (sender_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')

    # Team vacancies (for recruitment)
    cursor.execute('''
        CREATE TABLE team_vacancies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            role TEXT NOT NULL,
            required_skills TEXT,
            preferred_skills TEXT,
            slots_available INTEGER NOT NULL DEFAULT 1,
            slots_filled INTEGER NOT NULL DEFAULT 0,
            status TEXT DEFAULT 'open' CHECK(status IN ('open', 'filled', 'closed')),
            created_by INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE,
            FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')

    # Team join requests
    cursor.execute('''
        CREATE TABLE team_join_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER NOT NULL,
            vacancy_id INTEGER,
            user_id INTEGER NOT NULL,
            message TEXT,
            skills_match TEXT,
            status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'approved', 'rejected')),
            requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            reviewed_at TIMESTAMP,
            reviewed_by INTEGER,
            rejection_reason TEXT,
            FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE,
            FOREIGN KEY (vacancy_id) REFERENCES team_vacancies(id) ON DELETE SET NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (reviewed_by) REFERENCES users(id) ON DELETE SET NULL
        )
    ''')

    # Team invitations
    cursor.execute('''
        CREATE TABLE team_invitations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER NOT NULL,
            inviter_id INTEGER NOT NULL,
            invitee_email TEXT NOT NULL,
            invitee_id INTEGER,
            invitation_token TEXT NOT NULL UNIQUE,
            message TEXT,
            status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'accepted', 'declined', 'expired')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP,
            responded_at TIMESTAMP,
            FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE,
            FOREIGN KEY (inviter_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (invitee_id) REFERENCES users(id) ON DELETE SET NULL
        )
    ''')
    
    # Direct messages
    cursor.execute('''
        CREATE TABLE direct_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER NOT NULL,
            receiver_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            is_read BOOLEAN DEFAULT 0,
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            read_at TIMESTAMP,
            FOREIGN KEY (sender_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (receiver_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')
    
    # Notifications
    cursor.execute('''
        CREATE TABLE notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            type TEXT NOT NULL,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            link TEXT,
            is_read BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            read_at TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')
    
    # Event milestones
    cursor.execute('''
        CREATE TABLE event_milestones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            due_date TIMESTAMP NOT NULL,
            points INTEGER DEFAULT 0,
            status TEXT DEFAULT 'upcoming' CHECK(status IN ('upcoming', 'ongoing', 'completed', 'missed')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE
        )
    ''')
    
    # Team milestones
    cursor.execute('''
        CREATE TABLE team_milestones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER NOT NULL,
            milestone_id INTEGER NOT NULL,
            status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'in_progress', 'submitted', 'approved', 'rejected')),
            submission_link TEXT,
            feedback TEXT,
            points_earned INTEGER DEFAULT 0,
            submitted_at TIMESTAMP,
            reviewed_at TIMESTAMP,
            reviewed_by INTEGER,
            FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE,
            FOREIGN KEY (milestone_id) REFERENCES event_milestones(id) ON DELETE CASCADE,
            FOREIGN KEY (reviewed_by) REFERENCES users(id) ON DELETE SET NULL,
            UNIQUE(team_id, milestone_id)
        )
    ''')
    
    # Analytics tracking
    cursor.execute('''
        CREATE TABLE user_analytics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            events_participated INTEGER DEFAULT 0,
            events_won INTEGER DEFAULT 0,
            teams_joined INTEGER DEFAULT 0,
            teams_led INTEGER DEFAULT 0,
            tasks_completed INTEGER DEFAULT 0,
            skill_endorsements INTEGER DEFAULT 0,
            collaboration_score REAL DEFAULT 0.0,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            UNIQUE(user_id)
        )
    ''')
    
    # Insert default skills
    default_skills = [
        # Programming
        ('Python', 'Programming', 'General-purpose programming language'),
        ('JavaScript', 'Programming', 'Web programming language'),
        ('Java', 'Programming', 'Object-oriented programming language'),
        ('C++', 'Programming', 'System programming language'),
        ('React', 'Programming', 'JavaScript library for building user interfaces'),
        ('Node.js', 'Programming', 'JavaScript runtime environment'),
        ('Flutter', 'Programming', 'UI toolkit for mobile applications'),
        
        # Design
        ('UI/UX Design', 'Design', 'User interface and experience design'),
        ('Graphic Design', 'Design', 'Visual communication design'),
        ('Figma', 'Design', 'Collaborative design tool'),
        ('Adobe Photoshop', 'Design', 'Image editing software'),
        ('Adobe Illustrator', 'Design', 'Vector graphics editor'),
        
        # Data & AI
        ('Machine Learning', 'Data Science', 'Building predictive models'),
        ('Data Analysis', 'Data Science', 'Analyzing and interpreting data'),
        ('Deep Learning', 'Data Science', 'Neural network architectures'),
        ('TensorFlow', 'Data Science', 'Machine learning framework'),
        ('PyTorch', 'Data Science', 'Deep learning framework'),
        
        # Web Development
        ('HTML/CSS', 'Web Development', 'Web markup and styling'),
        ('Backend Development', 'Web Development', 'Server-side programming'),
        ('Frontend Development', 'Web Development', 'Client-side programming'),
        ('Database Management', 'Web Development', 'Managing data storage'),
        ('REST APIs', 'Web Development', 'API design and development'),
        
        # Soft Skills
        ('Leadership', 'Soft Skills', 'Team leadership and management'),
        ('Communication', 'Soft Skills', 'Effective communication'),
        ('Problem Solving', 'Soft Skills', 'Analytical thinking'),
        ('Time Management', 'Soft Skills', 'Efficient time utilization'),
        ('Teamwork', 'Soft Skills', 'Collaborative working'),
        
        # Other
        ('Cloud Computing', 'Technology', 'Cloud platforms and services'),
        ('Cybersecurity', 'Technology', 'Information security'),
        ('Blockchain', 'Technology', 'Distributed ledger technology'),
        ('IoT', 'Technology', 'Internet of Things'),
        ('DevOps', 'Technology', 'Development and operations practices')
    ]
    
    for skill_name, category, description in default_skills:
        cursor.execute(
            "INSERT INTO skills (name, category, description) VALUES (?, ?, ?)",
            (skill_name, category, description)
        )
    
    # Create sample users
    print("Creating sample users...")
    
    # Admin user
    cursor.execute(
        "INSERT INTO users (username, email, password, full_name, role, is_verified) VALUES (?, ?, ?, ?, ?, ?)",
        ('admin', 'admin@campusconnect.com', generate_password_hash('admin123'), 'System Administrator', 'admin', 1)
    )
    
    # Sample event managers
    cursor.execute(
        "INSERT INTO users (username, email, password, full_name, role, is_verified, department) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ('manager1', 'manager1@campus.edu', generate_password_hash('manager123'), 'Dr. Sarah Johnson', 'event_manager', 1, 'Computer Science')
    )
    
    cursor.execute(
        "INSERT INTO users (username, email, password, full_name, role, is_verified, department) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ('manager2', 'manager2@campus.edu', generate_password_hash('manager123'), 'Prof. Michael Chen', 'event_manager', 1, 'Engineering')
    )
    
    # Sample students
    students = [
        ('john_doe', 'john@student.edu', 'John Doe', 'Computer Science', 3),
        ('jane_smith', 'jane@student.edu', 'Jane Smith', 'Data Science', 2),
        ('alex_wilson', 'alex@student.edu', 'Alex Wilson', 'Software Engineering', 4),
        ('emily_brown', 'emily@student.edu', 'Emily Brown', 'AI/ML', 3),
        ('mike_jones', 'mike@student.edu', 'Mike Jones', 'Web Development', 2)
    ]
    
    for username, email, full_name, dept, year in students:
        cursor.execute(
            "INSERT INTO users (username, email, password, full_name, role, is_verified, department, year) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (username, email, generate_password_hash('student123'), full_name, 'student', 1, dept, year)
        )
    
    # Create sample events
    print("Creating sample events (demonstrating various event types)...")
    
    events = [
        ('CodeFest 2024', 'Annual coding competition with exciting challenges', 'hackathon', 'CF2024', 2, 
         '2024-03-15 09:00:00', '2024-03-17 18:00:00', '2024-03-10 23:59:59', 'Main Auditorium', 200, 4, 'ongoing'),
        ('AI/ML Workshop', 'Hands-on workshop on machine learning basics', 'workshop', 'AIML001', 3,
         '2024-03-20 14:00:00', '2024-03-20 17:00:00', '2024-03-18 23:59:59', 'Lab 301', 50, 1, 'upcoming'),
        ('Web Dev Bootcamp', 'Intensive web development training', 'workshop', 'WEB2024', 2,
         '2024-04-01 10:00:00', '2024-04-05 16:00:00', '2024-03-25 23:59:59', 'Tech Hub', 100, 3, 'upcoming'),
        ('Innovation Challenge', 'Build innovative solutions for real-world problems', 'competition', 'INNO24', 3,
         '2024-04-10 00:00:00', '2024-04-30 23:59:59', '2024-04-05 23:59:59', 'Online', 500, 5, 'upcoming'),
        ('Research Symposium', 'Present your research findings', 'research', 'RESEARCH2024', 2,
         '2024-04-15 09:00:00', '2024-04-15 17:00:00', '2024-04-10 23:59:59', 'Conference Hall', 150, 1, 'upcoming'),
        ('Tech Conference', 'Latest trends in technology', 'conference', 'TECHCONF24', 3,
         '2024-05-01 09:00:00', '2024-05-02 18:00:00', '2024-04-25 23:59:59', 'Convention Center', 300, 1, 'upcoming'),
        ('Project Showcase', 'Showcase your semester projects', 'project', 'PROJ2024', 2,
         '2024-05-15 10:00:00', '2024-05-15 16:00:00', '2024-05-10 23:59:59', 'Exhibition Hall', 100, 4, 'upcoming')
    ]
    
    for title, desc, event_type, code, manager_id, start, end, reg_deadline, venue, max_p, max_t, status in events:
        cursor.execute(
            '''INSERT INTO events (title, description, event_type, event_code, manager_id, start_date, end_date, 
               registration_deadline, venue, max_participants, max_team_size, min_team_size, is_team_event, status) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (title, desc, event_type, code, manager_id, start, end, reg_deadline, venue, max_p, max_t, 1, 1, status)
        )
        print(f"  + {title} ({event_type})")
    
    # Add event requirements for all events with smart defaults
    print("\nConfiguring abstract requirements for all event types...")
    
    # Get all events we just created
    all_events = cursor.execute("SELECT id, title, event_type, registration_deadline FROM events").fetchall()
    
    # Define which event types typically need abstracts (configurable by event managers)
    # Updated to allow abstracts for ALL event types - managers can enable/disable per event
    event_types_with_default_abstracts = {
        'hackathon': True,        # Hackathons typically require project abstracts
        'competition': True,      # Competitions often need submission abstracts  
        'research': True,         # Research events need paper abstracts
        'conference': True,       # Conferences require presentation abstracts
        'symposium': True,        # Symposiums need topic abstracts
        'project': True,          # Project showcases need descriptions
        'workshop': True,         # Workshops can require topic abstracts
        'seminar': True,          # Seminars can require presentation abstracts
        'meetup': False,          # Meetups usually casual
        'training': False,        # Training sessions usually don't need abstracts
        'other': False           # Generic events default to no abstracts
    }
    
    for event in all_events:
        event_id = event[0]
        title = event[1]
        event_type = event[2]
        reg_deadline = event[3]
        
        # Determine if this event type typically needs abstracts by default
        # Event managers can always override this setting
        needs_abstract = event_types_with_default_abstracts.get(event_type.lower(), False)
        
        # Calculate abstract deadline (1 day before registration deadline)
        try:
            from datetime import datetime, timedelta
            reg_deadline_dt = datetime.strptime(reg_deadline, '%Y-%m-%d %H:%M:%S')
            abstract_deadline = reg_deadline_dt - timedelta(days=1)
            abstract_deadline_str = abstract_deadline.strftime('%Y-%m-%d %H:%M:%S')
        except:
            # If parsing fails, set abstract deadline to registration deadline
            abstract_deadline_str = reg_deadline
        
        # Insert event requirements with smart defaults based on event type
        word_limits = {
            'hackathon': (200, 600),      # Hackathons need detailed project descriptions
            'competition': (150, 500),    # Standard competition abstracts
            'research': (250, 800),       # Research papers need more detail
            'conference': (200, 600),     # Conference presentations
            'symposium': (200, 600),      # Symposium topics
            'project': (150, 500),        # Project showcases
            'workshop': (100, 400),       # Workshop topics (shorter)
            'seminar': (150, 500),        # Seminar presentations
            'other': (150, 500)           # Default for other types
        }
        
        min_words, max_words = word_limits.get(event_type.lower(), (150, 500))
        
        # Set plagiarism threshold based on event type
        plagiarism_thresholds = {
            'research': 15.0,     # Stricter for research
            'conference': 20.0,   # Moderate for conferences
            'hackathon': 30.0,    # More lenient for hackathons (similar ideas common)
            'competition': 25.0,  # Standard for competitions
            'project': 25.0,      # Standard for projects
            'workshop': 35.0,     # More lenient for workshops
            'seminar': 25.0,      # Standard for seminars
            'other': 25.0         # Default
        }
        
        plagiarism_threshold = plagiarism_thresholds.get(event_type.lower(), 25.0)
        
        # Insert event requirements
        cursor.execute(
            """INSERT INTO event_requirements (
                event_id, requires_abstract, abstract_min_words, abstract_max_words,
                abstract_deadline, allowed_file_types, max_file_size_mb,
                plagiarism_threshold, auto_approve_threshold, auto_approve_timeout_hours
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                event_id,  # event_id
                needs_abstract,  # requires_abstract
                min_words,     # abstract_min_words (smart defaults)
                max_words,     # abstract_max_words (smart defaults)
                abstract_deadline_str if needs_abstract else None,  # abstract_deadline
                'pdf,docx,txt',  # allowed_file_types
                5.0,           # max_file_size_mb
                plagiarism_threshold,  # plagiarism_threshold (event-specific)
                10.0,          # auto_approve_threshold (10%)
                72             # auto_approve_timeout_hours
            )
        )
        
        if needs_abstract:
            print(f"  - {title} ({event_type}): Abstract enabled by default")
        else:
            print(f"  - {title} ({event_type}): Abstract disabled by default (can be enabled by manager)")
    
    # Commit all changes
    conn.commit()
    print("Database initialized successfully!")
    # Get summary statistics
    cursor.execute("SELECT COUNT(*) FROM event_requirements WHERE requires_abstract = 1")
    events_with_abstracts = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM event_requirements")
    total_events = cursor.fetchone()[0]
    
    cursor.execute("SELECT event_type, COUNT(*) as count FROM events GROUP BY event_type")
    event_type_counts = cursor.fetchall()
    
    print("Default users created:")
    print("  - Admin: admin/admin123")
    print("  - Event Managers: manager1/manager123, manager2/manager123")
    print("  - Students: john_doe/student123, jane_smith/student123, etc.")
    
    print(f"\nDatabase Initialization Summary:")
    print(f"- Total events created: {total_events}")
    print(f"- Events with abstracts enabled: {events_with_abstracts}")
    print(f"- Events with abstracts disabled: {total_events - events_with_abstracts}")
    print("\nEvent Types Distribution:")
    for event_type, count in event_type_counts:
        print(f"  - {event_type}: {count} event(s)")
    print("\nAbstract System Features:")
    print("- Smart word limits based on event type")
    print("- Event-specific plagiarism thresholds")
    print("- Auto-approval system (72 hours default)")
    print("- File upload support (PDF, DOCX, TXT)")
    print("- Version control and draft saving")
    print("- Comprehensive plagiarism detection")
    print("\nAbstract Submission System:")
    print("  - Event managers can enable/disable abstracts for ANY event type")
    print("  - Default abstract requirements set based on event type")
    print("  - Configurable word limits, deadlines, and plagiarism thresholds")
    print("  - Auto-approval system with timeout (72 hours default)")
    
    conn.close()

if __name__ == "__main__":
    try:
        init_database()
    except Exception as e:
        print(f"Error initializing database: {e}")
        sys.exit(1)
