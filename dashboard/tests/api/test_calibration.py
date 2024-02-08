import uuid

import pytest

from http import HTTPStatus as status

from conftest import DB_IDS


def test_get_all(client):
    response = client.get('/api/calibration')
    ids = [c['id'] for c in response.json]
    assert str(DB_IDS['front_calibration']) in ids
    assert str(DB_IDS['rear_calibration']) in ids


def test_get(client):
    id = str(DB_IDS['front_calibration'])
    response = client.get(f'/api/calibration/{id}')
    assert id == response.json['id']


def test_get_nonexistent(client):
    response = client.get(f'/api/calibration/{DB_IDS["nonexistent"]}')
    assert response.status_code == status.NOT_FOUND


def test_get_invalid_uuid(client):
    with pytest.raises(ValueError) as e:
        client.get('/api/calibration/xxxx')
    assert "badly formed" in str(e.value)


def test_put(client, auth):
    auth.login()

    id = uuid.uuid4()
    c_json = dict(
        id=id,
        name='test',
        method_id=uuid.UUID('12f4a1b922f74524abcbdaa99a5c1c3a'),
        inputs={'arm': 134.9375, 'max': 234.15625}
    )
    response = client.put('/api/calibration', json=c_json)
    assert response.status_code == status.CREATED

    response = client.get(f'/api/calibration/{id}')
    assert response.json['id'] == str(id)


def test_put_invalid_data(client, auth):
    auth.login()

    c_json = dict(
        id=uuid.uuid4(),
        name='test',
        method_id=uuid.UUID('12f4a1b922f74524abcbdaa99a5c1c3a'),
        inputs={'arm': 100.0}
    )
    response = client.put('/api/calibration', json=c_json)
    assert response.status_code == status.BAD_REQUEST


def test_delete(client, auth):
    auth.login()

    client.delete(f'/api/calibration/{DB_IDS["front_calibration"]}')
    response = client.get(f'/api/calibration/{DB_IDS["front_calibration"]}')
    assert response.status_code == status.NOT_FOUND
