# SOLID

# I - ISP - Interface Segregation Principle - Принцип разделения интерфейсов
# ISP - Пользователи не должны зависеть от методов которые они не используют
# ISP (моё) - много маленьких интерфейсов лучше, чем один большой


# ❌ Не правильно:
# class Player:
#     def play_music(self):
#         print('Играю музыку')
#
#     def view_album(self):
#         print('Вывод фотографии альбома на экранчик')
#
#     def equalizer(self):
#         print('Отображение эквалайзера')
#
#     def connect_other_music_station(self):
#         print('Подключение к другим музыкальным станциям')


# ✅ Правильно:
class MusicPlayer:
    def play_music(self):
        print('Играю музыку')


class Visual:
    def view_album(self):
        print('Вывод фотографии альбома на экранчик')


class Equalizer:
    def equalizer(self):
        print('Отображение эквалайзера')


class ConnectStation:
    def connect_other_music_station(self):
        print('Подключение к другим музыкальным станциям')


class Ipod(MusicPlayer, Equalizer, ConnectStation):
    pass

# Преимущества:
# 1) Масштабирование
# 2) Удобство чтения, тестирования, поддержки кода

# Недостатки:
# 1) Увеличение объёма кода/классов
# 2) KISS, YAGNI - при неудачном планировании