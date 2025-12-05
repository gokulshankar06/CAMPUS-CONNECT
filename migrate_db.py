import sqlite3
from datetime import datetime

def get_column_names(cursor, table_name):
    """Get existing column names for a table"""
    cursor.execute(f"PRAGMA table_info({table_name})")
    return [column[1] for column in cursor.fetchall()]

def column_exists(cursor, table_name, column_name):
    """Check if a column exists in a table"""
    columns = get_column_names(cursor, table_name)
    return column_name in columns

def migrate_database():
    """Migrate existing database to new schema"""
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    
    print("Starting database migration...")
    
    try:
        # Check and add new columns to users table
        if not column_exists(cursor, 'users', 'created_at'):
            cursor.execute('ALTER TABLE users ADD COLUMN created_at TIMESTAMP')
            cursor.execute('UPDATE users SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL')
            print("Added created_at to users table")
            
        if not column_exists(cursor, 'users', 'last_login'):
            cursor.execute('ALTER TABLE users ADD COLUMN last_login TIMESTAMP')
            print("Added last_login to users table")
            
        if not column_exists(cursor, 'users', 'profile_picture'):
            cursor.execute('ALTER TABLE users ADD COLUMN profile_picture TEXT')
            print("Added profile_picture to users table")
            
        if not column_exists(cursor, 'users', 'full_name'):
            cursor.execute('ALTER TABLE users ADD COLUMN full_name TEXT')
            print("Added full_name to users table")
        
        # Check and add new columns to assignments table
        if not column_exists(cursor, 'assignments', 'created_at'):
            cursor.execute('ALTER TABLE assignments ADD COLUMN created_at TIMESTAMP')
            cursor.execute('UPDATE assignments SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL')
            print("Added created_at to assignments table")
            
        if not column_exists(cursor, 'assignments', 'due_date'):
            cursor.execute('ALTER TABLE assignments ADD COLUMN due_date TIMESTAMP')
            print("Added due_date to assignments table")
            
        if not column_exists(cursor, 'assignments', 'max_marks'):
            cursor.execute('ALTER TABLE assignments ADD COLUMN max_marks INTEGER DEFAULT 100')
            print("Added max_marks to assignments table")
            
        if not column_exists(cursor, 'assignments', 'instructions'):
            cursor.execute('ALTER TABLE assignments ADD COLUMN instructions TEXT')
            print("Added instructions to assignments table")
            
        if not column_exists(cursor, 'assignments', 'is_active'):
            cursor.execute('ALTER TABLE assignments ADD COLUMN is_active BOOLEAN DEFAULT 1')
            print("Added is_active to assignments table")
            
        if not column_exists(cursor, 'assignments', 'category'):
            cursor.execute('ALTER TABLE assignments ADD COLUMN category TEXT DEFAULT "General"')
            print("Added category to assignments table")
        
        # Check and add new columns to submissions table
        if not column_exists(cursor, 'submissions', 'submitted_at'):
            cursor.execute('ALTER TABLE submissions ADD COLUMN submitted_at TIMESTAMP')
            cursor.execute('UPDATE submissions SET submitted_at = CURRENT_TIMESTAMP WHERE submitted_at IS NULL')
            print("Added submitted_at to submissions table")
            
        if not column_exists(cursor, 'submissions', 'file_name'):
            cursor.execute('ALTER TABLE submissions ADD COLUMN file_name TEXT')
            print("Added file_name to submissions table")
            
        if not column_exists(cursor, 'submissions', 'file_size'):
            cursor.execute('ALTER TABLE submissions ADD COLUMN file_size INTEGER')
            print("Added file_size to submissions table")
            
        if not column_exists(cursor, 'submissions', 'file_type'):
            cursor.execute('ALTER TABLE submissions ADD COLUMN file_type TEXT')
            print("Added file_type to submissions table")
            
        if not column_exists(cursor, 'submissions', 'plagiarism_score'):
            cursor.execute('ALTER TABLE submissions ADD COLUMN plagiarism_score REAL DEFAULT 0.0')
            print("Added plagiarism_score to submissions table")
            
        if not column_exists(cursor, 'submissions', 'grade'):
            cursor.execute('ALTER TABLE submissions ADD COLUMN grade INTEGER')
            print("Added grade to submissions table")
            
        if not column_exists(cursor, 'submissions', 'feedback'):
            cursor.execute('ALTER TABLE submissions ADD COLUMN feedback TEXT')
            print("Added feedback to submissions table")
            
        if not column_exists(cursor, 'submissions', 'status'):
            cursor.execute('ALTER TABLE submissions ADD COLUMN status TEXT DEFAULT "submitted"')
            print("Added status to submissions table")
        
        # Update source_docs table
        if not column_exists(cursor, 'source_docs', 'title'):
            cursor.execute('ALTER TABLE source_docs ADD COLUMN title TEXT')
            print("Added title to source_docs table")
            
        if not column_exists(cursor, 'source_docs', 'author'):
            cursor.execute('ALTER TABLE source_docs ADD COLUMN author TEXT')
            print("Added author to source_docs table")
            
        if not column_exists(cursor, 'source_docs', 'created_at'):
            cursor.execute('ALTER TABLE source_docs ADD COLUMN created_at TIMESTAMP')
            cursor.execute('UPDATE source_docs SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL')
            print("Added created_at to source_docs table")
        
        # Create notifications table if it doesn't exist
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS notifications (
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
        print("Created notifications table")
        
        # Create indexes (only if columns exist)
        try:
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_assignments_faculty ON assignments(faculty_id)')
            print("Created index on assignments.faculty_id")
        except sqlite3.OperationalError:
            pass
            
        try:
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_assignments_due_date ON assignments(due_date)')
            print("Created index on assignments.due_date")
        except sqlite3.OperationalError:
            pass
            
        try:
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_submissions_assignment ON submissions(assignment_id)')
            print("Created index on submissions.assignment_id")
        except sqlite3.OperationalError:
            pass
            
        try:
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_submissions_student ON submissions(student_id)')
            print("Created index on submissions.student_id")
        except sqlite3.OperationalError:
            pass
            
        try:
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_submissions_status ON submissions(status)')
            print("Created index on submissions.status")
        except sqlite3.OperationalError:
            pass
            
        try:
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id)')
            print("Created index on notifications.user_id")
        except sqlite3.OperationalError:
            pass
            
        try:
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_notifications_read ON notifications(is_read)')
            print("Created index on notifications.is_read")
        except sqlite3.OperationalError:
            pass
        
        # Add unique constraint to submissions if it doesn't exist
        try:
            cursor.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_submissions_unique ON submissions(student_id, assignment_id)')
            print("Created unique index on submissions")
        except sqlite3.OperationalError:
            pass
        
        conn.commit()
        print("\n✅ Database migration completed successfully!")
        print("Your database now has all the enhanced features:")
        print("- Timestamps for all tables")
        print("- Assignment due dates and categories")
        print("- File metadata for submissions")
        print("- Plagiarism scores and grading")
        print("- Notifications system")
        print("- Performance indexes")
        
    except Exception as e:
        print(f"❌ Error during migration: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == '__main__':
    migrate_database()
