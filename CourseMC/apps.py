from social_django.apps import PythonSocialAuthConfig


class LocalizedPythonSocialAuthConfig(PythonSocialAuthConfig):
    verbose_name = 'Социальная авторизация'

    def ready(self):
        super().ready()

        from social_django.models import (
            Association,
            Code,
            Nonce,
            Partial,
            UserSocialAuth,
        )

        self._localize_model(
            UserSocialAuth,
            'Связь с социальной сетью',
            'Связи с социальными сетями',
            {
                'user': 'Пользователь',
                'provider': 'Провайдер',
                'uid': 'Идентификатор пользователя',
                'extra_data': 'Дополнительные данные',
                'created': 'Создана',
                'modified': 'Изменена',
            },
        )
        self._localize_model(
            Nonce,
            'Одноразовый идентификатор',
            'Одноразовые идентификаторы',
            {
                'server_url': 'Адрес сервера',
                'timestamp': 'Метка времени',
                'salt': 'Соль',
            },
        )
        self._localize_model(
            Association,
            'OpenID-ассоциация',
            'OpenID-ассоциации',
            {
                'server_url': 'Адрес сервера',
                'handle': 'Идентификатор',
                'secret': 'Секрет',
                'issued': 'Время выдачи',
                'lifetime': 'Срок действия',
                'assoc_type': 'Тип ассоциации',
            },
        )
        self._localize_model(
            Code,
            'Код подтверждения',
            'Коды подтверждения',
            {
                'email': 'Электронная почта',
                'code': 'Код',
                'verified': 'Подтверждён',
                'timestamp': 'Создан',
            },
        )
        self._localize_model(
            Partial,
            'Незавершённая авторизация',
            'Незавершённые авторизации',
            {
                'token': 'Токен',
                'next_step': 'Следующий шаг',
                'backend': 'Способ авторизации',
                'data': 'Данные',
                'timestamp': 'Создана',
            },
        )

    @staticmethod
    def _localize_model(model, verbose_name, verbose_name_plural, fields):
        model._meta.verbose_name = verbose_name
        model._meta.verbose_name_plural = verbose_name_plural

        for field_name, field_verbose_name in fields.items():
            model._meta.get_field(field_name).verbose_name = field_verbose_name
