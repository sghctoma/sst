import os
import shutil
import tempfile
import uuid

import pytest

from argon2 import PasswordHasher

from app import create_app
from app.extensions import db
from app.models.board import Board
from app.models.calibration import Calibration
from app.models.linkage import Linkage
from app.models.session import Session
from app.models.session_html import SessionHtml
from app.models.setup import Setup
from app.models.track import Track
from app.models.user import User
from app.utils.first_init import _generate_rsa_keys, _initiate_database


DB_IDS = dict(
    front_calibration=uuid.UUID('bc31128fe48e4ab899312a849571782f'),
    rear_calibration=uuid.UUID('51aa638a88334be1b5860b4bf4ad3bb7'),
    linkage=uuid.UUID('b8be0857e88345819e0e02a377b49ad4'),
    setup=uuid.UUID('7d1cc6ea25eb47f9a83d25b5e0a0179f'),
    track=uuid.UUID('3fb905fd802740b4a13d43a81f36d81d'),
    session=uuid.UUID('d85d5df4562c4b878eebaeb7bb676ec9'),
    session2=uuid.UUID('b8789424e29c4d5fa288c5b614adea3d'),
    session_html=uuid.UUID('b8789424e29c4d5fa288c5b614adea3d'),
    board='0011223344556677',
    calibration_method_fraction=uuid.UUID('230e04a092ce42189a3c23bf3cde2b05'),
    calibration_method_percentage=uuid.UUID('c619045af435427797cb1e2c1fddcfeb'),
    calibration_method_linear=uuid.UUID('3e799d5a5652430e900c06a3277ab1dc'),
    calibration_method_isosceles=uuid.UUID('12f4a1b922f74524abcbdaa99a5c1c3a'),
    calibration_method_triangle=uuid.UUID('9a27abc4125148a2b64989fb315ca2de'),
    nonexistent=uuid.UUID('00000000-0000-0000-0000-000000000000'),
)

with open(os.path.join(os.path.dirname(__file__), 'linkage.txt'), 'rb') as f:
    linkage_data = f.read().decode('utf8')

with open(os.path.join(os.path.dirname(__file__), 'track.json'), 'rb') as f:
    track_data = f.read().decode('utf8')

with open(os.path.join(os.path.dirname(__file__), 'track.gpx'), 'rb') as f:
    track_gpx = f.read().decode('utf8')

with open(os.path.join(os.path.dirname(__file__), 'test.psst'), 'rb') as f:
    session_data = f.read()

with open(os.path.join(os.path.dirname(__file__), 'session.js'), 'rb') as f:
    session_script = f.read().decode('utf8')


def add_test_data():
    front_calibration = Calibration(
        id=DB_IDS['front_calibration'],
        name='front_calibration',
        method_id=uuid.UUID('12f4a1b922f74524abcbdaa99a5c1c3a'),
        inputs={'arm': 134.9375, 'max': 234.15625}
    )
    rear_calibration = Calibration(
        id=DB_IDS['rear_calibration'],
        name='rear_calibration',
        method_id=uuid.UUID('9a27abc4125148a2b64989fb315ca2de'),
        inputs={'arm1': 98.9, 'arm2': 202.8, 'max': 230}
    )
    linkage = Linkage(
        id=DB_IDS['linkage'],
        name='test_linkage',
        head_angle=63.5,
        front_stroke=180,
        rear_stroke=65,
        data=linkage_data
    )
    setup = Setup(
        id=DB_IDS['setup'],
        name='test_setup',
        linkage_id=DB_IDS['linkage'],
        front_calibration_id=DB_IDS['front_calibration'],
        rear_calibration_id=DB_IDS['rear_calibration']
    )
    track = Track(
        id=DB_IDS['track'],
        track=track_data
    )
    session = Session(
        id=DB_IDS['session'],
        name="test_session",
        description="session description",
        setup=DB_IDS['setup'],
        track=DB_IDS['track'],
        timestamp=1500000000,
    )
    session.data = session_data
    board = Board(id=DB_IDS['board'], setup_id=DB_IDS['setup'])

    # A second session is only needed so that we also have a session with an
    # already generated session_html.
    session2 = Session(
        id=DB_IDS['session_html'],
        name="test_session",
        description="session description",
        setup=DB_IDS['setup'],
        track=DB_IDS['track'],
        timestamp=1683457678,
    )
    session2.data = session_data
    session_html = SessionHtml(
        session_id=DB_IDS['session_html'],
        script=session_script,
        travel='<div id="a13dfdbf-19b4-41de-98f1-4251281bd1f9" data-root-id="p1968" style="display: contents;"></div>',
        velocity='<div id="b942c6c9-400a-4dcd-bf26-fb759997141f" data-root-id="p2089" style="display: contents;"></div>',
        map='<div id="ef4c2de6-b611-4d9f-bc51-3b8237ecf610" data-root-id="p2349" style="display: contents;"></div>',
        lr='<div id="c390f586-2dde-42bf-bb70-f167236d59d1" data-root-id="p2141" style="display: contents;"></div>',
        sw='<div id="a0bb159f-829a-4d92-a8a6-ad744800f666" data-root-id="p2173" style="display: contents;"></div>',
        f_thist='<div id="fc86b57d-f4c6-42ea-9776-89e192e5df8a" data-root-id="p1004" style="display: contents;"></div>',
        f_fft='<div id="ec36612a-d13c-4e96-a707-079b33721215" data-root-id="p1444" style="display: contents;"></div>',
        f_vhist='<div id="cd1feb3d-d6d3-4b77-8811-a929089db21d" data-root-id="p2408" style="display: contents;"></div>',
        r_thist='<div id="e7c214ef-cdbf-41a2-88fa-d5ab2219c16b" data-root-id="p1486" style="display: contents;"></div>',
        r_fft='<div id="c0478ff9-1143-49ab-b783-3e5426cb585e" data-root-id="p1926" style="display: contents;"></div>',
        r_vhist='<div id="ec8fa845-ccc0-4aa0-871e-eb6b173786ba" data-root-id="p2409" style="display: contents;"></div>',
        cbalance='<div id="e54d6616-1969-45fd-85bf-b1bdd2c2447b" data-root-id="p2211" style="display: contents;"></div>',
        rbalance='<div id="a3859fe3-1e75-45e9-9dd4-b4e42014647e" data-root-id="p2280" style="display: contents;"></div>',
    )

    db.session.add(front_calibration)
    db.session.add(rear_calibration)
    db.session.add(linkage)
    db.session.add(setup)
    db.session.add(track)
    db.session.add(session)
    db.session.add(session2)
    db.session.add(session_html)
    db.session.add(board)
    db.session.commit()


@pytest.fixture
def app():
    tmp_dir = tempfile.mkdtemp()
    priv_key = f'{tmp_dir}/private_key.pem'
    pub_key = f'{tmp_dir}/public_key.pem'
    db_uri = 'sqlite://'

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
        add_test_data()

        user = User(id=uuid.uuid4(), username='test')
        ph = PasswordHasher()
        user.hash = ph.hash('test')
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

    def login(self, username='test', password='test'):
        return self._client.post(
            '/auth/login', json={'username': username, 'password': password}
        )

    def logout(self):
        return self._client.delete('/auth/logout')


@pytest.fixture
def auth(client):
    return AuthActions(client)
