import time
import uuid
from datetime import datetime
from http import HTTPStatus as status

from app.extensions import db
from app.models.board import Board
from app.models.calibration import Calibration, CalibrationMethod
from app.models.linkage import Linkage
from app.models.setup import Setup
from app.telemetry.psst import dataclass_from_dict as dfd
from conftest import DB_IDS


def _create_test_entities():
    new_calibration = dict(
        id=uuid.uuid4(),
        name='new_calibration',
        method_id=DB_IDS['calibration_method_isosceles'],
        inputs={'arm': 134.9375, 'max': 234.15625}
    )
    new_linkage = dict(
        id=uuid.uuid4(),
        name='new_linkage',
        head_angle=63.5,
        front_stroke=180,
        rear_stroke=65,
        data=''
    )
    new_setup = dict(
        id=uuid.uuid4(),
        name='new_setup',
        linkage_id=DB_IDS['linkage'],
        front_calibration_id=DB_IDS['front_calibration'],
        rear_calibration_id=DB_IDS['rear_calibration']
    )
    new_track = dict(
        id=uuid.uuid4(),
        track=''
    )
    new_board = dict(
        id='xxxxxxxxxxxxxxxx',
        setup_id=DB_IDS['setup']
    )

    return dict(
        calibration=new_calibration,
        linkage=new_linkage,
        setup=new_setup,
        track=new_track,
        board=new_board
    )


def _add_test_data():
    e = _create_test_entities()
    calibration = dfd(Calibration, e['calibration'])
    linkage = dfd(Linkage, e['linkage'])
    setup = dfd(Setup, e['setup'])
    board = dfd(Board, e['board'])

    db.session.add(calibration)
    db.session.add(linkage)
    db.session.add(setup)
    db.session.add(board)
    db.session.commit()

    return (
        str(calibration.id),
        str(linkage.id),
        str(setup.id),
        str(board.id),
    )


def test_pull(client, auth):
    auth.login()

    response = client.get('/api/sync/pull')
    assert response.status_code == status.OK

    assert 'board' in response.json
    assert len(response.json['board']) == 1
    assert response.json['board'][0]['id'] == str(DB_IDS['board'])

    assert 'calibration_method' in response.json
    assert len(response.json['calibration_method']) == 5
    cm_ids = [cm['id'] for cm in response.json['calibration_method']]
    assert str(DB_IDS['calibration_method_fraction']) in cm_ids

    assert 'calibration' in response.json
    assert len(response.json['calibration']) == 2
    c_ids = [c['id'] for c in response.json['calibration']]
    assert str(DB_IDS['front_calibration']) in c_ids
    assert str(DB_IDS['rear_calibration']) in c_ids

    assert 'linkage' in response.json
    assert len(response.json['linkage']) == 1
    assert response.json['linkage'][0]['id'] == str(DB_IDS['linkage'])

    assert 'setup' in response.json
    assert len(response.json['setup']) == 1
    assert response.json['setup'][0]['id'] == str(DB_IDS['setup'])

    assert 'session' in response.json
    assert len(response.json['session']) == 2
    s_ids = [s['id'] for s in response.json['session']]
    assert str(DB_IDS['session']) in s_ids
    assert str(DB_IDS['session2']) in s_ids


def test_pull_deleted_session(app, client, auth):
    auth.login()

    with app.app_context():
        CalibrationMethod.delete(DB_IDS['session'])

    response = client.get('/api/sync/pull')
    assert response.status_code == status.OK

    assert 'session' in response.json
    assert len(response.json['session']) == 2
    for s in response.json['session']:
        if s['id'] == DB_IDS['session']:
            assert 'psst_encoded' not in s
        else:
            assert 'psst_encoded' in s


def test_pull_since(app, client, auth):
    auth.login()

    time.sleep(1)
    timestamp = int(datetime.now().timestamp())
    time.sleep(1)
    with app.app_context():
        calibration_id, linkage_id, setup_id, board_id = (_add_test_data())
        CalibrationMethod.delete(DB_IDS['calibration_method_fraction'])

    response = client.get(f'/api/sync/pull?since={timestamp}')
    assert response.status_code == status.OK

    assert len(response.json['calibration_method']) == 1
    assert response.json['calibration_method'][0]['deleted']

    assert len(response.json['board']) == 1
    assert response.json['board'][0]['id'] == board_id

    assert len(response.json['calibration']) == 1
    assert response.json['calibration'][0]['id'] == calibration_id

    assert len(response.json['linkage']) == 1
    assert response.json['linkage'][0]['id'] == linkage_id

    assert len(response.json['setup']) == 1
    assert response.json['setup'][0]['id'] == setup_id


def test_pull_since_in_future(client, auth):
    auth.login()

    timestamp = int(datetime.now().timestamp()) + 13
    response = client.get(f'/api/sync/pull?since={timestamp}')
    assert response.status_code == status.OK
    assert len(response.json['board']) == 0
    assert len(response.json['calibration_method']) == 0
    assert len(response.json['calibration']) == 0
    assert len(response.json['linkage']) == 0
    assert len(response.json['setup']) == 0


def test_push_new(app, client, auth):
    auth.login()

    time.sleep(1)
    timestamp = int(datetime.now().timestamp())

    calibration1_id = uuid.uuid4()
    calibration1 = dict(
        id=calibration1_id,
        name='new_calibration',
        method_id=DB_IDS['calibration_method_isosceles'],
        inputs={'arm': 134.9375, 'max': 234.15625},
        updated=timestamp
    )

    response = client.put('/api/sync/push', json={
        'calibration': [calibration1]
    })
    assert response.status_code == status.NO_CONTENT
    with app.app_context():
        assert Calibration.get(calibration1_id)


def test_push_update(app, client, auth):
    auth.login()

    time.sleep(1)
    timestamp = int(datetime.now().timestamp())

    calibration1 = dict(
        id=DB_IDS['front_calibration'],
        name='updated front calibration',
        method_id=DB_IDS['calibration_method_isosceles'],
        inputs={'arm': 1337, 'max': 100},
        updated=timestamp
    )

    response = client.put('/api/sync/push', json={
        'calibration': [calibration1]
    })
    assert response.status_code == status.NO_CONTENT
    with app.app_context():
        c = Calibration.get(DB_IDS['front_calibration'])
        assert c.name == "updated front calibration"


def test_push_delete(app, client, auth):
    auth.login()

    time.sleep(1)
    timestamp = int(datetime.now().timestamp())

    calibration1 = dict(
        id=DB_IDS['front_calibration'],
        name='x',
        method_id=DB_IDS['calibration_method_isosceles'],
        inputs={'arm': 1337, 'max': 100},
        updated=timestamp,
        deleted=timestamp
    )

    response = client.put('/api/sync/push', json={
        'calibration': [calibration1]
    })
    assert response.status_code == status.NO_CONTENT
    with app.app_context():
        assert not Calibration.get(DB_IDS['front_calibration'])


def test_push_multiple_client_update(app, client, auth):
    auth.login()

    time.sleep(1)
    timestamp = int(datetime.now().timestamp())

    calibration1 = dict(
        id=DB_IDS['front_calibration'],
        name='client 1',
        method_id=DB_IDS['calibration_method_isosceles'],
        inputs={'arm': 1337, 'max': 100},
        updated=timestamp
    )
    calibration2 = dict(
        id=DB_IDS['front_calibration'],
        name='client 2',
        method_id=DB_IDS['calibration_method_isosceles'],
        inputs={'arm': 1337, 'max': 100},
        updated=timestamp+13
    )

    # client2 updated later, but pushes first
    response = client.put('/api/sync/push', json={
        'calibration': [calibration2]
    })
    assert response.status_code == status.NO_CONTENT

    # client1 updated first, but pushes later.
    response = client.put('/api/sync/push', json={
        'calibration': [calibration1]
    })
    assert response.status_code == status.NO_CONTENT

    with app.app_context():
        c = Calibration.get(DB_IDS['front_calibration'])
        # client2 updated later, so its change should remain
        # even though client1 syncs later
        assert c.name == "client 2"
