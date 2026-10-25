from commands import register_commands
from app import app, db

register_commands(app, db)

if __name__ == "__main__":
    app.run()
