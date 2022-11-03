from django.shortcuts import render


def page_not_found_view(request, url):
    return render(request, "errors/404.html", status=404)
