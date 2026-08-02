# SOLID

# D - DIP - Dependency Inversion Principle - Принцип инверсии зависимостей
# DIP -
# 1) Модули верхних уровней не должны зависеть от модулей нижних уровней.
# Оба этих модуля должны зависеть от абстракций.
# 2) Абстракции не должны зависеть от деталей. Детали должны зависеть от
# абстракций.


# ❌ Не правильно:
class DB:
    def insert(self, data):
        if User.min_login_length < data[0] < User.max_login_length:
            print('Добавляю данные в таблицу!')
        else:
            print('Логин неверной длины!')

    def select(self):
        print('Получаю данные из таблицу')


class User:
    min_login_length = 4
    max_login_length = 25

    def register(self, login, password):
        db = DB()
        db.insert([login, password])

    def login(self, login, password):
        db = DB()
        data = db.select()
        if data[0] == login and data[1] == password:
            print('Успешная авторизация!')


# ✅ Правильно:
class DB:
    def insert(self, data):
        print('Добавляю данные в таблицу!')

    def select(self):
        print('Получаю данные из таблицу')


class User:
    min_login_length = 4
    max_login_length = 25

    def register(self, login, password):
        db = DB()
        if self.min_login_length < login < self.max_login_length:
            db.insert([login, password])
        else:
            print('Неверная длина логина!')

    def login(self, login, password):
        db = DB()
        data = db.select()
        if data[0] == login and data[1] == password:
            print('Успешная авторизация!')

# Преимущества:
# 1) Повышается надёжность кода
# 2) Повышается предсказуемость системы

# Недостатки:
# 1) Сложность исправления кода
# 2) Высокая цена ошибки