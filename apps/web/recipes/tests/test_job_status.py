import pytest
from django.contrib.auth import get_user_model

from recipes.models import ExtractionJob, Recipe

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(email="u@e.com", password="supersecret")


@pytest.fixture
def auth_client(client, user):
    client.login(username="u@e.com", password="supersecret")
    return client


def test_running_job_renders_poller(auth_client, user):
    job = ExtractionJob.objects.create(
        owner=user, source="upload", status=ExtractionJob.Status.EXTRACTING,
        step_label="Extracting recipe...")
    resp = auth_client.get(f"/jobs/{job.id}/status/")
    assert resp.status_code == 200
    assert b"Extracting recipe" in resp.content


def test_done_job_redirects(auth_client, user):
    recipe = Recipe.objects.create(owner=user, title="Pasta")
    job = ExtractionJob.objects.create(
        owner=user, source="upload", status=ExtractionJob.Status.DONE, recipe=recipe)
    resp = auth_client.get(f"/jobs/{job.id}/status/")
    assert resp.status_code == 204
    assert resp["HX-Redirect"] == f"/recipes/{recipe.id}/"


def test_other_users_job_404(auth_client, db):
    other = User.objects.create_user(email="o@e.com", password="supersecret")
    job = ExtractionJob.objects.create(owner=other, source="upload")
    resp = auth_client.get(f"/jobs/{job.id}/status/")
    assert resp.status_code == 404
