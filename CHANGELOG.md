# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added

- Added `marshmallow-sqlalchemy` dependency required by `flask-marshmallow` for `SQLAlchemyAutoSchema`
- **New graph-based pairing method** (`_make_pairs_graph_based`) - Creates pairs using a graph traversal algorithm that:
  - Builds a graph where each user is a node and edges have random weights
  - Uses SQLAlchemy Core to query last year's pairs (most recent pairs for the group) to identify illegal edges
  - Removes illegal edges to ensure users don't get paired with the same person from last year
  - Traverses the graph starting from a random node using a greedy approach (selecting highest-weight edges) to create a cycle
  - Ensures randomness while avoiding previous year's pairings

### Changed

- **Migrated from flask-script to Flask's built-in CLI** - `flask-script` is deprecated and incompatible with Flask 2.x+ (missing `flask._compat` module)
  - Removed `flask-script` dependency from `pyproject.toml`
  - Refactored `commands.py` from `flask-script.Command` classes to Click-based CLI commands
    - `CreateSuperUser` class → `@app.cli.command("createsuperuser")`
    - `SeedDatabase` class → `@app.cli.command("seed")`
  - Simplified `manage.py` (kept for backwards compatibility)
  - Registered CLI commands in `app.py` via `register_commands(app, db)`
  - Updated `dev-entrypoint.sh` and `entrypoint.sh` to use Flask CLI:
    - `python manage.py db migrate` → `flask db migrate`
    - `python manage.py db upgrade` → `flask db upgrade`
  - Regenerated `requirements.txt` without flask-script

### Fixed

- **SQLAlchemy 2.x compatibility fixes**
  - Replaced deprecated `Query.get(id)` with `db.session.get(Model, id)` across all files (app.py, api/*.py)
  - Fixed `select([...])` syntax to `select(...)` in `sql/locks.py`
  - Fixed `onupdate=datetime.now` to `onupdate=func.current_timestamp()` in `models.py` for proper timestamp updates

- **Flask 3.x compatibility fixes**
  - Removed deprecated `CSRF_ENABLED=True` config (CSRF is now controlled via `CSRFProtect` extension)
  - Changed `SQLALCHEMY_TRACK_MODIFICATIONS` to `False` for better performance
  - Replaced `request.json.get()` with safer `request.get_json().get()` pattern in `app.py`

- **Code quality fixes**
  - Removed incorrect `UserMixin` inheritance from non-user models (`GroupsAndUsersAssociation`, `Group`, `GroupMessage`, `Pair`, `Issue`)
  - Removed unused `datetime` import from `models.py`

### Migration Guide

Database migrations and custom commands now use the Flask CLI:

```bash
# Set the Flask app (required for CLI)
export FLASK_APP=app.py

# Database migrations
flask db migrate
flask db upgrade

# Custom commands
flask createsuperuser
flask seed
```
