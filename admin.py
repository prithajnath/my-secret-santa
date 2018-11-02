from flask_admin import Admin, AdminIndexView
from flask_admin.contrib.sqla import ModelView
from models import User, Participant

def register(app, db):
    #admin = Admin(app, index_view=MyAdminIndexView())
    admin = Admin(app)
    admin.add_view(ModelView(User, db.session))
    admin.add_view(ModelView(Participant, db.session))
