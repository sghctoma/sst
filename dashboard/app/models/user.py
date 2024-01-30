import uuid

from dataclasses import dataclass

from argon2 import PasswordHasher
from app.extensions import jwt, db


@jwt.user_identity_loader
def user_identity_lookup(user):
    return user.id


@jwt.user_lookup_loader
def user_lookup_callback(_jwt_header, jwt_data):
    identity = jwt_data['sub']
    return db.session.execute(
        db.select(User).filter_by(id=uuid.UUID(identity))).scalar_one_or_none()


@dataclass
class User(db.Model):
    id: uuid.UUID = db.Column(db.Uuid(), primary_key=True, default=uuid.uuid4)
    username: str = db.Column(db.Text, nullable=False, unique=True)
    hash = db.Column(db.Text, nullable=False)

    def check_password(self, password):
        ph = PasswordHasher()
        try:
            ph.verify(self.hash, password)
        except BaseException:
            return False

        if ph.check_needs_rehash(self.hash):
            self.hash = ph.hash(password)
            db.session.commit()

        return True
