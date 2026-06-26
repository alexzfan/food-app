from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import redirect, render

from .forms import SignupForm


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
            return redirect("discover")
    else:
        form = SignupForm()
    return render(request, "accounts/signup.html", {"form": form})


@login_required
def profile(request):
    if request.method == "POST":
        request.user.display_name = request.POST.get("display_name", "")
        request.user.save(update_fields=["display_name"])
    return render(request, "accounts/profile.html")
