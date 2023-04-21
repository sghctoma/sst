from flask import Blueprint

bp = Blueprint('frontend', __name__)

from app.frontend import routes
