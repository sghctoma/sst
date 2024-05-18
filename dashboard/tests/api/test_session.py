import base64
import hashlib
import uuid

import pytest

from flask import current_app
from http import HTTPStatus as status

from app.extensions import db
from app.models.session import Session
from conftest import DB_IDS, session_data, track_gpx


def test_get_all(client):
    response = client.get('/api/session')
    ids = [c['id'] for c in response.json]
    assert str(DB_IDS['session']) in ids


def test_get_incomplete(app, client):
    with app.app_context():
        session = Session.get(DB_IDS['session'])
        session.data = None
        db.session.commit()
    response = client.get('/api/session/incomplete')
    assert str(DB_IDS['session']) in response.json


def test_get_psst(client):
    id = str(DB_IDS['session'])
    response = client.get(f'/api/session/{id}/psst')
    session_data_hash = hashlib.sha256(session_data).digest().hex()
    assert hashlib.sha256(response.data).digest().hex() == session_data_hash


def test_get_psst_nonexistent(client):
    response = client.get(f'/api/session/{DB_IDS["nonexistent"]}/psst')
    assert response.status_code == status.NOT_FOUND


def test_get_last(client):
    id = str(DB_IDS['session_html'])
    response = client.get('/api/session/last')
    assert id == response.json['id']


def test_get_psst_invalid_uuid(client):
    with pytest.raises(ValueError) as e:
        client.get('/api/session/xxxx/psst')
    assert "badly formed" in str(e.value)


def test_get(client):
    id = str(DB_IDS['session'])
    response = client.get(f'/api/session/{id}')
    assert id == response.json['id']


def test_get_invalid_uuid(client):
    with pytest.raises(ValueError) as e:
        client.get('/api/session/xxxx')
    assert "badly formed" in str(e.value)


def test_get_nonexistent(client):
    response = client.get(f'/api/session/{DB_IDS["nonexistent"]}')
    assert response.status_code == status.NOT_FOUND


def test_filter(client):
    id = str(DB_IDS['session'])
    start = 10
    end = 13
    response = client.get(
        f'/api/session/{id}/filter?start={start}&end={end}')
    assert (hashlib.sha256(response.data).digest().hex() ==
            'e68e4aec59b75367578bd7045e43d2914f0b5152b7a09794ee4f87de08d16124')


@pytest.mark.parametrize(
    ('start', 'end'),
    (
        (-13, 13),
        (0, 1337),
        (13, 0),
    )
)
def test_filter_invalid_input(client, start, end):
    id = str(DB_IDS['session'])
    response = client.get(
        f'/api/session/{id}/filter?start={start}&end={end}')
    assert (hashlib.sha256(response.data).digest().hex() ==
            '83a1412a9a8c0f7b97b15121c6c33eedca0e89babe2312d65739d79c7c23d9c7')


def test_delete(client, auth):
    auth.login()

    client.delete(f'/api/session/{DB_IDS["session_html"]}')
    response = client.get(f'/api/session/{DB_IDS["session_html"]}')
    assert response.status_code == status.NOT_FOUND


def test_put(app, client, auth, requests_mock):
    auth.login()

    with app.app_context():
        api_server = current_app.config['GOSST_HTTP_API']
    url = f'{api_server}/api/internal/session'
    id = str(uuid.uuid4())
    requests_mock.put(url, json={'id': id}, status_code=status.CREATED)

    response = client.put('/api/session', json={"id": "dummy"})
    assert response.status_code == status.CREATED
    assert response.json['id'] == id


def test_put_invalid_data(app, client, auth, requests_mock):
    auth.login()

    with app.app_context():
        api_server = current_app.config['GOSST_HTTP_API']
    url = f'{api_server}/api/internal/session'
    id = str(uuid.uuid4())
    requests_mock.put(url, json={'id': id}, status_code=status.BAD_REQUEST)

    response = client.put('/api/session', json={"id": "dummy"})
    assert response.status_code == status.BAD_REQUEST


def test_put_normalized(app, client, auth, requests_mock):
    auth.login()

    with app.app_context():
        api_server = current_app.config['GOSST_HTTP_API']
    url = f'{api_server}/api/internal/session/normalized'
    id = str(uuid.uuid4())
    requests_mock.put(url, json={'id': id}, status_code=status.CREATED)

    response = client.put('/api/session/normalized', json={"id": "dummy"})
    assert response.status_code == status.CREATED
    assert response.json['id'] == id


def test_put_normalized_invalid_data(app, client, auth, requests_mock):
    auth.login()

    with app.app_context():
        api_server = current_app.config['GOSST_HTTP_API']
    url = f'{api_server}/api/internal/session'
    id = str(uuid.uuid4())
    requests_mock.put(url, json={'id': id}, status_code=status.BAD_REQUEST)

    response = client.put('/api/session', json={"id": "dummy"})
    assert response.status_code == status.BAD_REQUEST


def test_put_processed(client, auth):
    auth.login()

    id = str(uuid.uuid4())
    s_json = dict(
        id=id,
        name="test_session",
        description="session description",
        setup=DB_IDS['setup'],
        track=DB_IDS['track'],
        timestamp=1683457678,
        data=base64.b64encode(session_data).decode('utf-8'),
    )
    response = client.put('/api/session/psst', json=s_json)
    assert response.status_code == status.CREATED
    assert response.json['id'] == id


def test_put_processed_invalid_data(client, auth):
    auth.login()

    id = str(uuid.uuid4())
    s_json = dict(
        id=id,
        name="test_session",
        description="session description",
        setup=DB_IDS['setup'],
        track=DB_IDS['track'],
        timestamp=1683457678,
        data=base64.b64encode(b'test').decode('utf-8'),
    )
    response = client.put('/api/session/psst', json=s_json)
    assert response.status_code == status.BAD_REQUEST


def test_patch(auth, client):
    auth.login()

    patch_json = {'name': 'new_name', 'desc': 'new_description'}
    client.patch(f'/api/session/{DB_IDS["session"]}', json=patch_json)
    response = client.get(f'/api/session/{DB_IDS["session"]}')
    assert response.json['name'] == 'new_name'
    assert response.json['description'] == 'new_description'


def test_patch_psst(auth, client):
    auth.login()

    # get the original session
    response = client.get(f'/api/session/{DB_IDS["session"]}')
    session = response.json

    # check if patching really changes the 'data' field
    client.patch(f'/api/session/{DB_IDS["session"]}/psst', data='XXXX')
    response = client.get(f'/api/session/{DB_IDS["session"]}/psst')
    assert response.data == b'XXXX'

    # check if any other fields are unchanged
    response = client.get(f'/api/session/{DB_IDS["session"]}')
    new_session = response.json
    assert session == new_session


@pytest.mark.parametrize(
    ('id', 'message'),
    (
        (DB_IDS['session'], None),
        (DB_IDS['nonexistent'], b'does not exist'),
        (DB_IDS['session_html'], b'already generated'),
    )
)
def test_generate_bokeh(client, id, message):
    response = client.put(f'/api/session/{id}/bokeh')
    assert (response.status_code == status.NO_CONTENT or
            message in response.data)


@pytest.mark.parametrize(
    ('id', 'status'),
    (
        (DB_IDS['nonexistent'], status.NOT_FOUND),
        (DB_IDS['session'], status.NOT_FOUND),
        (DB_IDS['session_html'], status.OK),
    )
)
def test_session_html(client, auth, id, status):
    auth.login()

    response = client.get(f'/api/session/{id}/bokeh')
    assert response.status_code == status


def test_session_html_last(client, auth):
    auth.login()

    response = client.get('/api/session/last/bokeh')
    assert response.status_code == status.OK
    assert response.json['id'] == str(DB_IDS['session_html'])


def test_upload_gpx(client, auth):
    auth.login()

    id = DB_IDS['session_html']
    response = client.put(f'/api/session/{id}/gpx', data=track_gpx)
    assert response.status_code == status.OK
    assert hashlib.sha256(response.data).digest().hex() == (
        'acc6781678324e4b6dc52b8c7e76634f5d42276afb79612380d519f92aa26c04')


@pytest.mark.parametrize(
    ('id', 'status'),
    (
        (DB_IDS['nonexistent'], status.NOT_FOUND),
        (DB_IDS['session'], status.BAD_REQUEST),
    )
)
def test_upload_gpx_input_validation(client, auth, id, status):
    auth.login()

    response = client.put(f'/api/session/{id}/gpx', data=track_gpx)
    assert response.status_code == status
