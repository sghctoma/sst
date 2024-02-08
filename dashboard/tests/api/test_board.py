import pytest

from http import HTTPStatus as status

from conftest import DB_IDS


def test_get_all(client, auth):
    auth.login()
    response = client.get('/api/board')
    assert DB_IDS['board'] == response.json[0]['id']


def test_put(client, auth):
    auth.login()

    board_json = {'id': 'test', 'setup_id': None}
    response = client.put('/api/board', json=board_json)
    assert response.status_code == status.CREATED


def test_put_validate_setup_id(client, auth):
    auth.login()

    board_json = {'id': 'test', 'setup_id': 'test'}
    response = client.put('/api/board', json=board_json)
    assert response.status_code == status.BAD_REQUEST


def test_put_validate_id(client, auth):
    auth.login()

    board_json = {'setup_id': DB_IDS['setup']}
    with pytest.raises(BaseException) as e:
        client.put('/api/board', json=board_json)
    assert 'NOT NULL' in str(e.value)


def test_delete(client, auth):
    auth.login()

    client.delete(f'/api/board/{DB_IDS["board"]}')
    response = client.get('/api/board')
    assert len(response.json) == 0
