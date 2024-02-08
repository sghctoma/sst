import uuid

import pytest

from http import HTTPStatus as status

from conftest import DB_IDS


def test_get_all(client):
    response = client.get('/api/linkage')
    ids = [c['id'] for c in response.json]
    assert str(DB_IDS['linkage']) in ids


def test_get(client):
    id = str(DB_IDS['linkage'])
    response = client.get(f'/api/linkage/{id}')
    assert id == response.json['id']


def test_get_nonexistent(client):
    response = client.get(f'/api/linkage/{DB_IDS["nonexistent"]}')
    assert response.status_code == status.NOT_FOUND


def test_get_invalid_uuid(client):
    with pytest.raises(ValueError) as e:
        client.get('/api/linkage/xxxx')
    assert "badly formed" in str(e.value)


@pytest.mark.parametrize(
    ('data'),
    (
        ('Wheel_T;Leverage_R\n0;2.5\n180;3'),
        ('Wheel_T;Shock_T\n0;0\n180;65'),
    )
)
def test_put(client, auth, data):
    auth.login()

    id = uuid.uuid4()
    l_json = dict(
        id=id,
        name='test_linkage',
        head_angle=63.5,
        front_stroke=180,
        rear_stroke=65,
        data=data,
    )
    response = client.put('/api/linkage', json=l_json)
    assert response.status_code == status.CREATED

    response = client.get(f'/api/linkage/{id}')
    assert response.json['id'] == str(id)


@pytest.mark.parametrize(
    ('data'),
    (
        ('Wheel_T;Shock_T\n0;0\n180;'),
        ('xxxx;Shock_T\n0;0\n180;65'),
        ('Wheel_T;xxxx\n0;0\n180;65'),
    )
)
def test_put_validate_input(client, auth, data):
    auth.login()

    l_json = dict(
        id=uuid.uuid4(),
        name='test_linkage',
        head_angle=63.5,
        front_stroke=180,
        rear_stroke=65,
        data=data,
    )
    response = client.put('/api/linkage', json=l_json)
    assert response.status_code == status.BAD_REQUEST


def test_delete(client, auth):
    auth.login()

    client.delete(f'/api/linkage/{DB_IDS["linkage"]}')
    response = client.get(f'/api/linkage/{DB_IDS["linkage"]}')
    assert response.status_code == status.NOT_FOUND
