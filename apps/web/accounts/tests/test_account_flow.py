import pytest


@pytest.mark.django_db
def test_login_carries_next_through_form(client):
    # A logged-out user sent to /login/?next=... (e.g. by @login_required) must
    # get next round-tripped through the form so the POST lands them back where
    # they were headed instead of the default LOGIN_REDIRECT_URL.
    resp = client.get("/login/?next=/saved/")
    assert resp.status_code == 200
    assert b'name="next"' in resp.content
    assert b'value="/saved/"' in resp.content


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


@pytest.mark.django_db
def test_signup_page_renders_styled(client):
    resp = client.get("/signup/")
    assert resp.status_code == 200
    assert b"Create your account" in resp.content
    assert b"Continue with Google" in resp.content
    assert b"Already have an account" in resp.content
