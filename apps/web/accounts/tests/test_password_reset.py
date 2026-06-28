import re

import pytest
from django.contrib.auth import get_user_model
from django.core import mail

User = get_user_model()


@pytest.mark.django_db
def test_reset_form_get_renders(client):
    resp = client.get("/password-reset/")
    assert resp.status_code == 200
    assert b"Reset your password" in resp.content


@pytest.mark.django_db
def test_password_reset_emails_a_working_link(client):
    User.objects.create_user(email="cook@example.com", password="oldpassword1")

    resp = client.post("/password-reset/", {"email": "cook@example.com"})
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/password-reset/done/"

    assert len(mail.outbox) == 1
    body = mail.outbox[0].body
    match = re.search(r"/reset/[^/\s]+/[^/\s]+/", body)
    assert match, body
    link = match.group(0)

    # GET the link -> view stashes the token in the session and redirects
    # to the set-password URL.
    resp = client.get(link)
    assert resp.status_code == 302
    set_url = resp.headers["Location"]

    resp = client.post(
        set_url,
        {"new_password1": "brandnew-pass9", "new_password2": "brandnew-pass9"},
    )
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/reset/done/"

    user = User.objects.get(email="cook@example.com")
    assert user.check_password("brandnew-pass9")


@pytest.mark.django_db
def test_reset_unknown_email_shows_done_without_sending(client):
    resp = client.post("/password-reset/", {"email": "nobody@example.com"})
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/password-reset/done/"
    assert len(mail.outbox) == 0
