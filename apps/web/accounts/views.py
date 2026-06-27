from functools import wraps

from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from .forms import SignupForm


def onboarding_required(view):
    """Redirect authenticated users who haven't finished onboarding into it."""
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if request.user.is_authenticated and not request.user.onboarding_completed:
            return redirect("onboarding")
        return view(request, *args, **kwargs)
    return wrapped


class AppLoginView(LoginView):
    template_name = "accounts/login.html"
    redirect_authenticated_user = True


class AppLogoutView(LogoutView):
    pass


def signup(request):
    if request.user.is_authenticated:
        return redirect("discover")
    if request.method == "POST":
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("onboarding")
    else:
        form = SignupForm()
    return render(request, "accounts/signup.html", {"form": form})


@login_required
def profile(request):
    if request.method == "POST":
        request.user.display_name = request.POST.get("display_name", "")
        request.user.save(update_fields=["display_name"])
    return render(request, "accounts/profile.html")


@login_required
def onboarding(request):
    if request.user.onboarding_completed:
        return redirect("discover")
    return render(request, "accounts/onboarding_welcome.html")


@login_required
@require_POST
def onboarding_skip(request):
    request.user.onboarding_completed = True
    request.user.save(update_fields=["onboarding_completed"])
    return redirect("discover")
