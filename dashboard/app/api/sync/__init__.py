from flask import Blueprint

bp = Blueprint('sync', __name__)

from app.api.sync import routes
