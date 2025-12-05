#!/usr/bin/env python3
"""
Clean up CampusConnect folder - Remove test files, docs, and unnecessary files
Keeps only essential files needed to run the project
"""

import os
import shutil
from pathlib import Path

def cleanup_project():
    """Remove unnecessary files while keeping essentials"""
    print("🧹 CAMPUSCONNECT PROJECT CLEANUP")
    print("=" * 60)
    
    # Files to DELETE (patterns)
    delete_patterns = [
        # Test files
        "test_*.py",
        "*_test.py",
        "check_*.py",
        "verify_*.py",
        "debug_*.py",
        "fix_*.py",
        "setup_*.py",
        "create_*.py",
        "list_*.py",
        "enable_*.py",
        "quick_*.py",
        
        # Documentation files
        "*.md",
        "*.txt",
        "*.rst",
        "README*",
        "FEATURES_*",
        "ABSTRACT_*",
        "QUICK_*",
        
        # Batch and script files
        "*.bat",
        "*.sh",
        "*.sql",
        
        # Backup files
        "*_backup.*",
        "*.bak",
        "*.backup",
        "*_old.*",
        "*.old",
        
        # Log files
        "*.log",
        
        # Temporary files
        "*.tmp",
        "*.temp",
        
        # IDE and editor files
        ".idea",
        ".vscode",
        "*.swp",
        ".DS_Store",
        
        # Python cache
        "__pycache__",
        "*.pyc",
        "*.pyo",
        "*.pyd",
        ".Python",
        
        # Environment files
        "env/",
        "venv/",
        ".env.example",
        
        # Package files
        "*.egg",
        "*.egg-info",
        "dist/",
        "build/",
        "eggs/",
        ".eggs/",
        
        # Coverage and testing
        ".coverage",
        ".pytest_cache/",
        "nosetests.xml",
        "coverage.xml",
        "*.cover",
        ".hypothesis/",
        
        # Documentation build
        "docs/",
        "_build/",
        
        # Jupyter
        ".ipynb_checkpoints",
        "*.ipynb"
    ]
    
    # Files to KEEP (essential for running the project)
    keep_files = [
        # Core application files
        "app.py",
        "config.py",
        "models.py",
        "forms.py",
        "chatbot.py",
        "plagiarism_checker.py",
        "init_db.py",
        "database.db",
        "requirements.txt",
        ".env",
        
        # Essential scripts
        "run.py",
        "wsgi.py",
        
        # Keep this cleanup script temporarily
        "cleanup_project.py"
    ]
    
    # Directories to KEEP
    keep_dirs = [
        "blueprints",
        "templates", 
        "static",
        "migrations",
        "utils"
    ]
    
    deleted_files = []
    deleted_dirs = []
    kept_files = []
    total_size_freed = 0
    
    # Walk through all files and directories
    for root, dirs, files in os.walk(".", topdown=False):
        # Skip git directory
        if ".git" in root:
            continue
            
        # Process files
        for file in files:
            file_path = os.path.join(root, file)
            relative_path = os.path.relpath(file_path, ".")
            
            # Check if file should be kept
            should_keep = False
            
            # Check if in essential files list
            if file in keep_files:
                should_keep = True
            
            # Check if in essential directory
            for keep_dir in keep_dirs:
                if relative_path.startswith(keep_dir + os.sep):
                    # Only keep Python files and templates in these directories
                    if file.endswith(('.py', '.html', '.css', '.js', '.jpg', '.png', '.gif')):
                        should_keep = True
                        break
            
            # Delete if matches delete pattern and not marked to keep
            if not should_keep:
                should_delete = False
                
                # Check against delete patterns
                for pattern in delete_patterns:
                    if pattern.startswith("*") and pattern.endswith("*"):
                        # Contains pattern
                        if pattern[1:-1] in file:
                            should_delete = True
                            break
                    elif pattern.startswith("*"):
                        # Ends with pattern
                        if file.endswith(pattern[1:]):
                            should_delete = True
                            break
                    elif pattern.endswith("*"):
                        # Starts with pattern
                        if file.startswith(pattern[:-1]):
                            should_delete = True
                            break
                    else:
                        # Exact match
                        if file == pattern:
                            should_delete = True
                            break
                
                if should_delete:
                    try:
                        file_size = os.path.getsize(file_path)
                        os.remove(file_path)
                        deleted_files.append(relative_path)
                        total_size_freed += file_size
                    except Exception as e:
                        print(f"⚠️  Could not delete {relative_path}: {e}")
                else:
                    kept_files.append(relative_path)
        
        # Process directories
        for dir_name in dirs:
            dir_path = os.path.join(root, dir_name)
            relative_dir = os.path.relpath(dir_path, ".")
            
            # Skip essential directories
            if dir_name in keep_dirs or dir_name == ".git":
                continue
            
            # Delete if matches pattern
            for pattern in delete_patterns:
                if pattern.endswith("/"):
                    if dir_name == pattern[:-1]:
                        try:
                            shutil.rmtree(dir_path)
                            deleted_dirs.append(relative_dir)
                        except Exception as e:
                            print(f"⚠️  Could not delete directory {relative_dir}: {e}")
                        break
                elif dir_name == pattern:
                    try:
                        shutil.rmtree(dir_path)
                        deleted_dirs.append(relative_dir)
                    except Exception as e:
                        print(f"⚠️  Could not delete directory {relative_dir}: {e}")
                    break
    
    # Print summary
    print("\n📊 CLEANUP SUMMARY:")
    print("=" * 60)
    print(f"✅ Deleted {len(deleted_files)} files")
    print(f"✅ Deleted {len(deleted_dirs)} directories")
    print(f"✅ Freed up {total_size_freed / 1024 / 1024:.2f} MB")
    
    if len(deleted_files) > 0:
        print("\n🗑️  DELETED FILES (showing first 20):")
        for f in deleted_files[:20]:
            print(f"   - {f}")
        if len(deleted_files) > 20:
            print(f"   ... and {len(deleted_files) - 20} more files")
    
    print("\n✅ ESSENTIAL FILES KEPT:")
    essential_kept = [f for f in kept_files if not f.startswith(('.', '__'))]
    for f in sorted(set(essential_kept))[:20]:
        print(f"   - {f}")
    
    print("\n📁 PROJECT STRUCTURE AFTER CLEANUP:")
    print("   CampusConnect/")
    print("   ├── app.py (main application)")
    print("   ├── database.db (database)")
    print("   ├── blueprints/ (route handlers)")
    print("   ├── templates/ (HTML templates)")
    print("   ├── static/ (CSS, JS, images)")
    print("   ├── migrations/ (database migrations)")
    print("   └── utils/ (utility functions)")
    
    print("\n🚀 PROJECT IS NOW CLEAN AND READY TO RUN!")
    print("   Run: python app.py")
    
    # Offer to delete this cleanup script too
    print("\n❓ This cleanup script can also be deleted.")
    print("   Delete cleanup_project.py manually after running if desired.")

if __name__ == "__main__":
    response = input("⚠️  This will delete test files, docs, and backups. Continue? (yes/no): ")
    if response.lower() in ['yes', 'y']:
        cleanup_project()
    else:
        print("❌ Cleanup cancelled.")
