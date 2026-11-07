"""Register categories_bp once, without an additional /api prefix."""

from flask import Blueprint, jsonify
from ..categories import get_categories

categories_bp = Blueprint('categories', __name__)


@categories_bp.get('/api/categories')
def categories():
    return jsonify(data=get_categories())
