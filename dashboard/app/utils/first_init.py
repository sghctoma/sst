from os import path

from urllib.parse import urlparse

from flask import current_app
from flask_migrate import (
    current as db_current,
    stamp as db_stamp,
    upgrade as db_upgrade,
)

from app.extensions import db
from app.models.calibration import CalibrationMethod
from app.models.user import User


def _generate_rsa_keys(priv_file: str, pub_file: str):
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives import serialization

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_key = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    ).decode('utf-8')
    public_key = key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode('utf-8')

    open(priv_file, 'w').write(private_key)
    open(pub_file, 'w').write(public_key)


def _initiate_database():
    db_upgrade()
    cm_fraction = CalibrationMethod(
        id=1,
        name="fraction",
        description="Sample is in fraction of maximum suspension stroke.",
        properties=dict(
            inputs=[],
            intermediates={},
            expression='sample * MAX_STROKE',
        )
    )
    cm_percentage = CalibrationMethod(
        id=2,
        name="percentage",
        description="Sample is in percentage of maximum suspension stroke.",
        properties=dict(
            inputs=[],
            intermediates=dict(factor='MAX_STROKE / 100.0'),
            expression='sample * factor',
        )
    )
    cm_linear = CalibrationMethod(
        id=3,
        name="linear",
        description="Sample is linearly distributed within a given range.",
        properties=dict(
            inputs=['min_measurement', 'max_measurement'],
            intermediates=dict(
                factor="MAX_STROKE / (max_measurement - min_measurement)",
            ),
            expression='(sample - min_measurement) * factor',
        )
    )
    cm_as5600_isosceles_triangle = CalibrationMethod(
        id=4,
        name="as5600-isosceles-triangle",
        description="Triangle setup with the sensor between the base and leg",
        properties=dict(
            inputs=['arm', 'max'],
            intermediates=dict(
                start_angle='acos(max / 2.0 / arm)',
                factor='2.0 * pi / 4096',
                dbl_arm='2.0 * arm',
            ),
            expression='max - (dbl_arm * cos((factor*sample) + start_angle))',
        )
    )
    cm_as5600_triangle = CalibrationMethod(
        id=5,
        name="as5600-triangle",
        description="Triangle setup with the sensor between two known sides",
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
    db.session.add(cm_fraction)
    db.session.add(cm_percentage)
    db.session.add(cm_linear)
    db.session.add(cm_as5600_isosceles_triangle)
    db.session.add(cm_as5600_triangle)

    import random
    import string
    from argon2 import PasswordHasher
    user = User(id=1, username="admin")
    charset = string.ascii_letters + string.digits
    password = ''.join(random.choices(charset, k=26))
    ph = PasswordHasher()
    user.hash = ph.hash(password)
    current_app.logger.info(f"GENERATED INITIAL ACCOUNT: admin:{password}")
    db.session.add(user)

    db.session.commit()


def first_init():
    if not path.isfile(current_app.config['JWT_PRIVATE_KEY_FILE']):
        _generate_rsa_keys(current_app.config['JWT_PRIVATE_KEY_FILE'],
                           current_app.config['JWT_PUBLIC_KEY_FILE'])
    sqlite_uri = current_app.config['SQLALCHEMY_DATABASE_URI']
    if not path.isfile(urlparse(sqlite_uri).path):
        _initiate_database()
    elif db_current() is None:
        '''
        Flask-Migrate was introduced after version v0.2.0-alpha, and the first
        migration was created when the token_blocklist table was added. This
        was a mistake, since a "flask db upgrade" creates only that table when
        run on an empty database. So the original migrations directory was
        scrapped and recreated with an initial migration with all the tables
        in version v0.2.0-alpha, and another one with token_blocklist. Existing
        v0.2.0-alpha databases do not have a revision yet (no alembic_version
        table), so in order for them to work nicely, we need to stamp them to
        the initial migration revision.
        '''
        db_stamp(revision='ea6262808b9d')
        db_upgrade()
