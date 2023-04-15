from flask import (
    jsonify,
    render_template,
    request
)
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    current_user,
    get_jwt_identity,
    jwt_required
)
from app.auth import bp
from app.extensions import db
from app.models.user import User


@bp.route('/')
def index():
    return render_template('index.html')


@bp.route('/login', methods=['POST'])
def login():
    username = request.json.get('username', None)
    password = request.json.get('password', None)

    user = db.session.execute(
        db.select(User).filter_by(username=username)).scalar_one_or_none()
    if not user or not user.check_password(password):
        return jsonify(msg="Wrong username or password"), 401

    access_token = create_access_token(identity=user)
    refresh_token = create_refresh_token(identity=user)
    return jsonify(access_token=access_token, refresh_token=refresh_token)


@bp.route("/refresh", methods=["POST"])
@jwt_required(refresh=True)
def refresh():
    identity = get_jwt_identity()
    access_token = create_access_token(identity=identity)
    return jsonify(access_token=access_token)


@bp.route("/user", methods=["GET"])
@jwt_required()
def protected():
    return jsonify(
        id=current_user.id,
        username=current_user.username,
    )
