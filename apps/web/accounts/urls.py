from django.urls import path

from .views import (
    AppLoginView,
    AppLogoutView,
    onboarding,
    onboarding_skip,
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
]
