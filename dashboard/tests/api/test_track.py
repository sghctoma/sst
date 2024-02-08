import uuid

import pytest

from http import HTTPStatus as status

from conftest import DB_IDS


def test_get_all(client):
    response = client.get('/api/track')
    ids = [c['id'] for c in response.json]
    assert str(DB_IDS['track']) in ids


def test_get(client):
    id = str(DB_IDS['track'])
    response = client.get(f'/api/track/{id}')
    assert id == response.json['id']


def test_get_nonexistent(client):
    response = client.get(f'/api/track/{DB_IDS["nonexistent"]}')
    assert response.status_code == status.NOT_FOUND


def test_get_invalid_uuid(client):
    with pytest.raises(ValueError) as e:
        client.get('/api/track/xxxx')
    assert "badly formed" in str(e.value)


def test_put(client, auth):
    auth.login()

    id = uuid.uuid4()
    t_json = dict(
        id=id,
        track='{"lat": [6015517], "lon": [2095432], "ele": [0], "time": [0]}',
    )
    response = client.put('/api/track', json=t_json)
    assert response.status_code == status.CREATED

    response = client.get(f'/api/track/{id}')
    assert response.json['id'] == str(id)


@pytest.mark.parametrize(
    ('data'),
    (
        ('{"lat": [], "lon": [], "ele": [], "time": []}'),
        ('{"lat": [0], "lon": [0], "ele": [0, 1], "time": [0]}'),
        ('{"lat": [0], "lon": [0], "ele": [0]             }'),
        ('{"lat": [0], "lon": [0],             "time": [0]}'),
        ('{"lat": [0],             "ele": [0], "time": [0]}'),
        ('{            "lon": [0], "ele": [0], "time": [0]}'),
    )
)
def test_put_invalid_data(client, auth, data):
    auth.login()

    t_json = dict(
        id=uuid.uuid4(),
        track=data,
    )
    response = client.put('/api/track', json=t_json)
    assert response.status_code == status.BAD_REQUEST


def test_delete(client, auth):
    auth.login()

    client.delete(f'/api/track/{DB_IDS["track"]}')
    response = client.get(f'/api/track/{DB_IDS["track"]}')
    assert response.status_code == status.NOT_FOUND
