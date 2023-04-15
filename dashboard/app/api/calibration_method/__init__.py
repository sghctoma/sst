from flask import Blueprint

bp = Blueprint('calibration_method', __name__)

from app.api.calibration_method import routes
