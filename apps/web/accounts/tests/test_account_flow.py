import pytest


@pytest.mark.django_db
def test_verify_email_preview_renders(client):
    resp = client.get("/verify-email/")
    assert resp.status_code == 200
    assert b"Verify your email" in resp.content


@pytest.mark.django_db
def test_login_page_renders_styled(client):
    resp = client.get("/login/")
    assert resp.status_code == 200
    assert b"Continue with Google" in resp.content
    assert b"Forgot" in resp.content
    assert b"Create an account" in resp.content
