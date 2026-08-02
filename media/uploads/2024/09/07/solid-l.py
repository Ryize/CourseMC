# SOLID

# L - LSP - Liskov substitution principle - Принцип подстановки Барбары Лисков
# LSP - Дочерние классы должны иметь возможность замещать другие дочерние
# классы и родительский класс без ущерба функциональности.

# ❌ Не правильно:
# class Weapon:
#     def shoot(self):
#         print('Стреляю')
#
#     def hit(self):
#         print('Удар прикладом')
#
#     def reload(self):
#         print('Перезарядка')
#
#
# class Pistol(Weapon):
#     def hit(self):
#         print('Удар рукоятью')
#
#
# class AK47(Weapon):
#     pass
#
#
# class Bazooka(Weapon):
#     def hit(self):
#         print('Удар трубой')
#
#     def reload(self):
#         print('Долгая перезарядка')
#
#
# class Knife(Weapon):
#     def shoot(self):
#         print('Кинул нож')
#
#     def hit(self):
#         print('Бью ножом')
#
#     def reload(self):
#         raise NotImplementedError('Метод невозможен в данном классе')
#
#
# class Grenade(Weapon):
#     def shoot(self):
#         print('Кинул гранату')
#
#     def hit(self):
#         print('Удар гранатой')
#
#     def reload(self):
#         raise NotImplementedError('Метод невозможен в данном классе')


# ✅ Правильно:
class HotWeapon:
    def shoot(self):
        print('Стреляю')

    def hit(self):
        print('Удар прикладом')

    def reload(self):
        print('Перезарядка')


class SteelWeapon:
    def shoot(self):
        print('Кидаю оружие')

    def hit(self):
        print('Удар оружием')


class AdditionalWeapon:
    def shoot(self):
        print('Кидаю оружие')



class Pistol(HotWeapon):
    def hit(self):
        print('Удар рукоятью')


class AK47(HotWeapon):
    pass


class Bazooka(HotWeapon):
    def hit(self):
        print('Удар трубой')

    def reload(self):
        print('Долгая перезарядка')


class Knife(SteelWeapon):
    def shoot(self):
        print('Кинул нож')

    def hit(self):
        print('Бью ножом')


class Grenade(AdditionalWeapon):
    def shoot(self):
        print('Кинул гранату')


# Преимущества:
# 1) Возможность гибкого масштабирования
# 2) Сохранение полиморфизма
# 3) Предсказуемость кода

# Недостатки:
# 1) Увеличение объёма кода/классов
# YAGNI - You arent gona need it
# KISS - Keep it simple stupid
