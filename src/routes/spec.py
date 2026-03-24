from flask import Blueprint, jsonify
from pathlib import Path
import yaml

spec_bp = Blueprint('spec', __name__, url_prefix='/api')

@spec_bp.route('/openapi.json')
def serve_spec():
    """Serve OpenAPI specification as JSON"""
    spec_path = Path(__file__).parent.parent.parent / 'static' / 'openapi.yaml'
    with open(spec_path) as f:
        spec_data = yaml.safe_load(f)
    return jsonify(spec_data)
