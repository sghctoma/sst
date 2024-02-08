import pytest

from http import HTTPStatus as status


def test_login(client, auth):
    assert client.get('/').status_code == status.OK

    response = auth.login()
    assert b'refresh_token' in response.data
    assert b'access_token' in response.data


@pytest.mark.parametrize(
    ('username', 'password', 'message'),
    (
        ('a', 'test', b'Wrong username or password'),
        ('test', 'a', b'Wrong username or password')
    ),
)
def test_login_validate_input(auth, username, password, message):
    response = auth.login(username, password)
    assert message in response.data


def test_refresh(client, auth):
    response = auth.login()
    response = client.post('/auth/refresh', headers={
        'Authorization': f"Bearer {response.json['refresh_token']}"
    })
    assert b'refresh_token' in response.data
    assert b'access_token' in response.data


def test_pwchange(client, auth):
    auth.login()
    response = client.patch('/auth/pwchange', json={
        'old_password': 'test', 'new_password': 'newpassword'
    })
    assert response.status_code == status.NO_CONTENT


@pytest.mark.parametrize(
    ('old', 'new', 'status'),
    (
        ('test', 'xxxx', status.BAD_REQUEST),
        ('xxxx', 'xxxx', status.FORBIDDEN),
    )
)
def test_pwchange_validate_input(client, auth, old, new, status):
    auth.login()
    response = client.patch('/auth/pwchange', json={
        'old_password': old, 'new_password': new
    })
    assert response.status_code == status


def test_logout(client, auth):
    auth.login()
    response = client.delete('/auth/logout')
    assert b'logout successful' in response.data
