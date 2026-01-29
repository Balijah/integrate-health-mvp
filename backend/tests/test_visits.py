"""
Tests for visit endpoints.
"""

import pytest
from httpx import AsyncClient
from datetime import datetime


@pytest.mark.asyncio
class TestVisitEndpoints:
    """Tests for visit API endpoints."""

    async def test_create_visit_success(self, client: AsyncClient, auth_headers):
        """Test successful visit creation."""
        response = await client.post(
            "/api/v1/visits",
            headers=auth_headers,
            json={
                "patient_ref": "PT-NEW-001",
                "visit_date": "2024-01-15T14:00:00Z",
                "chief_complaint": "Fatigue for 2 weeks",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["patient_ref"] == "PT-NEW-001"
        assert data["chief_complaint"] == "Fatigue for 2 weeks"
        assert data["transcription_status"] == "pending"
        assert "id" in data

    async def test_create_visit_minimal(self, client: AsyncClient, auth_headers):
        """Test visit creation with minimal data."""
        response = await client.post(
            "/api/v1/visits",
            headers=auth_headers,
            json={
                "patient_ref": "PT-MIN-001",
                "visit_date": "2024-01-15T14:00:00Z",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["patient_ref"] == "PT-MIN-001"
        assert data["chief_complaint"] is None

    async def test_create_visit_unauthenticated(self, client: AsyncClient):
        """Test visit creation without authentication."""
        response = await client.post(
            "/api/v1/visits",
            json={
                "patient_ref": "PT-001",
                "visit_date": "2024-01-15T14:00:00Z",
            },
        )

        # FastAPI returns 403 for missing credentials with OAuth2PasswordBearer
        assert response.status_code in [401, 403]

    async def test_list_visits(self, client: AsyncClient, auth_headers, test_visit):
        """Test listing visits."""
        response = await client.get(
            "/api/v1/visits",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert len(data["items"]) >= 1

    async def test_list_visits_pagination(self, client: AsyncClient, auth_headers, test_visit):
        """Test visit listing with pagination."""
        response = await client.get(
            "/api/v1/visits?limit=1&offset=0",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "limit" in data
        assert "offset" in data
        assert data["limit"] == 1

    async def test_get_visit_success(self, client: AsyncClient, auth_headers, test_visit):
        """Test getting a single visit."""
        response = await client.get(
            f"/api/v1/visits/{test_visit.id}",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(test_visit.id)
        assert data["patient_ref"] == test_visit.patient_ref

    async def test_get_visit_not_found(self, client: AsyncClient, auth_headers):
        """Test getting a non-existent visit."""
        response = await client.get(
            "/api/v1/visits/00000000-0000-0000-0000-000000000000",
            headers=auth_headers,
        )

        assert response.status_code == 404

    async def test_delete_visit_success(self, client: AsyncClient, auth_headers, test_visit):
        """Test deleting a visit."""
        response = await client.delete(
            f"/api/v1/visits/{test_visit.id}",
            headers=auth_headers,
        )

        assert response.status_code == 204

        # Verify it's deleted
        get_response = await client.get(
            f"/api/v1/visits/{test_visit.id}",
            headers=auth_headers,
        )
        assert get_response.status_code == 404

    async def test_delete_visit_not_found(self, client: AsyncClient, auth_headers):
        """Test deleting a non-existent visit."""
        response = await client.delete(
            "/api/v1/visits/00000000-0000-0000-0000-000000000000",
            headers=auth_headers,
        )

        assert response.status_code == 404

    async def test_visit_isolation(self, client: AsyncClient, db_session, test_visit):
        """Test that users can only see their own visits."""
        from app.models.user import User
        from app.services.auth import hash_password, create_access_token
        import uuid

        # Create another user
        other_user = User(
            id=uuid.uuid4(),
            email="other@example.com",
            hashed_password=hash_password("password123"),
            full_name="Other User",
            is_active=True,
        )
        db_session.add(other_user)
        await db_session.commit()

        other_token = create_access_token(str(other_user.id))
        other_headers = {"Authorization": f"Bearer {other_token}"}

        # Try to access the test_visit with other user
        response = await client.get(
            f"/api/v1/visits/{test_visit.id}",
            headers=other_headers,
        )

        assert response.status_code == 404
