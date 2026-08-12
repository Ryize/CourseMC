from django.db import migrations


ASSIGNMENT_LABEL = '<p class="lesson-assignment-label">Задание:</p>'


ASSIGNMENT_TAILS = {
    40: '''
        <p class="lesson-assignment-label">Задание:</p>
        <p class="lesson-assignment-text">Напишите программу, которая по
        введённому радиусу вычисляет площадь и длину окружности. Сохраните
        результат в текстовый файл. Если вместо числа ввели текст, число
        меньше или равно нулю либо файл не удалось открыть, программа должна
        вывести понятное сообщение, а не завершиться с ошибкой.</p>
    ''',
    41: '''
        <p class="lesson-assignment-label">Задание:</p>
        <ol class="lesson-assignment-list">
            <li>Напишите функцию <code>greet(name)</code>, которая принимает
                имя и возвращает строку приветствия. Например,
                <code>greet('Маша')</code> возвращает «Привет, Маша!».</li>
            <li>Напишите две функции: <code>is_even(number)</code> возвращает
                <code>True</code>, если число делится на 2 без остатка, иначе
                <code>False</code>; <code>max_of_three(a, b, c)</code>
                возвращает наибольшее из трёх чисел.</li>
            <li>Напишите <code>sum_range(start, end)</code>, которая
                возвращает сумму всех целых чисел от первой границы до второй
                включительно. Если границы передали в обратном порядке,
                поменяйте их местами.</li>
        </ol>
    ''',
    42: '''
        <p class="lesson-assignment-label">Задание:</p>
        <p class="lesson-assignment-text">Напишите функцию
        <code>read_file_info(filename)</code>. <code>filename</code> — имя
        файла, например <code>notes.txt</code>. Функция должна вернуть
        расширение файла (для <code>notes.txt</code> это <code>txt</code>),
        количество строк и его содержимое. Если файла нет или у имени нет
        расширения, верните понятное сообщение вместо аварийного завершения
        программы.</p>
    ''',
    43: '''
        <p class="lesson-assignment-label">Задание:</p>
        <p class="lesson-assignment-text">Возьмите свою программу из
        предыдущих уроков и приведите её к PEP 8 — правилам читаемого кода на
        Python. Проверьте имена переменных и функций, отступы, пробелы,
        слишком длинные строки, порядок импортов и неиспользуемый код.
        Приложите версии «до» и «после» с коротким списком изменений.</p>
    ''',
    44: '''
        <p class="lesson-assignment-label">Задание:</p>
        <ol class="lesson-assignment-list">
            <li>Дима считает, что текст в круглых скобках читать не нужно.
                Напишите функцию <code>shortener(text)</code>, которая
                получает строку и возвращает её без фрагментов в круглых
                скобках и без самих скобок. Вложенных скобок учитывать не
                нужно. Например, из «Я изучаю Python (каждый день)» должно
                получиться «Я изучаю Python».</li>
            <li>Напишите функцию <code>camel(text)</code>, которая чередует
                регистр букв в строке: первая буква заглавная, следующая
                строчная и так далее. Пробелы, цифры и знаки препинания не
                участвуют в чередовании, но остаются в строке. Например,
                «привет, мир!» превращается в «ПрИвЕт, МиР!».</li>
        </ol>
    ''',
    45: '''
        <p class="lesson-assignment-label">Задание:</p>
        <ol class="lesson-assignment-list">
            <li>Напишите функцию <code>sum_range(start, end)</code>.
                <code>start</code> — начало диапазона, <code>end</code> —
                конец. Функция возвращает сумму всех целых чисел между ними
                включительно. Если начало больше конца, поменяйте значения
                местами.</li>
            <li>Напишите функцию <code>max_of_three(a, b, c)</code>, которая
                возвращает наибольшее из трёх переданных чисел.</li>
            <li>Напишите программу, которая считает количество дней между
                двумя датами. Дату храните как кортеж
                <code>(год, месяц, день)</code>. Для дат
                <code>(2014, 7, 2)</code> и <code>(2014, 7, 11)</code>
                результат равен 9.</li>
        </ol>
    ''',
    46: '''
        <p class="lesson-assignment-label">Задание:</p>
        <p class="lesson-assignment-text">Напишите функцию
        <code>is_prime(n: int) -&gt; bool</code>. Простое число — это целое
        число больше 1, которое делится без остатка только на 1 и на себя:
        7 — простое, а 8 — нет. Функция должна вернуть <code>True</code> для
        простого числа и <code>False</code> в остальных случаях. Затем
        напишите <code>main() -&gt; None</code>: она считывает число, вызывает
        <code>is_prime</code> и выводит результат. Поместите вызов
        <code>main()</code> под условие <code>if __name__ == '__main__'</code>,
        чтобы он выполнялся только при прямом запуске файла.</p>
    ''',
    47: '''
        <p class="lesson-assignment-label">Задание:</p>
        <ol class="lesson-assignment-list">
            <li>Напишите функцию, которая получает строку и возвращает
                количество заглавных и строчных букв. Для строки
                «Быстрая Лиса Бровей» ожидаемый результат: 3 заглавные и 14
                строчных букв.</li>
            <li>Напишите функцию, которая возвращает новый список без
                повторов, сохраняя порядок первого появления элементов.
                Например, из <code>[3, 1, 3, 2, 1]</code> получится
                <code>[3, 1, 2]</code>.</li>
        </ol>
    ''',
    48: '''
        <p class="lesson-assignment-label">Задание:</p>
        <ol class="lesson-assignment-list">
            <li>Напишите <code>is_in_range(number, start, end)</code>.
                Она возвращает <code>True</code>, если число находится между
                границами включительно, иначе <code>False</code>.</li>
            <li>Напишите <code>has_unique_items(items)</code>. Она возвращает
                <code>True</code>, если в списке нет повторяющихся элементов.</li>
            <li>Напишите <code>is_valid_password(password)</code>. Пароль
                считается подходящим, если в нём не менее 8 символов, есть
                хотя бы одна буква и хотя бы одна цифра.</li>
        </ol>
    ''',
    49: '''
        <p class="lesson-assignment-label">Задание:</p>
        <p class="lesson-assignment-text">Реализуйте игру «Угадай число».
        Программа загадывает число от 1 до 100, после каждой попытки сообщает
        «больше» или «меньше» и считает попытки. Если пользователь введёт
        слово <code>exit</code>, игра завершается. Вынесите отдельно
        генерацию числа, проверку ответа и запуск игры.</p>
    ''',
    50: '''
        <p class="lesson-assignment-label">Задание:</p>
        <p class="lesson-assignment-text">Напишите функцию
        <code>draw_stairs(height)</code>. <code>height</code> — высота
        лесенки от 1 до 20. Функция выводит строки из символов <code>#</code>:
        при высоте 3 это <code>#</code>, затем <code>##</code> и
        <code>###</code>.</p>
    ''',
    51: '''
        <p class="lesson-assignment-label">Задание:</p>
        <ol class="lesson-assignment-list">
            <li>Рекурсивно найдите сумму чисел от 1 до <code>n</code>.</li>
            <li>Рекурсивно вычислите факториал числа от 0 до 10. Факториал
                5 — это произведение чисел <code>1 × 2 × 3 × 4 × 5</code>,
                то есть 120.</li>
            <li>Рекурсивно вычислите число Фибоначчи с номером от 0 до 20:
                каждое следующее число равно сумме двух предыдущих.</li>
        </ol>
        <p class="lesson-assignment-text">Рекурсия — это вызов функцией самой
        себя. В комментарии к каждому решению укажите базовый случай — когда
        вызовы прекращаются, — и рекурсивный шаг.</p>
    ''',
    55: '''
        <p class="lesson-assignment-label">Задание:</p>
        <ol class="lesson-assignment-list">
            <li>Напишите свой декоратор — функцию, которая получает другую
                функцию и добавляет ей поведение. Выберите полезное действие:
                например, вывод имени функции или подсчёт количества её
                вызовов. Не используйте декоратор измерения времени и проверку
                на чётность.</li>
            <li>Напишите функцию сортировки списка по убыванию последней
                цифры числа: из <code>[691, 547]</code> должен получиться
                <code>[547, 691]</code>, потому что 7 больше 1. Для этой
                задачи добавьте отдельный декоратор, который запускает
                сортировку 100 раз и выводит среднее время выполнения.</li>
        </ol>
    ''',
    56: '''
        <p class="lesson-assignment-label">Задание:</p>
        <p class="lesson-assignment-text">Выберите две завершённые задачи из
        блока функций. Улучшите их: уберите повторяющийся код, разделите
        большую логику на небольшие функции, добавьте аннотации типов
        (подсказки, какие данные функция принимает и возвращает) и обработайте
        одну ожидаемую ошибку. Кратко опишите, что изменилось.</p>
    ''',
    58: '''
        <p class="lesson-assignment-label">Задание:</p>
        <ol class="lesson-assignment-list">
            <li>Создайте класс <code>Message</code> с полем текста.
                <code>to_upper()</code> должен возвращать текст в верхнем
                регистре, а <code>reverse_words()</code> — тот же текст со
                словами в обратном порядке.</li>
            <li>Создайте класс <code>Person</code> с именем и годом рождения.
                Добавьте метод, который по переданному текущему году возвращает
                возраст человека.</li>
        </ol>
    ''',
    59: '''
        <p class="lesson-assignment-label">Задание:</p>
        <p class="lesson-assignment-text">Создайте класс <code>Calculator</code>.
        При создании объекта передавайте начальное число в
        <code>__init__</code> — это специальный метод, который запускается
        автоматически при создании объекта. Добавьте методы сложения,
        вычитания, умножения и деления. При делении на ноль возвращайте
        понятное сообщение.</p>
    ''',
    60: '''
        <p class="lesson-assignment-label">Задание:</p>
        <p class="lesson-assignment-text">Создайте общий класс
        <code>Figure</code> и классы <code>Rectangle</code>,
        <code>Circle</code> и <code>Triangle</code>, которые наследуют его.
        Для каждой фигуры реализуйте расчёт площади и периметра. Не разрешайте
        создавать фигуру с отрицательными размерами.</p>
    ''',
    61: '''
        <p class="lesson-assignment-label">Задание:</p>
        <p class="lesson-assignment-text">Расширьте программу с фигурами
        классами <code>Square</code>, <code>Ellipse</code> и
        <code>EquilateralTriangle</code>. Добавьте общий метод
        <code>describe()</code>, который возвращает понятное описание своей
        фигуры. Поместите разные фигуры в один список и вызовите этот метод у
        каждой — так вы покажете полиморфизм.</p>
    ''',
    62: '''
        <p class="lesson-assignment-label">Задание:</p>
        <p class="lesson-assignment-text">Создайте класс <code>Soldier</code>
        с именем, званием и служебным номером. Храните звание и номер как
        внутренние поля объекта, а доступ к ним дайте через свойства
        <code>rank</code> и <code>service_number</code>. При изменении
        проверяйте, что звание и номер не пустые.</p>
    ''',
    63: '''
        <p class="lesson-assignment-label">Задание:</p>
        <p class="lesson-assignment-text">Добавьте к программе с фигурами
        специальные методы: <code>__str__</code> для понятного вывода через
        <code>print()</code>, <code>__repr__</code> для технического
        представления объекта и <code>__eq__</code> для сравнения двух фигур.
        Фигуры равны, если у них совпадают тип и размеры.</p>
    ''',
    64: '''
        <p class="lesson-assignment-label">Задание:</p>
        <p class="lesson-assignment-text">Создайте класс <code>Candy</code>
        с названием, ценой за килограмм и весом. Создайте два подкласса с
        дополнительными свойствами. Добавьте метод, который по заданному весу
        партии возвращает её стоимость.</p>
    ''',
    65: '''
        <p class="lesson-assignment-label">Задание:</p>
        <p class="lesson-assignment-text">Создайте абстрактный класс
        <code>PaymentMethod</code> с общим методом оплаты и два конкретных
        способа оплаты, например картой и наличными. Создайте
        <code>Order</code>: он хранит товары, считает сумму и принимает
        объект способа оплаты. Сам заказ не должен знать, как именно проходит
        оплата — он только вызывает общий метод.</p>
    ''',
    66: '''
        <p class="lesson-assignment-label">Задание:</p>
        <p class="lesson-assignment-text">Спроектируйте небольшую систему из
        трёх связанных классов: например, «книга — автор — библиотека» или
        «курс — урок — ученик». Для каждого класса определите только нужные
        данные и действия. Объясните в комментарии, за что отвечает каждый
        класс.</p>
    ''',
    67: '''
        <p class="lesson-assignment-label">Задание:</p>
        <p class="lesson-assignment-text">Создайте класс <code>BankAccount</code>
        с текущим балансом и историей операций. Добавьте пополнение, снятие и
        перевод между счетами. Не разрешайте вносить или снимать нулевую и
        отрицательную сумму, а также снимать больше денег, чем есть на
        балансе.</p>
    ''',
    68: '''
        <p class="lesson-assignment-label">Задание:</p>
        <p class="lesson-assignment-text">Для <code>BankAccount</code> или
        другого класса из ООП-блока напишите минимум четыре теста: обычный
        успешный сценарий, граничный случай, неверный ввод и проверку, что
        после ошибки состояние объекта не изменилось. Например, после
        неудачной попытки снять слишком большую сумму баланс должен остаться
        прежним.</p>
    ''',
    69: '''
        <p class="lesson-assignment-label">Задание:</p>
        <p class="lesson-assignment-text">Протестируйте методы выбранного
        класса. Используйте <code>setUp</code> — метод, который запускается
        перед каждым тестом и создаёт общие данные. Дайте тестам понятные имена
        и в каждом тесте проверяйте один ожидаемый результат.</p>
    ''',
    70: '''
        <p class="lesson-assignment-label">Задание:</p>
        <p class="lesson-assignment-text">Добавьте пять новых тестов к
        проекту из ООП-блока. Минимум один тест должен проверять неправильный
        ввод или ошибку, а ещё один — совместную работу двух объектов,
        например перевод между двумя банковскими счетами.</p>
    ''',
    71: '''
        <p class="lesson-assignment-label">Задание:</p>
        <ol class="lesson-assignment-list">
            <li>Напишите функцию, которая принимает три числа и возвращает их
                по возрастанию — от меньшего к большему.</li>
            <li>Напишите функцию сокращения дроби <code>m/n</code>. Например,
                дробь <code>6/8</code> должна превратиться в <code>3/4</code>.</li>
            <li>Для обеих функций напишите тесты на обычные значения,
                граничные случаи (например, одинаковые числа) и неверные
                данные.</li>
        </ol>
    ''',
    72: '''
        <p class="lesson-assignment-label">Задание:</p>
        <p class="lesson-assignment-text">Добавьте в <code>BankAccount</code>
        собственные классы ошибок <code>InvalidAmountError</code> и
        <code>InsufficientFundsError</code>. Первую ошибку вызывайте для
        нулевой или отрицательной суммы, вторую — когда денег на счёте не
        хватает. Используйте их при пополнении, снятии и переводе, затем
        добавьте тесты.</p>
    ''',
    73: '''
        <p class="lesson-assignment-label">Задание:</p>
        <p class="lesson-assignment-text">Создайте UML-диаграмму классов
        итогового проекта — схему, где каждый класс показан отдельным блоком.
        Укажите названия классов, важные поля, методы и связи между объектами.
        Диаграмма должна соответствовать написанному коду.</p>
    ''',
    74: '''
        <p class="lesson-assignment-label">Задание:</p>
        <p class="lesson-assignment-text">Проведите финальную доработку
        проекта: уберите повторяющийся код, разделите слишком большие методы,
        проверьте, что внутренние данные объектов не меняются напрямую, и
        обновите тесты. В конце составьте короткий список важных решений,
        которые вы приняли в архитектуре проекта.</p>
    ''',
    75: '''
        <p class="lesson-assignment-label">Задание:</p>
        <p class="lesson-assignment-text">Создайте локальную базу SQLite и
        таблицу <code>students</code> с 4–5 полями, например именем, почтой и
        датой регистрации. Добавьте и удалите один столбец, затем удалите
        учебную таблицу-копию. Используйте SQLite: отдельный сервер базы
        данных устанавливать не нужно.</p>
    ''',
    76: '''
        <p class="lesson-assignment-label">Задание:</p>
        <p class="lesson-assignment-text">Заполните таблицу минимум пятью
        записями и выполните CRUD-операции: <code>INSERT</code> — добавить
        запись, <code>SELECT</code> — получить записи с фильтром и
        сортировкой, <code>UPDATE</code> — изменить запись,
        <code>DELETE</code> — удалить запись. Структуру таблицы на этом уроке
        не меняйте.</p>
    ''',
    77: '''
        <p class="lesson-assignment-label">Задание:</p>
        <p class="lesson-assignment-text">Создайте таблицы
        <code>students</code>, <code>courses</code> и <code>enrollments</code>.
        Последняя таблица должна связывать ученика и курс через внешние ключи
        — поля со ссылками на записи других таблиц. Выполните запрос с
        <code>JOIN</code>, который объединит сведения из таблиц. Затем
        добавьте индекс для поля, по которому часто ищете, и объясните, какой
        запрос он ускоряет.</p>
    ''',
    78: '''
        <p class="lesson-assignment-label">Задание:</p>
        <p class="lesson-assignment-text">На таблице платежей или оценок
        выполните запросы: <code>COUNT</code> — посчитать записи,
        <code>SUM</code> — найти сумму, <code>AVG</code> — среднее значение,
        <code>GROUP BY</code> — объединить записи в группы и
        <code>HAVING</code> — отфильтровать готовые группы. Для каждого
        запроса дайте понятное имя столбцу и подпишите, на какой вопрос он
        отвечает.</p>
    ''',
}


def _replace_assignment(materials, assignment_html):
    label_index = materials.find(ASSIGNMENT_LABEL)
    if label_index == -1:
        return materials

    quiz_index = materials.find('<p data-quiz-id=', label_index)
    trailing_content = materials[quiz_index:] if quiz_index != -1 else ''
    return f'{materials[:label_index]}{assignment_html.strip()}{trailing_content}'


def clarify_beginner_assignments(apps, schema_editor):
    DirectionStudy = apps.get_model('Course', 'DirectionStudy')
    Schedule = apps.get_model('Course', 'Schedule')
    backend_direction = DirectionStudy.objects.filter(title='Backend 2024').first()
    if not backend_direction:
        return

    schedules = Schedule.objects.filter(
        direction_id=backend_direction.pk,
        position__in=ASSIGNMENT_TAILS,
    )
    for schedule in schedules:
        materials = _replace_assignment(
            schedule.lesson_materials or '',
            ASSIGNMENT_TAILS[schedule.position],
        )
        if materials != schedule.lesson_materials:
            schedule.lesson_materials = materials
            schedule.save(update_fields=('lesson_materials',))


class Migration(migrations.Migration):

    dependencies = [
        ('Course', '0013_number_helpful_materials'),
    ]

    operations = [
        migrations.RunPython(
            clarify_beginner_assignments,
            migrations.RunPython.noop,
        ),
    ]
