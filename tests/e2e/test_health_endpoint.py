"""End-to-end tests for health endpoint."""

import pytest
from fastapi.testclient import TestClient

from src.main import app


class TestHealthEndpoint:
    """Test health check endpoint."""

    def test_health_endpoint_returns_200(self, test_client):
        """Test GET /health returns 200."""
        response = test_client.get("/health")

        assert response.status_code == 200

    def test_health_endpoint_response_format(self, test_client):
        """Test health endpoint response format."""
        response = test_client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] == "ok"

    def test_health_endpoint_with_client(self):
        """Test health endpoint with explicit TestClient."""
        client = TestClient(app)
        response = client.get("/health")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
