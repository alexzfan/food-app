import pytest


@pytest.mark.django_db
def test_verify_email_preview_renders(client):
    resp = client.get("/verify-email/")
    assert resp.status_code == 200
    assert b"Verify your email" in resp.content
