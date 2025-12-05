from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_login import LoginManager, login_required, current_user
import os
import logging
from datetime import datetime

from chatbot import get_response
from models import User, get_db_connection
from config import config
from dotenv import load_dotenv
from blueprints import blueprints
from init_db import init_database # Import the function

# Load environment variables
load_dotenv()

# Setup Flask app
app = Flask(__name__)
app.config.from_object(config[os.environ.get('FLASK_ENV') or 'default'])

# Setup logging
log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
log_file = 'campusconnect.log'

# Configure root logger
logging.basicConfig(
    level=logging.DEBUG,
    format=log_format,
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)

# Get logger for this module
logger = logging.getLogger(__name__)
logger.info("Starting CampusConnect application")

# Create upload folder if it doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Setup Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'

@login_manager.user_loader
def load_user(user_id):
    return User.get(user_id)

# Custom Jinja2 filters
@app.template_filter('format_date')
def format_date(date_string, format='%b %d, %Y'):
    """Format date string from database to readable format"""
    if not date_string:
        return 'No date'

    try:
        # Handle different date formats from SQLite
        if isinstance(date_string, str):
            # Try parsing common SQLite date formats
            for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%Y-%m-%dT%H:%M:%S']:
                try:
                    date_obj = datetime.strptime(date_string, fmt)
                    return date_obj.strftime(format)
                except ValueError:
                    continue
            # If no format matches, return as is
            return date_string
        else:
            # If it's already a datetime object
            return date_string.strftime(format)
    except Exception:
        return str(date_string)

@app.template_filter('format_datetime')
def format_datetime(datetime_string, format='%b %d, %Y %I:%M %p'):
    """Format datetime string from database to readable format"""
    return format_date(datetime_string, format)

# Add 'now' function to Jinja2 environment globals
def get_now():
    """Return current datetime - called each time template is rendered"""
    return datetime.now()

app.jinja_env.globals['now'] = get_now

### Blueprints are now defined in the `blueprints/` package and imported above.

@app.route('/')
def index():
    return render_template('index_standalone.html')


@app.route('/notifications')
@login_required
def notifications():
    conn = get_db_connection()
    user_notifications = conn.execute(
        "SELECT * FROM notifications WHERE user_id = ? ORDER BY created_at DESC LIMIT 20",
        (current_user.id,)
    ).fetchall()
    conn.close()
    return render_template('notifications_standalone.html',
                         user=current_user,
                         notifications=user_notifications)

@app.route('/mark_notification_read/<int:notification_id>')
@login_required
def mark_notification_read(notification_id):
    conn = get_db_connection()
    conn.execute(
        "UPDATE notifications SET is_read = 1 WHERE id = ? AND user_id = ?",
        (notification_id, current_user.id)
    )
    conn.commit()
    conn.close()
    return redirect(url_for('notifications'))

@app.route('/chatbot')
@login_required
def chatbot():
    return render_template('chatbot.html', user=current_user)

@app.route('/chat', methods=['POST'])
@login_required
def chat():
    user_input = request.json.get('user_input')
    chatbot_response = get_response(user_input)
    return jsonify({'response': chatbot_response})

# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    return render_template('errors/404_standalone.html'), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {error}")
    return render_template('errors/500_standalone.html'), 500

# Register all blueprints
app.logger.info("Registering blueprints...")
for bp in blueprints:
    app.logger.info(f"Registering blueprint: {bp.name} with url_prefix: {bp.url_prefix}")
    app.register_blueprint(bp)

# Debug: List all registered routes
app.logger.info("Registered routes:")
for rule in app.url_map.iter_rules():
    app.logger.info(f"{rule.endpoint}: {rule.rule} -> {rule.methods}")

if __name__ == '__main__':
    if not os.path.exists('database.db'):
        logger.info("Database not found. Creating new database...")
        init_database()

    app.run(debug=app.config.get('DEBUG', False), host='0.0.0.0', port=5000)