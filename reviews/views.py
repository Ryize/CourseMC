
from django.contrib.auth import get_user
from django.http import HttpResponse, JsonResponse
from django.views.generic import ListView

from reviews.models import Review


class ReviewView(ListView):
    model = Review
    template_name = 'Review/index.html'
    context_object_name = 'reviews'
    paginate_by = 16

    def post(self, *args, **kwargs):
        content = self.request.POST.get('content')
        user = get_user(self.request)
        if not user:
            return JsonResponse({
                'success': False,
                'error_code': 0,
                'error_msg': 'Вы не авторизованны!'
            })
        if Review.objects.filter(author_id=user).first():
            return JsonResponse({
                'success': False,
                'error_code': 1,
                'error_msg': 'Вы уже оставляли отзыв!'
            })
        Review(author_id=user, content=content).save()
        return JsonResponse({
                'success': True
            })
            
    def get_context_data(self, *, object_list=None, **kwargs):
        context = super().get_context_data(**kwargs)
        context['reviews_count'] = Review.objects.all().count()
        return context

def check_left_review(request):
    if request.method == 'POST':
        if Review.objects.filter(author_id=get_user(request)).first():
            return JsonResponse({
                'success': True
            })
        return JsonResponse({
            'success': False
        })