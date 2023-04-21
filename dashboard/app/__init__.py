import queue
import threading

from http import HTTPStatus as status
from datetime import datetime, timedelta, timezone

from flask import jsonify, Flask
from flask_jwt_extended import (
    create_access_token,
    get_jwt,
    get_jwt_identity,
    set_access_cookies
)
from werkzeug.exceptions import HTTPException

from app.extensions import db, jwt
from app.telemetry.session_html import create_cache


id_queue = queue.Queue()


def create_app():
    app = Flask(__name__)
    app.config["JWT_TOKEN_LOCATION"] = ["cookies", "headers"]
    app.config['JWT_ALGORITHM'] = 'RS256'
    app.config['JWT_PRIVATE_KEY'] = open('rs256.pem').read()
    app.config['JWT_PUBLIC_KEY'] = open('rs256.pub').read()
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(minutes=20)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////data/gosst.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['GOSST_HOST'] = 'localhost'
    app.config['GOSST_PORT'] = 557
    app.config.from_prefixed_env()

    @app.after_request
    def refresh_expiring_jwts(response):
        try:
            exp_timestamp = get_jwt()["exp"]
            now = datetime.now(timezone.utc)
            target_timestamp = datetime.timestamp(now + timedelta(minutes=1.5))
            if target_timestamp > exp_timestamp:
                access_token = create_access_token(identity=get_jwt_identity())
                set_access_cookies(response, access_token)
            return response
        except (RuntimeError, KeyError):
            # If there is not a valid JWT, just return the original response
            return response

    @app.errorhandler(HTTPException)
    def handle_exception(e):
        return jsonify(status=e.code, msg=e.name), status.INTERNAL_SERVER_ERROR

    # Initialize Flask extensions here
    db.init_app(app)
    jwt.init_app(app)

    # Register blueprints here
    from app.frontend import bp as frontend_bp
    app.register_blueprint(frontend_bp)

    from app.auth import bp as auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')

    from app.api import bp as api_bp
    app.register_blueprint(api_bp, url_prefix='/api')

    def generator():
        with app.app_context():
            app.logger.info("Bokeh HTML generator thread started")
            while True:
                try:
                    id = id_queue.get()
                    app.logger.info(f"generating cache for session {id}")
                    create_cache(id, 5, 350)
                    app.logger.info(f"cache ready for session {id}")
                except BaseException as e:
                    app.logger.error(f"cache failed for session {id}: {e}")

    def start_generator():
        gt = threading.Thread(target=generator)
        gt.daemon = True
        gt.start()

    @app.before_first_request
    def beforefirst_request():
        start_generator()

    return app
