from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from .views import (
    AppLoginView,
    AppLogoutView,
    onboarding,
    onboarding_cook_time,
    onboarding_skip,
    onboarding_tastes,
    profile,
    signup,
    verify_email,
)

urlpatterns = [
    path("login/", AppLoginView.as_view(), name="login"),
    path("logout/", AppLogoutView.as_view(), name="logout"),
    path("signup/", signup, name="signup"),
    path("verify-email/", verify_email, name="verify_email"),
    path("profile/", profile, name="profile"),
    path("onboarding/", onboarding, name="onboarding"),
    path("onboarding/skip/", onboarding_skip, name="onboarding_skip"),
    path("onboarding/tastes/", onboarding_tastes, name="onboarding_tastes"),
    path("onboarding/cook-time/", onboarding_cook_time, name="onboarding_cook_time"),
    path(
        "password-reset/",
        auth_views.PasswordResetView.as_view(
            template_name="accounts/password_reset_form.html",
            email_template_name="accounts/password_reset_email.txt",
            subject_template_name="accounts/password_reset_subject.txt",
            success_url=reverse_lazy("password_reset_done"),
        ),
        name="password_reset",
    ),
    path(
        "password-reset/done/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="accounts/password_reset_done.html",
        ),
        name="password_reset_done",
    ),
    path(
        "reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="accounts/password_reset_confirm.html",
            success_url=reverse_lazy("password_reset_complete"),
        ),
        name="password_reset_confirm",
    ),
    path(
        "reset/done/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="accounts/password_reset_complete.html",
        ),
        name="password_reset_complete",
    ),
]
