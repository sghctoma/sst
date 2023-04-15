from flask import Blueprint

bp = Blueprint('calibration', __name__)

from app.api.calibration import routes
