from django.http import HttpResponse, JsonResponse


def health(request):
    return JsonResponse({"status": "ok"})


def discover_placeholder(request):
    # Temporary; replaced by recipes.views.discover in Task 4.
    return HttpResponse("discover")
