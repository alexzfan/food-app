from django.urls import path

from .views import AppLoginView, AppLogoutView, profile, signup

urlpatterns = [
    path("login/", AppLoginView.as_view(), name="login"),
    path("logout/", AppLogoutView.as_view(), name="logout"),
    path("signup/", signup, name="signup"),
    path("profile/", profile, name="profile"),
]
