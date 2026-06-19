import json

from fastapi.testclient import TestClient

import backend.routes.benchmark_dashboard_routes as benchmark_routes
from backend.evidence.integrity import attach_integrity_manifest
from backend.main import app


client = TestClient(app)


