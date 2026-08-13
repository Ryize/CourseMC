import requests
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render

from chatgpt.models import RequestsGPT
from reviews.models import Review


@login_required
def index(request):
    context = {
        'reviews_count': Review.objects.all().count()
    }
    return render(request, 'chatgpt/index.html', context)


@login_required
def send_request_api(request):
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        chat = ChatGPT()
        data = request.POST.get('text')
        text_gpt = chat.send(data).lstrip('\n')
        text_gpt = text_gpt.replace(
            '\n', '<br>'
        ).replace(
            '  ', '&nbsp;&nbsp;'
        ).replace(
            '```python', '<br>'
        ).replace(
            '```', ''
        )
        result_data = {
            'success': True,
            'text': text_gpt,
        }
        if request.user.username != 'MatveyChekashov':
            RequestsGPT.objects.create(
                user=request.user,
                text_request=data,
                text_response=text_gpt
            )
        return JsonResponse(result_data)


class ChatGPT:
    def send(self, data) -> str:
        if not settings.PROXYAPI_API_KEY:
            return 'Сервис временно не настроен. Обратитесь к преподавателю.'

        response = requests.post(
            settings.PROXYAPI_REVIEW_API_URL,
            headers={
                'Authorization': f'Bearer {settings.PROXYAPI_API_KEY}',
                'Content-Type': 'application/json',
            },
            json={
                'model': settings.PROXYAPI_REVIEW_MODEL,
                'messages': [{'role': 'user', 'content': data}],
                'max_tokens': 1200,
                'temperature': 0.7,
            },
            timeout=(5, 75),
        )
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content']
