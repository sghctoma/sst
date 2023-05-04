from flask import Blueprint


bp = Blueprint('api', __name__)

from app.api.board import bp as board_bp
bp.register_blueprint(board_bp, url_prefix='/board')

from app.api.calibration import bp as calibration_bp
bp.register_blueprint(calibration_bp, url_prefix='/calibration')

from app.api.calibration_method import bp as calibration_method_bp
bp.register_blueprint(calibration_method_bp, url_prefix='/calibration-method')

from app.api.linkage import bp as linkage_bp
bp.register_blueprint(linkage_bp, url_prefix='/linkage')

from app.api.session import bp as session_bp
bp.register_blueprint(session_bp, url_prefix='/session')

from app.api.setup import bp as setup_bp
bp.register_blueprint(setup_bp, url_prefix='/setup')

from app.api.track import bp as track_bp
bp.register_blueprint(track_bp, url_prefix='/track')
