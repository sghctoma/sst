from datetime import timedelta
from flask import Flask
from app.extensions import db, jwt


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
    app.config.from_prefixed_env()

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

    return app
