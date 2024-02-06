import os
import shutil
import tempfile
import uuid

import pytest

from argon2 import PasswordHasher

from app import create_app
from app.extensions import db
from app.models.user import User
from app.utils.first_init import _generate_rsa_keys, _initiate_database


with open(os.path.join(os.path.dirname(__file__), 'data.sql'), 'rb') as f:
    _data_sql = f.read().decode('utf8')


@pytest.fixture
def app():
    tmp_dir = tempfile.mkdtemp()
    priv_key = f'{tmp_dir}/private_key.pem'
    pub_key = f'{tmp_dir}/public_key.pem'
    db_uri = f'sqlite:///{tmp_dir}/test.db'

    _generate_rsa_keys(priv_key, pub_key)

    app = create_app({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': db_uri,
        'JWT_PRIVATE_KEY_FILE': priv_key,
        'JWT_PUBLIC_KEY_FILE': pub_key,
        'JWT_CSRF_METHODS': [],
    })

    with app.app_context():
        _initiate_database()
        user = User(id=uuid.uuid4(), username="test")
        ph = PasswordHasher()
        user.hash = ph.hash("test")
        db.session.add(user)
        db.session.commit()

    yield app

    shutil.rmtree(tmp_dir)


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def runner(app):
    return app.test_cli_runner()


class AuthActions:
    def __init__(self, client):
        self._client = client

    def login(self, username="test", password="test"):
        return self._client.post(
            "/auth/login", json={"username": username, "password": password}
        )

    def logout(self):
        return self._client.delete("/auth/logout")


@pytest.fixture
def auth(client):
    return AuthActions(client)
