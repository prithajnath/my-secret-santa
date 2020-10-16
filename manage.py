from flask_script import Manager
from flask_migrate import Migrate, MigrateCommand
from commands import CreateSuperUser, SeedDatabase
from app import app, db


migrate = Migrate(app, db)
manager = Manager(app)
manager.add_command('db', MigrateCommand)
manager.add_command('createsuperuser', CreateSuperUser)
manager.add_command('seed', SeedDatabase)

if __name__ == "__main__":
    manager.run()
