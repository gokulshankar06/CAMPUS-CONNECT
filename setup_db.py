import sqlite3
import os

# Remove existing database
if os.path.exists('database.db'):
    os.remove('database.db')
    print("Removed existing database.db")

# Create new database
conn = sqlite3.connect('database.db')
cursor = conn.cursor()

# Users table with all required columns
cursor.execute('''
    CREATE TABLE users (
        id INTEGER PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL CHECK (role IN ('student', 'faculty')),
        is_verified BOOLEAN NOT NULL DEFAULT 0,
        otp TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_login TIMESTAMP,
        profile_picture TEXT,
        full_name TEXT
    )
''')

# Assignments table
cursor.execute('''
    CREATE TABLE assignments (
        id INTEGER PRIMARY KEY,
        title TEXT NOT NULL,
        description TEXT,
        code TEXT UNIQUE NOT NULL,
        faculty_id INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        due_date TIMESTAMP,
        max_marks INTEGER DEFAULT 100,
        instructions TEXT,
        is_active BOOLEAN DEFAULT 1,
        category TEXT DEFAULT 'General',
        FOREIGN KEY (faculty_id) REFERENCES users (id)
    )
''')

# Submissions table
cursor.execute('''
    CREATE TABLE submissions (
        id INTEGER PRIMARY KEY,
        content TEXT NOT NULL,
        student_id INTEGER NOT NULL,
        assignment_id INTEGER NOT NULL,
        submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        file_name TEXT,
        file_size INTEGER,
        file_type TEXT,
        plagiarism_score REAL DEFAULT 0.0,
        grade INTEGER,
        feedback TEXT,
        status TEXT DEFAULT 'submitted' CHECK (status IN ('submitted', 'graded', 'returned')),
        FOREIGN KEY (student_id) REFERENCES users (id),
        FOREIGN KEY (assignment_id) REFERENCES assignments (id),
        UNIQUE(student_id, assignment_id)
    )
''')

# Notifications table
cursor.execute('''
    CREATE TABLE notifications (
        id INTEGER PRIMARY KEY,
        user_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        message TEXT NOT NULL,
        type TEXT DEFAULT 'info' CHECK (type IN ('info', 'success', 'warning', 'error')),
        is_read BOOLEAN DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
''')

# Source docs table
cursor.execute('''
    CREATE TABLE source_docs (
        id INTEGER PRIMARY KEY,
        content TEXT NOT NULL,
        title TEXT,
        author TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
''')

# Create indexes for performance
cursor.execute('CREATE INDEX idx_assignments_faculty ON assignments(faculty_id)')
cursor.execute('CREATE INDEX idx_assignments_due_date ON assignments(due_date)')
cursor.execute('CREATE INDEX idx_submissions_assignment ON submissions(assignment_id)')
cursor.execute('CREATE INDEX idx_submissions_student ON submissions(student_id)')
cursor.execute('CREATE INDEX idx_submissions_status ON submissions(status)')
cursor.execute('CREATE INDEX idx_notifications_user ON notifications(user_id)')
cursor.execute('CREATE INDEX idx_notifications_read ON notifications(is_read)')

conn.commit()

# Verify schema
print("Database created successfully!")
print("\nUsers table columns:")
cursor.execute('PRAGMA table_info(users)')
columns = cursor.fetchall()
for row in columns:
    print(f"  {row[1]} ({row[2]})")

print("\nAssignments table columns:")
cursor.execute('PRAGMA table_info(assignments)')
columns = cursor.fetchall()
for row in columns:
    print(f"  {row[1]} ({row[2]})")

print("\nSubmissions table columns:")
cursor.execute('PRAGMA table_info(submissions)')
columns = cursor.fetchall()
for row in columns:
    print(f"  {row[1]} ({row[2]})")

print("\nNotifications table columns:")
cursor.execute('PRAGMA table_info(notifications)')
columns = cursor.fetchall()
for row in columns:
    print(f"  {row[1]} ({row[2]})")

conn.close()
print("\nDatabase setup complete with all required columns!")
