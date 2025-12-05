from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from flask_login import login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import random
import sqlite3
import os
from werkzeug.utils import secure_filename

from models import User, get_db_connection
from utils.email_utils import send_email


auth_bp = Blueprint('auth', __name__)

# Configure upload folder for profile pictures
UPLOAD_FOLDER = os.path.join('static', 'uploads', 'profile_pics')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@auth_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        role = request.form.get('role', '').strip()
        full_name = request.form.get('full_name', '').strip()

        if not username or not email or not password or not role:
            flash('All fields are required.', 'danger')
            return render_template('signup.html')

        if role not in ('student', 'event_manager', 'admin'):
            flash('Invalid role selected.', 'danger')
            return render_template('signup.html')

        hashed_password = generate_password_hash(password)
        otp = str(random.randint(100000, 999999))

        # Use username as full_name if not provided
        if not full_name:
            full_name = username

        conn = get_db_connection()
        try:
            conn.execute(
                "INSERT INTO users (username, email, password, role, full_name, is_verified, otp) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (username, email, hashed_password, role, full_name, False, otp)
            )
            conn.commit()

            session['email'] = email
            session['otp'] = otp

            sent = send_email(email, otp)

            if sent:
                flash('Registration successful! Please check your email for the OTP.', 'success')
            else:
                # Development-friendly fallback: reveal OTP if email is not configured
                if current_app.config.get('DEBUG', False):
                    flash(f'Registration successful! (Dev) Email could not be sent. Your OTP is: {otp}', 'warning')
                else:
                    flash('Registration successful, but we could not send the OTP email. Please try again later.', 'warning')
            return redirect(url_for('auth.verify_otp'))
        except sqlite3.IntegrityError:
            flash('Username or email already exists.', 'danger')
        finally:
            conn.close()

    return render_template('signup.html')


@auth_bp.route('/verify_otp', methods=['GET', 'POST'])
def verify_otp():
    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'change_email':
            new_email = request.form.get('new_email', '').strip()
            if not new_email:
                flash('Please enter a valid email.', 'danger')
                return render_template('verify_otp.html')

            from sqlite3 import IntegrityError
            import random
            otp = str(random.randint(100000, 999999))

            conn = get_db_connection()
            try:
                # Ensure new email is not already taken
                existing = conn.execute("SELECT id FROM users WHERE email = ?", (new_email,)).fetchone()
                if existing:
                    flash('Email already in use. Please use a different email.', 'danger')
                    return render_template('verify_otp.html')

                # Update the unverified user's email and OTP based on the current session email
                conn.execute(
                    "UPDATE users SET email = ?, otp = ? WHERE email = ? AND is_verified = 0",
                    (new_email, otp, session.get('email'))
                )
                conn.commit()

                # Update session and resend OTP
                session['email'] = new_email
                session['otp'] = otp
                sent = send_email(new_email, otp)

                if sent:
                    flash('Email updated. A new OTP has been sent to your new address.', 'success')
                else:
                    if current_app.config.get('DEBUG', False):
                        flash(f'Email updated. (Dev) Email could not be sent. Your new OTP is: {otp}', 'warning')
                    else:
                        flash('Email updated, but we could not send the OTP email. Please try again later.', 'warning')
                return redirect(url_for('auth.verify_otp'))
            except IntegrityError:
                flash('Email already exists. Try another email.', 'danger')
            finally:
                conn.close()

        else:
            user_otp = request.form.get('otp')

            if user_otp == session.get('otp'):
                conn = get_db_connection()
                conn.execute(
                    "UPDATE users SET is_verified = ? WHERE email = ?",
                    (True, session.get('email'))
                )
                conn.commit()
                conn.close()
                flash('Email verified successfully! You can now log in.', 'success')
                return redirect(url_for('auth.login'))
            else:
                flash('Invalid OTP. Please try again.', 'danger')

    return render_template('verify_otp.html')


@auth_bp.route('/resend_otp', methods=['POST'])
def resend_otp():
    email = session.get('email')
    if not email:
        flash('Session expired. Please try signing up again.', 'danger')
        return redirect(url_for('auth.signup'))

    otp = str(random.randint(100000, 999999))
    conn = get_db_connection()
    conn.execute(
        "UPDATE users SET otp = ? WHERE email = ?",
        (otp, email)
    )
    conn.commit()
    conn.close()

    session['otp'] = otp
    sent = send_email(email, otp)

    if sent:
        flash('A new OTP has been sent to your email!', 'success')
    else:
        if current_app.config.get('DEBUG', False):
            flash(f'(Dev) Email could not be sent. Your new OTP is: {otp}', 'warning')
        else:
            flash('We could not send the OTP email. Please try again later or contact support.', 'danger')
    return redirect(url_for('auth.verify_otp'))


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not username or not password:
            flash('Username and password are required.', 'danger')
            return render_template('login_standalone.html')

        user = User.get_by_username(username)

        if user and check_password_hash(user.password, password):
            if user.is_verified:
                login_user(user)
                conn = get_db_connection()
                conn.execute(
                    "UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?",
                    (user.id,)
                )
                conn.commit()
                conn.close()
                flash(f'Welcome back, {user.username}!', 'success')
                return redirect(url_for('main.dashboard'))
            else:
                flash('Please verify your email before logging in.', 'warning')
                session['email'] = user.email
                session['otp'] = user.otp
                return redirect(url_for('auth.verify_otp'))
        else:
            flash('Invalid username or password.', 'danger')
    return render_template('login_standalone.html')

@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    # Debug: Print current user and request info
    current_app.logger.info(f"Profile route accessed by user: {current_user.id} ({current_user.username})")
    current_app.logger.info(f"Request method: {request.method}")
    current_app.logger.info(f"URL for auth.profile: {url_for('auth.profile', _external=True)}")

    # Ensure upload directory exists
    upload_path = os.path.join(current_app.root_path, 'static', 'uploads', 'profile_pics')
    os.makedirs(upload_path, exist_ok=True)

    if request.method == 'POST':
        try:
            # Handle profile update
            username = request.form.get('username', '').strip()
            email = request.form.get('email', '').strip()
            full_name = request.form.get('full_name', '').strip()
            bio = request.form.get('bio', '').strip()

            current_app.logger.info(f"Updating profile for user {current_user.id}")

            # Handle profile picture upload
            profile_pic_path = current_user.profile_picture # Keep the old path by default
            file = request.files.get('profile_pic')

            if file and file.filename != '' and allowed_file(file.filename):
                # Generate a secure filename
                filename = f"user_{current_user.id}_{secure_filename(file.filename)}"
                filepath = os.path.join(upload_path, filename)

                # Save the file
                file.save(filepath)

                # Store relative path for database
                profile_pic_path = os.path.join('uploads', 'profile_pics', filename).replace('\\', '/')
                current_app.logger.info(f"Profile picture saved to: {profile_pic_path}")

            # Update user info in database
            conn = get_db_connection()
            try:
                conn.execute(
                    '''UPDATE users SET username = ?, email = ?, full_name = ?,
                       bio = ?, profile_picture = ? WHERE id = ?''',
                    (username, email, full_name, bio, profile_pic_path, current_user.id)
                )
                conn.commit()
                current_app.logger.info("Profile updated successfully")
                flash('Profile updated successfully!', 'success')
            except Exception as e:
                conn.rollback()
                current_app.logger.error(f"Error updating profile: {str(e)}")
                flash('Error updating profile. Please try again.', 'error')
            finally:
                conn.close()

            return redirect(url_for('auth.profile'))

        except Exception as e:
            current_app.logger.error(f"Unexpected error in profile update: {str(e)}")
            flash('An unexpected error occurred. Please try again.', 'error')

    # For GET request, fetch current user data
    conn = get_db_connection()
    try:
        user_data = conn.execute(
            'SELECT username, email, full_name, bio, profile_picture, role, created_at FROM users WHERE id = ?',
            (current_user.id,)
        ).fetchone()

        if not user_data:
            current_app.logger.error(f"User data not found for user_id: {current_user.id}")
            flash('User data not found. Please log in again.', 'error')
            return redirect(url_for('auth.login'))

        # Convert Row to dict for easier handling in template
        user_data = dict(user_data)

        # Ensure profile_picture has a default value if None
        if not user_data['profile_picture']:
            user_data['profile_picture'] = 'images/default-avatar.png'

        current_app.logger.debug(f"Loaded user data: {user_data}")

        return render_template('profile.html', user_data=user_data)

    except Exception as e:
        current_app.logger.error(f"Error fetching user data: {str(e)}")
        flash('Error loading profile data. Please try again.', 'error')
        return redirect(url_for('main.dashboard'))

    finally:
        conn.close()

@auth_bp.route('/change_password', methods=['POST'])
@login_required
def change_password():
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')

    if not all([current_password, new_password, confirm_password]):
        flash('All fields are required.', 'danger')
        return redirect(url_for('auth.profile'))

    if new_password != confirm_password:
        flash('New passwords do not match.', 'danger')
        return redirect(url_for('auth.profile'))

    if len(new_password) < 8:
        flash('Password must be at least 8 characters long.', 'danger')
        return redirect(url_for('auth.profile'))

    conn = get_db_connection()
    user = conn.execute('SELECT password FROM users WHERE id = ?', (current_user.id,)).fetchone()

    if not check_password_hash(user['password'], current_password):
        flash('Current password is incorrect.', 'danger')
        conn.close()
        return redirect(url_for('auth.profile'))

    # Update password
    hashed_password = generate_password_hash(new_password)
    conn.execute('UPDATE users SET password = ? WHERE id = ?', (hashed_password, current_user.id))
    conn.commit()
    conn.close()

    flash('Password updated successfully!', 'success')
    return redirect(url_for('auth.profile'))

@auth_bp.route('/logout')
@login_required
def logout():
    # Clear all session data
    session.clear()
    # Logout the user
    logout_user()
    flash('You have been logged out successfully.', 'success')
    return redirect(url_for('auth.login'))