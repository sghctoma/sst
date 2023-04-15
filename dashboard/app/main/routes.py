from flask import (
    jsonify,
    render_template,
    request
)
from flask_jwt_extended import (
    current_user,
    get_jwt_identity,
    jwt_required
)
from app.main import bp


@bp.route('/')
def index():
    return render_template('index.html')
