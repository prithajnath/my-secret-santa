class dbMixin(object):
    def save_to_db(self, db):
        db.session.add(self)
        db.session.commit()

    def delete_from_db(self, db):
        db.session.delete(self)
        db.session.commit()
