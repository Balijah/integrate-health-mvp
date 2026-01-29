"""
Tests for note endpoints.
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient


@pytest.mark.asyncio
class TestNoteEndpoints:
    """Tests for note API endpoints."""

    async def test_get_note_not_exists(
        self, client: AsyncClient, auth_headers, test_visit
    ):
        """Test getting notes when none exist."""
        response = await client.get(
            f"/api/v1/visits/{test_visit.id}/notes",
            headers=auth_headers,
        )

        # API returns 404 when no note exists, or 200 with null/empty response
        assert response.status_code in [200, 404]

    async def test_generate_note_no_transcript(
        self, client: AsyncClient, auth_headers, test_visit
    ):
        """Test generating note when no transcript exists."""
        response = await client.post(
            f"/api/v1/visits/{test_visit.id}/notes/generate",
            headers=auth_headers,
            json={},
        )

        assert response.status_code == 400
        assert "transcript" in response.json()["detail"].lower()

    async def test_get_note_visit_not_found(self, client: AsyncClient, auth_headers):
        """Test getting notes for non-existent visit."""
        response = await client.get(
            "/api/v1/visits/00000000-0000-0000-0000-000000000000/notes",
            headers=auth_headers,
        )

        assert response.status_code == 404

    async def test_export_note_not_found(
        self, client: AsyncClient, auth_headers, test_visit
    ):
        """Test exporting note that doesn't exist."""
        response = await client.post(
            f"/api/v1/visits/{test_visit.id}/notes/00000000-0000-0000-0000-000000000000/export",
            headers=auth_headers,
            json={"format": "markdown"},
        )

        assert response.status_code == 404


@pytest.mark.asyncio
class TestNoteWithExistingNote:
    """Tests for note endpoints when a note already exists."""

    @pytest_asyncio.fixture
    async def visit_with_note(self, db_session, test_user):
        """Create a visit with an existing note."""
        import uuid
        from datetime import datetime
        from app.models.visit import Visit
        from app.models.note import Note

        visit = Visit(
            id=uuid.uuid4(),
            user_id=test_user.id,
            patient_ref="PT-NOTE-001",
            visit_date=datetime.utcnow(),
            chief_complaint="Test with note",
            transcript="Test transcript content",
            transcription_status="completed",
        )
        db_session.add(visit)
        await db_session.commit()

        note = Note(
            id=uuid.uuid4(),
            visit_id=visit.id,
            content={
                "subjective": {
                    "chief_complaint": "Test complaint",
                    "history_of_present_illness": "Test history",
                    "review_of_systems": "",
                    "past_medical_history": "",
                    "medications": [],
                    "supplements": [],
                    "allergies": [],
                    "social_history": "",
                    "family_history": "",
                },
                "objective": {
                    "vitals": {
                        "blood_pressure": "",
                        "heart_rate": "",
                        "temperature": "",
                        "weight": "",
                    },
                    "physical_exam": "",
                    "lab_results": "",
                },
                "assessment": {
                    "diagnoses": ["Test diagnosis"],
                    "clinical_reasoning": "Test reasoning",
                },
                "plan": {
                    "treatment_plan": "Test plan",
                    "medications_prescribed": [],
                    "supplements_recommended": [],
                    "lifestyle_recommendations": "",
                    "lab_orders": [],
                    "follow_up": "",
                    "patient_education": "",
                },
                "metadata": {
                    "generated_at": datetime.utcnow().isoformat(),
                    "model_version": "test",
                    "confidence_score": 0.95,
                },
            },
            note_type="soap",
            status="draft",
        )
        db_session.add(note)
        await db_session.commit()
        await db_session.refresh(visit)
        await db_session.refresh(note)

        return {"visit": visit, "note": note}

    async def test_get_note_success(
        self, client: AsyncClient, auth_headers, visit_with_note
    ):
        """Test getting an existing note."""
        visit = visit_with_note["visit"]

        response = await client.get(
            f"/api/v1/visits/{visit.id}/notes",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "draft"
        assert "content" in data
        assert data["content"]["subjective"]["chief_complaint"] == "Test complaint"

    async def test_update_note_success(
        self, client: AsyncClient, auth_headers, visit_with_note
    ):
        """Test updating a note."""
        visit = visit_with_note["visit"]
        note = visit_with_note["note"]

        # Get the existing note to get full content
        get_response = await client.get(
            f"/api/v1/visits/{visit.id}/notes",
            headers=auth_headers,
        )
        existing_content = get_response.json()["content"]

        # Update the chief complaint
        existing_content["subjective"]["chief_complaint"] = "Updated complaint"

        response = await client.put(
            f"/api/v1/visits/{visit.id}/notes/{note.id}",
            headers=auth_headers,
            json={
                "content": existing_content,
                "status": "reviewed",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "reviewed"
        assert data["content"]["subjective"]["chief_complaint"] == "Updated complaint"

    async def test_export_note_markdown(
        self, client: AsyncClient, auth_headers, visit_with_note
    ):
        """Test exporting note as markdown."""
        visit = visit_with_note["visit"]
        note = visit_with_note["note"]

        response = await client.post(
            f"/api/v1/visits/{visit.id}/notes/{note.id}/export",
            headers=auth_headers,
            json={"format": "markdown"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["format"] == "markdown"
        assert "content" in data
        assert "# SOAP Note" in data["content"]

    async def test_export_note_json(
        self, client: AsyncClient, auth_headers, visit_with_note
    ):
        """Test exporting note as JSON."""
        visit = visit_with_note["visit"]
        note = visit_with_note["note"]

        response = await client.post(
            f"/api/v1/visits/{visit.id}/notes/{note.id}/export",
            headers=auth_headers,
            json={"format": "json"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["format"] == "json"
