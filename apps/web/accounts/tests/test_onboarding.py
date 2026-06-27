import pytest
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.mark.django_db
def test_new_user_preference_defaults():
    u = User.objects.create_user(email="new@e.com", password="supersecret")
    assert u.preferred_cuisines == []
    assert u.dietary_tags == []
    assert u.max_cook_time_minutes is None
    assert u.onboarding_completed is False


@pytest.fixture
def user(db):
    return User.objects.create_user(email="u@e.com", password="supersecret")


@pytest.fixture
def auth_client(client, user):
    client.login(username="u@e.com", password="supersecret")
    return client


@pytest.mark.django_db
def test_signup_redirects_to_onboarding(client):
    resp = client.post(
        "/signup/",
        {"email": "cook@example.com", "display_name": "Cook", "password": "supersecret"},
    )
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/onboarding/"


@pytest.mark.django_db
def test_incomplete_user_is_gated_to_onboarding(auth_client):
    resp = auth_client.get("/")  # discover
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/onboarding/"


@pytest.mark.django_db
def test_completed_user_reaches_discover(auth_client, user):
    user.onboarding_completed = True
    user.save(update_fields=["onboarding_completed"])
    resp = auth_client.get("/")
    assert resp.status_code == 200


@pytest.mark.django_db
def test_welcome_renders(auth_client):
    resp = auth_client.get("/onboarding/")
    assert resp.status_code == 200
    assert b"what are we cooking" in resp.content.lower() or b"cook" in resp.content.lower()


@pytest.mark.django_db
def test_skip_completes_with_empty_prefs(auth_client, user):
    resp = auth_client.post("/onboarding/skip/")
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/"
    user.refresh_from_db()
    assert user.onboarding_completed is True
    assert user.preferred_cuisines == []
    assert user.dietary_tags == []


@pytest.mark.django_db
def test_tastes_saves_and_advances(auth_client, user):
    resp = auth_client.post(
        "/onboarding/tastes/",
        {"cuisines": ["Italian", "Thai"], "diets": ["Vegetarian"]},
    )
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/onboarding/cook-time/"
    user.refresh_from_db()
    assert user.preferred_cuisines == ["Italian", "Thai"]
    assert user.dietary_tags == ["Vegetarian"]
    assert user.onboarding_completed is False  # not done until cook-time step


@pytest.mark.django_db
def test_tastes_ignores_unknown_values(auth_client, user):
    auth_client.post("/onboarding/tastes/", {"cuisines": ["Italian", "Klingon"]})
    user.refresh_from_db()
    assert user.preferred_cuisines == ["Italian"]


@pytest.mark.django_db
def test_cook_time_completes_onboarding(auth_client, user):
    resp = auth_client.post("/onboarding/cook-time/", {"max_cook_time": "30"})
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/"
    user.refresh_from_db()
    assert user.max_cook_time_minutes == 30
    assert user.onboarding_completed is True


@pytest.mark.django_db
def test_cook_time_any_stores_null(auth_client, user):
    auth_client.post("/onboarding/cook-time/", {"max_cook_time": "0"})
    user.refresh_from_db()
    assert user.max_cook_time_minutes is None
    assert user.onboarding_completed is True
