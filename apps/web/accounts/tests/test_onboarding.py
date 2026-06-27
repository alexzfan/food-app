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
