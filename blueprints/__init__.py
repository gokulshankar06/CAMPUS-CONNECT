# Package initializer for blueprints

# Import all blueprints to make them available when importing from blueprints
from .auth import auth_bp
from .events import events_bp
from .event_manager import event_manager_bp
from .main import main_bp
from .abstracts import abstracts_bp
from .teams import teams_bp
from .team_recruitment import team_recruitment_bp
from .prize_management import prize_management_bp

# List of all blueprints for easy registration
# Main blueprint should be registered first to handle root routes
blueprints = [
    main_bp,  # Register main_bp first to handle root routes
    auth_bp,
    events_bp,
    event_manager_bp,
    abstracts_bp,
    teams_bp,
    team_recruitment_bp,
    prize_management_bp
]

# Print debug information
print("[DEBUG] Blueprints being registered:")
for bp in blueprints:
    print(f"  - {bp.name} (import_name={bp.import_name})")

