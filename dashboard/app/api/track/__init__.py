from flask import Blueprint

bp = Blueprint('track', __name__)

from app.api.track import routes
