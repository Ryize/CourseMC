import random

import openai
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
    if request.is_ajax():
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
    __api_keys = (
        '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',
        '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',
        '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',
    )

    def __init__(self):
        openai.api_key = random.choice(self.__api_keys)
        self.model_engine = "text-davinci-003"

    def send(self, data) -> str:
        try:
            completion = openai.Completion.create(
                engine=self.model_engine,
                prompt=data,
                max_tokens=2048,
                temperature=1,
                top_p=1,
                frequency_penalty=0,
                presence_penalty=0
            )

            return completion.choices[0].text
        except:
            completion = openai.Completion.create(
                engine=self.model_engine,
                prompt=data,
                max_tokens=2048,
                temperature=1,
                top_p=1,
                frequency_penalty=0,
                presence_penalty=0
            )

            return completion.choices[0].text
