import datetime
import os
import time
import uuid

from threading import Thread
from time import sleep
from typing import Union

from yookassa import Payment, Configuration

from billing.config import SHOP_ID, SECRET_KEY
from billing.models import PaymentVerification, InformationPayments

Configuration.account_id = SHOP_ID
Configuration.secret_key = SECRET_KEY


def get_payment_url(amount: int) -> tuple:
    """
    Получение ссылки и id оплаты занятия.

    Args:
        amount: int (сумма оплаты)

    Returns:
        tuple:
            [0] - str (ссылка на оплату)
            [1] - str (id оплаты. Нужно для подтверждения оплаты в YooKassa)
    """

    idempotence_key = str(uuid.uuid4())
    payment = Payment.create({
        'amount': {
            'value': f'{amount}',
            'currency': 'RUB'
        },
        'confirmation': {
            'type': 'redirect',
            'return_url': 'https://coursemc.ru/billing/success/'
        },
        'description': 'Оплата занятий',
        'receipt': {
            'email': 'chekashovmatvey@gmail.com',
            'items': [
                {
                    'description': 'Урок',
                    'amount': {
                        'value': f'{amount}',
                        'currency': 'RUB'
                    }, 'vat_code': 1,
                    'quantity': 1}],
            'tax_system_id': 1,
        }
    }, idempotence_key)

    return payment.confirmation.confirmation_url, payment.id


def check_payment(payment_id: Union[str, int], amount: int) -> bool:
    """
    Проверить оплату.

    Args:
        payment_id: str | int (id оплаты, который получается при создании
        ссылки оплаты)
        amount: int (сумма оплаты)
    """

    idempotence_key = str(uuid.uuid4())
    try:
        Payment.capture(
            payment_id,
            {
                "amount": {
                    "value": f"{amount}",
                    "currency": "RUB"
                }
            },
            idempotence_key
        )
    except:
        pass
    res = Payment.find_one(payment_id)
    return res.status == 'succeeded'


def _() -> None:
    """
    Подтверждение оплаты.

    Каждые 60 секунд проверяет, была ли оплата, если да, то создается платеж.
    Использует модель PaymentVerification.
    """

    if os.environ.get('RUN_CHECK_BILLING', '0') == '1':
        return
    os.environ['RUN_CHECK_BILLING'] = '1'
    while True:
        try:
            users = {}
            for i in PaymentVerification.objects.order_by('-date').all():
                if i.user not in users:
                    users[i.user] = 0
                if users[i.user] > 5:
                    i.delete()
                if (time.time() - i.date.timestamp()) / 60 > 30:
                    i.delete()
                if check_payment(i.payment_id, i.amount):
                    i.delete()
                    if not InformationPayments.objects.filter(date=datetime.date.today(), amount=i.amount).first():
                        InformationPayments.objects.create(user=i.user,
                                                           amount=i.amount)
                time.sleep(3)
            sleep(60)
        except:
            pass


t = Thread(target=_, daemon=True)
t.start()
