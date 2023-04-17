import queue
import threading

from http import HTTPStatus as status
from datetime import timedelta

from flask import jsonify, Flask
from werkzeug.exceptions import HTTPException

from app.extensions import db, jwt
from app.telemetry.session_html import create_cache


id_queue = queue.Queue()


def create_app():
    app = Flask(__name__)
    app.config['JWT_SECRET_KEY'] = 'super-secret'
    app.config['JWT_ALGORITHM'] = 'HS256'
    app.config['JWT_PRIVATE_KEY'] = None
    app.config['JWT_PUBLIC_KEY'] = None
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(minutes=10)
    app.config['JWT_REFRESH_TOKEN_EXPIRES'] = timedelta(hours=8)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////data/gosst.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['GOSST_HOST'] = 'localhost'
    app.config['GOSST_PORT'] = 557
    app.config.from_prefixed_env()

    @app.errorhandler(HTTPException)
    def handle_exception(e):
        return jsonify(status=e.code, msg=e.name), status.INTERNAL_SERVER_ERROR

    # Initialize Flask extensions here
    db.init_app(app)
    jwt.init_app(app)

    # Register blueprints here
    from app.main import bp as main_bp
    app.register_blueprint(main_bp)

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
