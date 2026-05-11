"""Shim re-exporting pool HTTP catalog helpers from ``app.pool.catalog``."""

from __future__ import annotations

from app.pool.catalog import (
    POOL_DESIGN_AND_INSTALLATION_SERVICE,
    POOL_SERVICES,
    SERVICES,
    api_get_service,
    api_list_services,
    get_service,
    get_service_by_slug,
    list_services,
    router,
)

__all__ = [
    "POOL_DESIGN_AND_INSTALLATION_SERVICE",
    "POOL_SERVICES",
    "SERVICES",
    "api_get_service",
    "api_list_services",
    "get_service",
    "get_service_by_slug",
    "list_services",
    "router",
]

from flask import Blueprint, request, jsonify

service_templates_bp = Blueprint('service_templates', __name__)

@service_templates_bp.route('/api/v1/service-templates', methods=['POST'])
def create_service_template():
    data = request.json
    template = {
        'name': data.get('name'),
        'pricing': data.get('pricing'),
        'duration': data.get('duration'),
        'checklist': data.get('checklist')
    }
    # Insert logic to save template to the database
    return jsonify({'status': 'success', 'template': template}), 201
