from django.urls import path

from .views import (
    AppLoginView,
    AppLogoutView,
    onboarding,
    onboarding_cook_time,
    onboarding_skip,
    onboarding_tastes,
    profile,
    signup,
)

urlpatterns = [
    path("login/", AppLoginView.as_view(), name="login"),
    path("logout/", AppLogoutView.as_view(), name="logout"),
    path("signup/", signup, name="signup"),
    path("profile/", profile, name="profile"),
    path("onboarding/", onboarding, name="onboarding"),
    path("onboarding/skip/", onboarding_skip, name="onboarding_skip"),
    path("onboarding/tastes/", onboarding_tastes, name="onboarding_tastes"),
    path("onboarding/cook-time/", onboarding_cook_time, name="onboarding_cook_time"),
]
