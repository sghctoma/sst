from flask import Blueprint

bp = Blueprint('setup', __name__)

from app.api.setup import routes
