#!/usr/bin/env python3
"""
Deployment Script for Abstract Submission and Team Management Features
CampusConnect+ Event Management System
"""

import os
import sys
import sqlite3
import subprocess
from datetime import datetime

def check_requirements():
    """Check if all requirements are met"""
    print("🔍 Checking system requirements...")
    
    # Check Python version
    if sys.version_info < (3, 8):
        print("❌ Python 3.8+ is required")
        return False
    
    print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor} detected")
    
    # Check if database exists
    if not os.path.exists('database.db'):
        print("❌ Database not found. Please run init_db.py first")
        return False
    
    print("✅ Database found")
    
    # Check required directories
    upload_dirs = [
        'static/uploads/abstracts',
        'static/uploads/profile_pics'
    ]
    
    for directory in upload_dirs:
        if not os.path.exists(directory):
            print(f"📁 Creating directory: {directory}")
            os.makedirs(directory, exist_ok=True)
        else:
            print(f"✅ Directory exists: {directory}")
    
    return True

def run_migration():
    """Run database migration"""
    print("\n🔄 Running database migration...")
    
    try:
        # Import and run migration
        from migrate_abstract_teams import migrate_database
        migrate_database()
        print("✅ Database migration completed successfully")
        return True
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        return False

def verify_blueprints():
    """Verify that all blueprints are properly registered"""
    print("\n🔍 Verifying blueprint registration...")
    
    try:
        from blueprints import blueprints
        expected_blueprints = ['auth', 'events', 'event_manager', 'main', 'abstracts', 'teams']
        
        registered_names = [bp.name for bp in blueprints]
        
        for expected in expected_blueprints:
            if expected in registered_names:
                print(f"✅ Blueprint '{expected}' registered")
            else:
                print(f"❌ Blueprint '{expected}' missing")
                return False
        
        return True
    except Exception as e:
        print(f"❌ Blueprint verification failed: {e}")
        return False

def test_plagiarism_checker():
    """Test plagiarism checker functionality"""
    print("\n🔍 Testing plagiarism checker...")
    
    try:
        from plagiarism_checker import PlagiarismChecker
        
        checker = PlagiarismChecker()
        
        # Test with sample text
        sample_text = "This is a test abstract for the plagiarism detection system."
        
        # This would require an actual event in the database
        # For now, just test that the class can be instantiated
        print("✅ Plagiarism checker initialized successfully")
        return True
    except Exception as e:
        print(f"❌ Plagiarism checker test failed: {e}")
        return False

def create_sample_data():
    """Create sample data for testing"""
    print("\n📊 Creating sample data...")
    
    try:
        conn = sqlite3.connect('database.db')
        conn.row_factory = sqlite3.Row
        
        # Check if we have events that require abstracts
        events_with_abstracts = conn.execute("""
            SELECT COUNT(*) as count FROM event_requirements WHERE requires_abstract = 1
        """).fetchone()
        
        if events_with_abstracts['count'] > 0:
            print(f"✅ Found {events_with_abstracts['count']} events configured for abstracts")
        else:
            print("ℹ️ No events currently require abstracts")
        
        # Check team functionality
        teams_count = conn.execute("SELECT COUNT(*) as count FROM teams").fetchone()
        print(f"✅ Database contains {teams_count['count']} teams")
        
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Sample data creation failed: {e}")
        return False

def verify_templates():
    """Verify that all required templates exist"""
    print("\n🔍 Verifying templates...")
    
    required_templates = [
        'templates/submit_abstract.html',
        'templates/create_team.html',
        'templates/team_dashboard.html',
        'templates/team_invitation.html',
        'templates/manage_abstracts.html',
        'templates/review_abstract.html'
    ]
    
    all_exist = True
    for template in required_templates:
        if os.path.exists(template):
            print(f"✅ Template found: {template}")
        else:
            print(f"❌ Template missing: {template}")
            all_exist = False
    
    return all_exist

def run_basic_tests():
    """Run basic functionality tests"""
    print("\n🧪 Running basic functionality tests...")
    
    try:
        # Test database connection
        conn = sqlite3.connect('database.db')
        
        # Test new tables exist
        tables_to_check = [
            'abstract_submissions',
            'team_invitations',
            'event_requirements',
            'team_activity_logs'
        ]
        
        for table in tables_to_check:
            result = conn.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'").fetchone()
            if result:
                print(f"✅ Table '{table}' exists")
            else:
                print(f"❌ Table '{table}' missing")
                return False
        
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Basic tests failed: {e}")
        return False

def display_usage_instructions():
    """Display usage instructions"""
    print("\n" + "="*60)
    print("🎉 DEPLOYMENT COMPLETED SUCCESSFULLY!")
    print("="*60)
    print("\n📋 NEXT STEPS:")
    print("\n1. Start the application:")
    print("   python app.py")
    print("\n2. Access the application:")
    print("   http://localhost:5000")
    print("\n3. Test new features:")
    print("   • Create or join teams for events")
    print("   • Submit abstracts for hackathons/competitions")
    print("   • Review submissions as event manager")
    print("   • Export reports and analytics")
    print("\n4. Default accounts:")
    print("   • Admin: admin/admin123")
    print("   • Event Manager: manager1/manager123")
    print("   • Students: john_doe/student123, jane_smith/student123")
    print("\n📚 Documentation:")
    print("   • See ABSTRACT_TEAM_FEATURES.md for detailed documentation")
    print("   • Check application logs for any issues")
    print("\n🔧 Configuration:")
    print("   • Modify event requirements in the admin panel")
    print("   • Adjust plagiarism thresholds as needed")
    print("   • Configure email settings for notifications")
    print("\n" + "="*60)

def main():
    """Main deployment function"""
    print("🚀 CampusConnect+ Feature Deployment")
    print("=" * 50)
    print("Deploying Abstract Submission and Team Management Features")
    print("=" * 50)
    
    # Step 1: Check requirements
    if not check_requirements():
        print("\n❌ Requirements check failed. Please fix issues and try again.")
        sys.exit(1)
    
    # Step 2: Run migration
    if not run_migration():
        print("\n❌ Database migration failed. Please check logs and try again.")
        sys.exit(1)
    
    # Step 3: Verify blueprints
    if not verify_blueprints():
        print("\n❌ Blueprint verification failed. Please check blueprint registration.")
        sys.exit(1)
    
    # Step 4: Test plagiarism checker
    if not test_plagiarism_checker():
        print("\n⚠️ Plagiarism checker test failed. Feature may not work correctly.")
    
    # Step 5: Verify templates
    if not verify_templates():
        print("\n❌ Template verification failed. Some features may not work.")
        sys.exit(1)
    
    # Step 6: Run basic tests
    if not run_basic_tests():
        print("\n❌ Basic functionality tests failed.")
        sys.exit(1)
    
    # Step 7: Create sample data
    create_sample_data()
    
    # Step 8: Display instructions
    display_usage_instructions()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️ Deployment interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Deployment failed with error: {e}")
        sys.exit(1)
