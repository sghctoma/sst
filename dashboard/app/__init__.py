import logging
import queue
import threading
import sys

import click

from http import HTTPStatus as status
from datetime import datetime, timedelta, timezone

from flask import jsonify, Flask
from flask_jwt_extended import (
    create_access_token,
    get_jwt,
    set_access_cookies,
    get_current_user
)
from werkzeug.exceptions import HTTPException

from app.extensions import db, jwt, migrate, sio
from app.telemetry.session_html import create_cache
from app.utils.first_init import first_init
from app.utils.converters import UuidConverter


id_queue = queue.Queue()


def _sqlite_pragmas(app: Flask):
    if 'sqlite' in app.config['SQLALCHEMY_DATABASE_URI']:
        def _pragma_on_connect(dbapi_con, con_record):
            dbapi_con.execute('PRAGMA journal_mode=WAL')

        with app.app_context():
            from sqlalchemy import event
            event.listen(db.engine, 'connect', _pragma_on_connect)


def create_app(test_config=None):
    app = Flask(__name__)
    app.config['JWT_TOKEN_LOCATION'] = ['cookies', 'headers']
    app.config['JWT_ALGORITHM'] = 'RS256'
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=1)
    app.config['JWT_REFRESH_TOKEN_EXPIRES'] = timedelta(days=30)
    app.config['JWT_COOKIE_SECURE'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////data/gosst.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['GOSST_HTTP_API'] = 'http://localhost:8080'

    if test_config:
        app.config.update(test_config)
    else:
        app.config.from_prefixed_env()

    app.logger.addHandler(logging.StreamHandler(sys.stdout))
    app.logger.setLevel(logging.INFO)

    app.url_map.converters['uuid'] = UuidConverter

    ctx = click.get_current_context(silent=True)
    if not ctx:
        app.config['JWT_PRIVATE_KEY'] = open(
            app.config['JWT_PRIVATE_KEY_FILE']).read()
        app.config['JWT_PUBLIC_KEY'] = open(
            app.config['JWT_PUBLIC_KEY_FILE']).read()

    @app.cli.command("init")
    def init_command():
        first_init()

    @app.after_request
    def refresh_expiring_jwts(response):
        try:
            exp_timestamp = get_jwt()["exp"]
            now = datetime.now(timezone.utc)
            target_timestamp = datetime.timestamp(now + timedelta(minutes=10))
            if target_timestamp > exp_timestamp:
                access_token = create_access_token(identity=get_current_user())
                set_access_cookies(response, access_token)
            return response
        except (RuntimeError, KeyError):
            # If there is not a valid JWT, just return the original response
            return response

    @app.errorhandler(HTTPException)
    def handle_exception(e):
        return jsonify(status=e.code, msg=e.name), status.INTERNAL_SERVER_ERROR

    # Initialize Flask extensions here
    jwt.init_app(app)
    sio.init_app(app)

    db.init_app(app)
    _sqlite_pragmas(app)
    migrate.init_app(app, db)

    # Register blueprints here
    from app.frontend import bp as frontend_bp
    app.register_blueprint(frontend_bp)

    from app.auth import bp as auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')

    from app.api import bp as api_bp
    app.register_blueprint(api_bp, url_prefix='/api')

    def html_generator():
        with app.app_context():
            app.logger.info("Bokeh HTML generator thread started")
            while True:
                try:
                    id = id_queue.get()
                    app.logger.info(f"generating cache for session {id}")
                    create_cache(id, 5, 200)
                    sio.emit("session_ready")
                    app.logger.info(f"cache ready for session {id}")
                except BaseException as e:
                    app.logger.error(f"cache failed for session {id}: {e}")

    generator_thread = threading.Thread(target=html_generator)
    generator_thread.daemon = True
    generator_thread.start()

    return app
