from functools import wraps
from flask import request, redirect, flash, current_app
import sqlite3
import os


def validate_input(required_fields):
    def decorator(function):
        @wraps(function)
        def decorated_function(*args, **kwargs):
            for field in required_fields:
                if not request.form.get(field):
                    flash(f"{field.replace('_', ' ').title()} is required.", 'danger')
                    return redirect(request.url)
            return function(*args, **kwargs)
        return decorated_function
    return decorator


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'gif'}


def safe_db_operation(operation_func, *args, **kwargs):
    """
    Safely execute database operations with proper connection management
    """
    conn = None
    try:
        conn = sqlite3.connect('instance/campusconnect.db')
        conn.row_factory = sqlite3.Row
        result = operation_func(conn, *args, **kwargs)
        conn.commit()
        return result
    except Exception as e:
        if conn:
            conn.rollback()
        current_app.logger.error(f"Database operation failed: {str(e)}")
        raise
    finally:
        if conn:
            conn.close()


def create_upload_directories(base_path, *subdirs):
    """
    Create upload directories if they don't exist
    """
    try:
        os.makedirs(base_path, exist_ok=True)
        for subdir in subdirs:
            path = os.path.join(base_path, subdir)
            os.makedirs(path, exist_ok=True)
        return True
    except Exception as e:
        current_app.logger.error(f"Error creating directories: {str(e)}")
        return False