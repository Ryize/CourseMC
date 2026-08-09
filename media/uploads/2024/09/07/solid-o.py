# SOLID

# O - OCP - Open closed principle - Принцип открытости закрытости.
# OCP - Класс должен быть открыт для расширения, но закрыт для изменения.

# ❌ Не правильно:
# class Shop:
#     tshirt = [1000, 0.95]
#     short = [1500, 0.94]
#     sneakers = [5000, 0.9]
#     gloves = [800, 0.85]
#
#     def __init__(self, title):
#         self.title = title
#
#     def calculate_discount(self):
#         if self.title == 'Майка':
#             return self.tshirt[0] * self.tshirt[1]
#         elif self.title == 'Шорты':
#             return self.short[0] * self.short[1]
#         elif self.title == 'Кроссовки':
#             return self.sneakers[0] * self.sneakers[1]
#         elif self.title == 'Перчатки':
#             return self.gloves[0] * self.gloves[1]

# shop1 = Shop('Майка')
# shop2 = Shop('Шорты')
# shop3 = Shop('Кроссовки')
# shop4 = Shop('Перчатки')
#
# print(shop1.calculate_discount())
# print(shop2.calculate_discount())
# print(shop3.calculate_discount())
# print(shop4.calculate_discount())

# ✅ Правильно:
class BaseProduct:
    def calculate_discount(self):
        return self.price * self.discount


class Tshirt(BaseProduct):
    price = 1000
    discount = 0.95


class Short(BaseProduct):
    price = 1500
    discount = 0.94


class Sneakers(BaseProduct):
    price = 5000
    discount = 0.9


class Gloves(BaseProduct):
    price = 800
    discount = 0.85


tshirt = Tshirt()
short = Short()
sneakers = Sneakers()
gloves = Gloves()

print(tshirt.calculate_discount())
print(short.calculate_discount())
print(sneakers.calculate_discount())
print(gloves.calculate_discount())

# Преимущества:
# 1) Классификация/Иерархия
# 2) Структуризация
# 3) Улучшение читаемости кода (+ уменьшение человеческого фактора)

# Недостатки:
# 1) Нарушение DRY
# 2) Увеличение объёма кода/классов
