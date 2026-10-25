from models import User, Group
from flask_marshmallow import Marshmallow

ma = Marshmallow()


class UserSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = User
        include_relationships = True
        load_instance = True
        # Geography has no marshmallow field, and home coordinates must never be serialized
        exclude = ("location",)


class GroupSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Group
        load_instance = True
