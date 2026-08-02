from django.contrib.auth import get_user
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_POST
from django.views.generic import ListView

from reviews.models import Review


class ReviewView(ListView):
    model = Review
    template_name = "Review/index.html"
    context_object_name = "reviews"
    paginate_by = 16

    def post(self, *args, **kwargs):
        content = self.request.POST.get("content", "").strip()
        user = get_user(self.request)
        if not user.is_authenticated:
            return JsonResponse(
                {
                    "success": False,
                    "error_code": 0,
                    "error_msg": "Вы не авторизованы!",
                },
                status=401,
            )
        if not content:
            return JsonResponse(
                {
                    "success": False,
                    "error_code": 2,
                    "error_msg": "Напишите текст отзыва.",
                },
                status=400,
            )
        if Review.objects.filter(author_id=user).exists():
            return JsonResponse(
                {
                    "success": False,
                    "error_code": 1,
                    "error_msg": "Вы уже оставляли отзыв!",
                }
            )
        Review(author_id=user, content=content).save()
        return JsonResponse({"success": True})

    def get_context_data(self, *, object_list=None, **kwargs):
        context = super().get_context_data(**kwargs)
        context["reviews_count"] = Review.objects.all().count()
        return context


@require_POST
def check_left_review(request):
    user = get_user(request)
    if not user.is_authenticated:
        return JsonResponse({"success": False})
    return JsonResponse(
        {"success": Review.objects.filter(author_id=user).exists()}
    )
