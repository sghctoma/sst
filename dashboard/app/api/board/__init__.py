from flask import Blueprint

bp = Blueprint('board', __name__)

from app.api.board import routes
