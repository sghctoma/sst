import uuid

import pytest

from http import HTTPStatus as status

from conftest import DB_IDS


lnk_json = dict(
    id=uuid.uuid4(),
    name='test_linkage',
    head_angle=63.5,
    front_stroke=180,
    rear_stroke=65,
    data='Wheel_T;Leverage_R\n0;2.5\n180;3',
)

fcal_json = dict(
    id=uuid.uuid4(),
    name='test',
    method_id=uuid.UUID('12f4a1b922f74524abcbdaa99a5c1c3a'),
    inputs={'arm': 134.9375, 'max': 234.15625}
)

rcal_json = dict(
    id=uuid.uuid4(),
    name='test',
    method_id=uuid.UUID('12f4a1b922f74524abcbdaa99a5c1c3a'),
    inputs={'arm': 134.9375, 'max': 234.15625}
)

board_json = dict(
    id='test',
    setup_id=None,
)


def test_get_all(client):
    response = client.get('/api/setup')
    ids = [c['id'] for c in response.json]
    assert str(DB_IDS['setup']) in ids


def test_get(client):
    id = str(DB_IDS['setup'])
    response = client.get(f'/api/setup/{id}')
    assert id == response.json['id']


def test_get_nonexistent(client):
    response = client.get(f'/api/setup/{DB_IDS["nonexistent"]}')
    assert response.status_code == status.NOT_FOUND


def test_get_invalid_uuid(client):
    with pytest.raises(ValueError) as e:
        client.get('/api/setup/xxxx')
    assert "badly formed" in str(e.value)


def test_put(client, auth):
    auth.login()

    id = uuid.uuid4()
    s_json = dict(
        id=id,
        name='test',
        linkage_id=DB_IDS['linkage'],
        front_calibration_id=DB_IDS['front_calibration'],
        rear_calibration_id=DB_IDS['rear_calibration']
    )
    response = client.put('/api/setup', json=s_json)
    assert response.status_code == status.CREATED

    response = client.get(f'/api/setup/{id}')
    assert response.json['id'] == str(id)


@pytest.mark.parametrize(
    ('linkage', 'front_calibration', 'rear_calibration'),
    (
        (None, DB_IDS['front_calibration'], DB_IDS['rear_calibration']),
        (DB_IDS['linkage'], None, None),
    )
)
def test_put_invalid_data(client, auth, linkage,
                          front_calibration, rear_calibration):
    auth.login()

    s_json = dict(
        id=uuid.uuid4(),
        name='test',
        linkage_id=linkage,
        front_calibration_id=front_calibration,
        rear_calibration_id=rear_calibration
    )
    response = client.put('/api/setup', json=s_json)
    assert response.status_code == status.BAD_REQUEST


@pytest.mark.parametrize(
    ('board', 'linkage'),
    (
        (board_json, lnk_json),
        (None, lnk_json),
        (None, DB_IDS['linkage'])
    )
)
def test_put_combined(client, auth, board, linkage):
    auth.login()

    setup_json = dict(
        name="test_setup",
        linkage=linkage,
        front_calibration=fcal_json,
        rear_calibration=rcal_json,
        board=board,
    )
    response = client.put('/api/setup/combined', json=setup_json)
    assert response.status_code == status.CREATED

    id = response.json['id']

    response = client.get(f'/api/setup/{id}')
    assert response.json['id'] == str(id)


@pytest.mark.parametrize(
    ('linkage', 'front_calibration', 'rear_calibration', 'message'),
    (
        (None, fcal_json, rcal_json, "Invalid data for linkage!"),
        (lnk_json, None, None, "No calibration given"),
    )
)
def test_put_combined_invalid_input(client, auth, linkage, front_calibration,
                                    rear_calibration, message):
    auth.login()

    setup_json = dict(
        name="test_setup",
        linkage=linkage,
        front_calibration=front_calibration,
        rear_calibration=rear_calibration,
        board=board_json,
    )
    response = client.put('/api/setup/combined', json=setup_json)
    assert response.status_code == status.BAD_REQUEST
    assert response.json['msg'] == message


def test_delete(client, auth):
    auth.login()

    client.delete(f'/api/setup/{DB_IDS["setup"]}')
    response = client.get(f'/api/setup/{DB_IDS["setup"]}')
    assert response.status_code == status.NOT_FOUND
