import pytest
from django.contrib.auth import get_user_model

from accounts.forms import SignupForm

User = get_user_model()


@pytest.mark.django_db
def test_signup_creates_user_and_logs_in(client):
    resp = client.post(
        "/signup/",
        {"email": "cook@example.com", "display_name": "Cook", "password": "supersecret"},
    )
    assert resp.status_code == 302
    user = User.objects.get(email="cook@example.com")
    assert user.check_password("supersecret")
    assert "_auth_user_id" in client.session


@pytest.mark.django_db
def test_signup_does_not_require_display_name(client):
    resp = client.post(
        "/signup/", {"email": "no-name@example.com", "password": "supersecret"}
    )
    assert resp.status_code == 302
    u = User.objects.get(email="no-name@example.com")
    assert u.check_password("supersecret")
    assert u.display_name == ""
    assert "display_name" not in SignupForm().fields


@pytest.mark.django_db
def test_login_with_email(client):
    User.objects.create_user(email="a@b.com", password="supersecret")
    resp = client.post("/login/", {"username": "a@b.com", "password": "supersecret"})
    assert resp.status_code == 302
    assert "_auth_user_id" in client.session


@pytest.mark.django_db
def test_email_must_be_unique(client):
    User.objects.create_user(email="a@b.com", password="supersecret")
    form_resp = client.post(
        "/signup/", {"email": "a@b.com", "display_name": "x", "password": "supersecret"}
    )
    assert form_resp.status_code == 200  # re-render with error
    assert User.objects.filter(email="a@b.com").count() == 1
