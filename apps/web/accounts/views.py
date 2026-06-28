from functools import wraps

from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from .constants import COOK_TIME_OPTIONS, CUISINE_OPTIONS, DIET_OPTIONS
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


def verify_email(request):
    """Standalone styled preview of the email-verification screen.

    Not wired into signup (see the account-flow spec) — renders only.
    """
    return render(request, "accounts/verify_email.html")


@login_required
@onboarding_required
def profile(request):
    if request.method == "POST":
        request.user.display_name = request.POST.get("display_name", "")
        request.user.save(update_fields=["display_name"])
    return render(request, "accounts/profile.html")


@login_required
def onboarding(request):
    if request.user.onboarding_completed:
        return redirect("discover")
    return render(request, "accounts/onboarding_welcome.html", {"step": 1})


@login_required
@require_POST
def onboarding_skip(request):
    request.user.onboarding_completed = True
    request.user.save(update_fields=["onboarding_completed"])
    return redirect("discover")


@login_required
def onboarding_tastes(request):
    if request.user.onboarding_completed:
        return redirect("discover")
    if request.method == "POST":
        # Filter against the canonical lists: dedupes, bounds the stored length to
        # the number of options, and gives a stable order regardless of POST order.
        submitted_cuisines = set(request.POST.getlist("cuisines"))
        submitted_diets = set(request.POST.getlist("diets"))
        chosen_cuisines = [c for c in CUISINE_OPTIONS if c in submitted_cuisines]
        chosen_diets = [d for d in DIET_OPTIONS if d in submitted_diets]
        request.user.preferred_cuisines = chosen_cuisines
        request.user.dietary_tags = chosen_diets
        request.user.save(update_fields=["preferred_cuisines", "dietary_tags"])
        return redirect("onboarding_cook_time")
    return render(
        request,
        "accounts/onboarding_tastes.html",
        {
            "cuisine_options": CUISINE_OPTIONS,
            "diet_options": DIET_OPTIONS,
            "selected_cuisines": request.user.preferred_cuisines,
            "selected_diets": request.user.dietary_tags,
            "step": 2,
        },
    )


@login_required
def onboarding_cook_time(request):
    if request.user.onboarding_completed:
        return redirect("discover")
    if request.method == "POST":
        valid = {str(m) for m, _ in COOK_TIME_OPTIONS}
        raw = request.POST.get("max_cook_time", "0")
        # Unknown/tampered value -> 0, which stores as None (same as the "Any" option).
        minutes = int(raw) if raw in valid else 0
        request.user.max_cook_time_minutes = minutes or None
        request.user.onboarding_completed = True
        request.user.save(update_fields=["max_cook_time_minutes", "onboarding_completed"])
        return redirect("discover")
    return render(
        request,
        "accounts/onboarding_cook_time.html",
        {"cook_time_options": COOK_TIME_OPTIONS, "step": 3},
    )
