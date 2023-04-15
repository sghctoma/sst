from flask import Blueprint

bp = Blueprint('linkage', __name__)

from app.api.linkage import routes
