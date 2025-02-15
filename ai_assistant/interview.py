import os
import requests
import json


class Interview:
    """
    Класс для проведения интервью на знание Python.

    Класс использует OpenAI API для сравнения эталонного ответа с ответом пользователя
    и выставления оценки по 10-бальной шкале.

    Attributes:
        client: Объект клиента OpenAI, инициализируется с помощью API токена.
        description (str): Инструкция для оценки ответов.
        question (str): Вопрос, на который нужно ответить.
        reference_question (str): Эталонный ответ.
        user_question (str): Ответ пользователя.
    """

    client = None
    description = """
                   Ты проводишь собеседование на знание языка программирования Python.
                   На вход получаешь два ответа на вопрос, эталонный и ответ, который нужно проверить.
                   Сравни их по смыслу. Выстави оценку за правильность ответа по 10-бальной шкале.
                   Будь снисходителен: ответ не должен точно повторять эталонный, должны быть похожи основные мысли.
                   Не снижай оценку за структуру ответа, его краткость или многословность.
                   Главное, чтобы в представленном ответе хоть как-то упоминались тезисы из эталонного ответа!
                   Если все мысли похожи — это максимальный балл.
                   Не снижай оценку за грамотность и форматирование ответа.
                   Полное несовпадение — 0 баллов.
                   Верна основная мысль — от 2 до 6 баллов.
                   Верна основная мысль и дополнительные мысли — от 6 до 10 баллов.
                   Не пиши о сравнении с эталонным ответом.
                   Не снижай оценку за отсутствие второстепенных данных.
                   Начни без вступления — сразу с оценки и того, что можно добавить к ответу.
                   Оценку пиши одним числом.
                  """
                  
    def __init__(self, question, reference_question, user_question) -> None:
        """
        Инициализация объекта класса Interview.

        Args:
            question (str): Вопрос для собеседования.
            reference_question (str): Эталонный ответ на вопрос.
            user_question (str): Ответ пользователя, который необходимо оценить.
        """
        token = 'sk-59J1nXyKKDgwIt31fmxhoLn1JnoLHPdw'
        self.question = question
        self.reference_question = reference_question
        self.user_question = user_question

# interview = Interview('Что такое переменная в Python?',
#                       'Переменная в Python — это именованная ссылка на объект. Переменные позволяют сохранять, изменять и использовать значения в программах. В Python переменные не требуют объявления их типа, так как интерпретатор определит тип данных автоматически.',
#                       'Переменная в Питоне — это как ярлык, который можно прикрепить к игрушке, чтобы потом знать, как её звать. Переменные помогают запомнить что-то важное, менять это и использовать, когда нужно. В Питоне не надо говорить, какая игрушка — машина или мячик, Питон сам всё поймёт!')
#
# print(interview.get_response())

class InterviewThisOutOfOpenAI(Interview):
    """
    Класс для проведения интервью на знание Python.

    Класс наследуется от класса Interview и использует OpenAI API для сравнения эталонного ответа с ответом пользователя
    и выставления оценки по 10-бальной шкале.
    Не использует библиотеку OpenAI.
    """


    def __init__(self, question, reference_question, user_question) -> None:
        """
        Инициализация объекта класса InterviewThisOutOfOpenAI.

        Args:
            question (str): Вопрос для собеседования.
            reference_question (str): Эталонный ответ на вопрос.
            user_question (str): Ответ пользователя, который необходимо оценить.
        """
        self.token = 'sk-59J1nXyKKDgwIt31fmxhoLn1JnoLHPdw'
        super().__init__(question, reference_question, user_question)

    def get_response(self) -> str:
        """
        Выполняет запрос к OpenAI API для оценки ответа пользователя.

        Формирует запрос к модели с инструкцией по оценке ответа пользователя и возвращает оценку.

        Returns:
            str: Оценка ответа пользователя, сгенерированная OpenAI.
        """
        user_request = (f'Вопрос: {self.question}.'
                        f'Эталонный ответ: {self.reference_question}'
                        f'Ответ: {self.user_question}')

        # Заголовки запроса
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.token}'
        }

        # Данные запроса
        data = {
            "model": "gpt-4o",  # Или другой доступный вам вариант модели
            "messages": [
                {"role": "system", "content": self.description},
                {"role": "user", "content": user_request}
            ],
            "max_tokens": 150,
            "temperature": 0.7
        }
        
        proxies = {
            "https": "http://1zhPU6Rq:aafJcerK@194.87.117.211:63692"
        }

        # Отправка POST-запроса к API
        response = requests.post('https://api.proxyapi.ru/openai/v1/chat/completions', headers=headers, data=json.dumps(data), proxies=proxies)

        # Обработка ответа
        if response.status_code == 200:
            result = response.json()
            return result['choices'][0]['message']['content']
        else:
            return f"Error: {response.status_code}\n{response.text}"

# interview = InterviewThisOutOfOpenAI('Что такое переменная в Python?',
#                       'Переменная в Python — это именованная ссылка на объект. Переменные позволяют сохранять, изменять и использовать значения в программах. В Python переменные не требуют объявления их типа, так как интерпретатор определит тип данных автоматически.',
#                       'Переменная в Питоне — это как ярлык, который можно прикрепить к игрушке, чтобы потом знать, как её звать. Переменные помогают запомнить что-то важное, менять это и использовать, когда нужно. В Питоне не надо говорить, какая игрушка — машина или мячик, Питон сам всё поймёт!')
#
# print(interview.get_response())