import uuid

import pytest

from http import HTTPStatus as status

from conftest import DB_IDS


def test_get_all(client):
    response = client.get('/api/calibration-method')
    ids = [c['id'] for c in response.json]
    assert str(DB_IDS['calibration_method_fraction']) in ids


def test_get(client):
    id = str(DB_IDS['calibration_method_fraction'])
    response = client.get(f'/api/calibration-method/{id}')
    assert id == response.json['id']


def test_get_nonexistent(client):
    response = client.get(f'/api/calibration-method/{DB_IDS["nonexistent"]}')
    assert response.status_code == status.NOT_FOUND


def test_get_invalid_uuid(client):
    with pytest.raises(ValueError) as e:
        client.get('/api/calibration-method/xxxx')
    assert "badly formed" in str(e.value)


def test_put(client, auth):
    auth.login()

    id = uuid.uuid4()
    cm_json = dict(
        id=id,
        name="test",
        description="test",
        properties=dict(
            inputs=['arm1', 'arm2', 'max'],
            intermediates=dict(
                start_angle='acos((arm1**2+arm2**2-max**2)/(2*arm1*arm2))',
                factor='2.0 * pi / 4096',
                arms_sqr_sum='arm1**2 + arm2**2',
                dbl_arm1_arm2='2 * arm1 * arm2',

            ),
            expression='max - sqrt(arms_sqr_sum - dbl_arm1_arm2 * '
            'cos(start_angle-(factor*sample)))',
        )
    )
    response = client.put('/api/calibration-method', json=cm_json)
    assert response.status_code == status.CREATED

    response = client.get(f'/api/calibration-method/{id}')
    assert response.json['id'] == str(id)


def test_put_invalid_expression(client, auth):
    auth.login()

    cm_json = dict(
        id=uuid.uuid4(),
        name="test",
        description="test",
        properties=dict(
            inputs=[],
            intermediates={},
            expression='xxxx',
        )
    )
    response = client.put('/api/calibration-method', json=cm_json)
    assert response.status_code == status.BAD_REQUEST


def test_delete(client, auth):
    auth.login()

    id = DB_IDS['calibration_method_fraction']
    client.delete(f'/api/calibration-method/{id}')
    response = client.get(f'/api/calibration-method/{id}')
    assert response.status_code == status.NOT_FOUND
