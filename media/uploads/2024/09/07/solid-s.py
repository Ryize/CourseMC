# SOLID

# S - SRP - Single Responsibility Principle - Принцип единой ответственности
# SRP - любая программная сущность должна отвечать за одно и только за одно
# действие.

# Принцип SLAP - Single Layer Abstraction Principle - Принцип единого уровня
# абстракции.
# SLAP - любая программная сущность должна отвечать за один уровень абстракции.

# ❌ Не правильно:
# def register():
#     login = input('Введите ваш логин: ')
#     password = input('Введите ваш пароль: ')
#
#     if not 3 < len(login) < 24:
#         print('Неверная длинна логина')
#         return False
#     elif not 3 < len(password) < 32:
#         print('Неверная длинна пароля')
#         return False
#
#     with open('BAZA.txt', encoding='utf-8') as file:
#         for line in file.read().split():
#             file_login = line.split('/')[0]
#             if file_login == login:
#                 print('Такой пользователь уже зарегистрирован!')
#                 return False
#
#     with open('BAZA.txt', 'a', encoding='utf-8') as file:
#         file.write(f'{login}/{password}\n')
#     return True


# ✅ Правильно:
def create_user(login: str, password: str) -> None:
    with open('BAZA.txt', 'a', encoding='utf-8') as file:
        file.write(f'{login}/{password}\n')


def check_user_exist(login: str) -> bool:
    with open('BAZA.txt', encoding='utf-8') as file:
        for line in file.read().split():
            file_login = line.split('/')[0]
            if file_login == login:
                print('Такой пользователь уже зарегистрирован!')
                return False
    return True


def get_user_auth_data() -> tuple:
    login = input('Введите ваш логин: ')
    password = input('Введите ваш пароль: ')
    return login, password


def check_auth_data(login: str, password: str) -> bool:
    if not 3 < len(login) < 24:
        print('Неверная длинна логина')
        return False
    elif not 3 < len(password) < 32:
        print('Неверная длинна пароля')
        return False
    return True


def register() -> bool:
    login, password = get_user_auth_data()

    if not check_auth_data(login, password):
        return False

    if not check_user_exist(login):
        return False

    create_user(login, password)
    return True

# Преимущества:
# 1) Легче читать код
# 2) Проще вносить изменения
# 3) Легче писать тесты


# Недостатки:
# 1) Увеличение объёма кода
# 2) Большее количество функций