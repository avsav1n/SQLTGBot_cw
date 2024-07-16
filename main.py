'''
Основной модуль, описывающий логику работы Telegram-бота
и его взаимодействия с базой данных PostgreSQL.

'''
from random import shuffle, choice, sample, randint
from datetime import date, timedelta

from telebot import types, TeleBot
from telebot.storage import StateMemoryStorage
from telebot.handler_backends import State, StatesGroup
from sqlalchemy import distinct

from models import Word, Study, User, DBaseConfig
from config import TGBOT_TOKEN
from cash_func import cash_func

# BACKEND_INFO - оперативный словарь.
# Хранит информацию о количестве частей речи, находящихся в базе данных (для подготовки карточек)
# и данные о языке отображаемых карточек (ru-en, en-ru) для каждого пользователя.
# Информация хранится в виде:
# {'types': [id_type_1, id_type_2...], chat_id_1: 'russian', chat_id_2: 'english',...}
BACKEND_INFO = {}

class DBase:
    '''Статический класс для работы с базой данных PostgreSQL.

       Для взаимодействия с базой данных необходимо в файл .config ввести параметры подключения.
       
    '''
    @cash_func
    @staticmethod
    def _pulling_info_word_id(word: str, chat_id: int) -> int:
        '''Функция выборки идентификатора слова (id_word) из таблицы "word".
           Возвращает id_word.

        '''
        return (
            session.query(Word).filter(Word.title == word).first().id_word
            if BACKEND_INFO[chat_id] == 'english' else
            session.query(Word).filter(Word.translation == word).first().id_word
            )

    @cash_func
    @staticmethod
    def _pulling_info_user_id(chat_id: int) -> int:
        '''Функция выборки идентификатора пользователя (id_user) из таблицы "user".
           Возвращает id_user.

        '''
        return session.query(User).filter(User.id_chat == chat_id).first().id_user

    @staticmethod
    def planning_for_today() -> dict:
        '''Функция выборки информации об идентификаторе чата пользователей (id_chat) 
           и слов (id_word) из таблицы "study", соответствующие условию: добавлены 
           в персональный список ранее текущей даты.
           Возвращает словарь: {id_chat: [id_word, id_word...], id_chat:...}

           Используется при подключении модуля 'notifications.py'.

        '''
        query = session.query(Study).with_entities(User.id_chat, Study.id_word)\
                       .join(User.study).filter(Study.date < date.today()).all()
        if query:
            return {key[0]:[value[1] for value in query if value[0] == key[0]]for key in query}

    @staticmethod
    def pull_out_schedule_words_for_cards(word_id: int) -> list:
        '''Функция выборки целевого и вспомогательных слов для карточек.
           Язык целевого слова выбирается случайным образом.
           Возвращает кортеж из целевого слова, его перевода, кортежа из слов-вариантов 
           перевода и флага-индикатора выбранного языка (0 - 'english', 1 - 'ru-en):
           (word_title, word_translation, [word_translation,...], flag) или
           (word_translation, word_title, [word_title,...], flag).

           Используется при подключении модуля 'notifications.py'.

        '''
        type_id, *target_word = session.query(Word)\
                                       .with_entities(Word.id_type, Word.title, Word.translation)\
                                       .filter(Word.id_word == word_id).all()[0]
        other_words = session.query(Word).with_entities(Word.title, Word.translation)\
                             .filter(Word.id_type == type_id).all()
        other_words = sample(other_words, k=3)
        flag = randint(1, 100) % 2
        target_word, target_word_transl = target_word[flag], target_word[1 - flag]
        words_transl = [word[1 - flag] for word in other_words] + [target_word_transl]
        shuffle(words_transl)
        return target_word, target_word_transl, words_transl, flag

    @staticmethod
    def postpone_date(word_id: int) -> None:
        '''Функция смены даты слова в таблице "study".
           Откладывание осуществляется на 3-и дня
        
        '''
        session.query(Study).filter(Study.id_word == word_id)\
               .update({'date': date.today() + timedelta(3)})
        session.commit()

    @staticmethod
    def pull_out_user_words(chat_id:int)-> list:
        '''Функция выборки персональных слов из таблицы "study", 
           принадлежащих конкретному пользователю.
           Возвращает список: [(word_title, word_translation),...]
        
        '''
        user_id = DBase._pulling_info_user_id(chat_id)
        return session.query(Study).with_entities(Word.title, Word.translation)\
                        .join(Word.study).filter(Study.id_user == user_id).all()

    @staticmethod
    def filling_backend_info_words()-> list:
        '''Функция выборки всех уникальных значений id_type из таблицы "word".
           Возвращает список: [id_type, id_type,...]
           Используется для заполнения оперативного словаря BACKEND_INFO.

        '''
        total = session.query(Word).with_entities(distinct(Word.id_type)).all()
        return [i[0] for i in total]

    @staticmethod
    def filling_backend_info_users() -> dict:
        '''Функция выборки всех идентификаторов чата (id_chat) и используемого 
           языка карточек (language).
           Возвращает словарь: {id_chat: language,...}
           Используется для заполнения оперативного словаря BACKEND_INFO.
        
        '''
        return dict(session.query(User.id_chat, User.language).all())

    @staticmethod
    def add_new_user(chat_id: int) -> None:
        '''Функция добавления нового пользователя.
           Добавляет пользователя в таблицу "user" и обновляет оперативный словарь BACKEND_INFO.
        
        '''
        model = User(id_chat=chat_id, language='english')
        session.add(model)
        session.commit()
        BACKEND_INFO.update({chat_id: 'english'})

    @staticmethod
    def change_language(chat_id: int) -> None:
        '''Функция смены языка карточек.
           Измененяет значения языка пользователя в таблице "user" и
           обновляет оперативный словарь BACKEND_INFO.

        '''
        options = {'english':'russian', 'russian': 'english'}
        session.query(User).filter(User.id_chat == chat_id)\
               .update({'language': options[BACKEND_INFO[chat_id]]})
        session.commit()
        BACKEND_INFO[chat_id] = options[BACKEND_INFO[chat_id]]

    @staticmethod
    def pull_out_words_for_cards(chat_id: int) -> list:
        '''Функция выборки четырех слов для карточек.
           Язык целевого слова выбирается в зависимости от языка 
           пользователя (language) таблицы "user".
           Возвращает кортеж из целевого слова, его перевода, списка из слов-вариантов перевода:
           (word_title, word_translation, [word_translation,...]) или
           (word_translation, word_title, [word_title,...]).

        '''
        words = session.query(Word)\
                        .with_entities(Word.title, Word.translation)\
                        .filter(Word.id_type == choice(BACKEND_INFO['types'])).all()
        words = sample(words, k=4)
        match BACKEND_INFO[chat_id]:
            case 'english':
                target_word, *words_transl = (words[i] if not i else words[i][1] for i in range(4))
                target_word, target_word_transl = target_word
            case 'russian':
                target_word, *words_transl = (words[i] if not i else words[i][0] for i in range(4))
                target_word_transl, target_word = target_word
        words_transl.append(target_word_transl)
        shuffle(words_transl)
        return target_word, target_word_transl, words_transl

    @staticmethod
    def add_word(target_word: str, chat_id: int) -> None:
        '''Функция добавления слова в персональный список пользователя.
           Добавляет слово в таблицу "study".
        
        '''
        word_id = DBase._pulling_info_word_id(target_word, chat_id)
        user_id = DBase._pulling_info_user_id(chat_id)
        model = Study(id_word=word_id, id_user=user_id, date=date.today() + timedelta(3))
        session.add(model)
        session.commit()

    @staticmethod
    def del_word(target_word: str, chat_id: int) -> None:
        '''Функция удаления слова из персонального списка пользователя.
           Удаляет слово из таблицы "study".
        
        '''
        word_id = DBase._pulling_info_word_id(target_word, chat_id)
        user_id = DBase._pulling_info_user_id(chat_id)
        session.query(Study).filter(Study.id_word == word_id)\
                            .filter(Study.id_user == user_id).delete()
        session.commit()

    @staticmethod
    def is_in_study(target_word: str, chat_id: int) -> bool:
        '''Функция проверки наличия целевого слова в персональном списке пользователя.
           Возвращает логическое значение:
               True - отображается кнопка 'Удалить 🗑';
               False - отображается кнопка 'Добавить ➕'.

        '''
        word_id = DBase._pulling_info_word_id(target_word, chat_id)
        user_id = DBase._pulling_info_user_id(chat_id)
        try:
            session.query(Study).filter(Study.id_user == user_id)\
                   .filter(Study.id_word == word_id).first().id_study
            return True
        except AttributeError:
            return False


class RegisterStates(StatesGroup):
    '''Класс регистрации состояний Telegram-бота, 
       для их использования в функциях-обработчиках.

    '''
    target_word = State()
    target_word_transl = State()
    words_transl = State()
    target_word_message= State()


class Extentions:
    '''Класс дополнительных возможностей: регистрация кнопок пользователя для 
       интерфейса Telegram-бота и некоторые вспомогательные функции.

    '''
    add_word = types.KeyboardButton('Добавить \U00002795')
    del_word = types.KeyboardButton('Удалить \U0001F5D1')
    next_cards = types.KeyboardButton('Следующее \U000023E9')
    ru_en_change = types.KeyboardButton('\U0001F1F7\U0001F1FA Сменить \U0001F1EC\U0001F1E7')
    en_ru_change = types.KeyboardButton('\U0001F1EC\U0001F1E7 Сменить \U0001F1F7\U0001F1FA')
    show_users_list = types.KeyboardButton('Ваши слова \U0001F9E0')
    im_ready = types.KeyboardButton('Поехали! \U0001F680')

    @staticmethod
    def random_phrase_win() -> str:
        '''Функция возвращает произвольную фразу
           в случае правильного ответа пользователя.

        '''
        answer_options = (
            'Да, Вы правы \U0001F44D', 'Так держать \U0001F44F',
            'Точно! \U0001F4AA', 'Прекрасно \U0001F973', 'В точку \U0001F4AF',
            'Верно \U00002705'
        )
        return choice(answer_options)

    @staticmethod
    def random_phrase_lose() -> str:
        '''Функция возвращает произвольную фразу
           в случае неверного ответа пользователя.

        '''
        answer_options = (
            'К сожалению нет \U0001F648', 'Ответ неверный \U0000274C',
            'Не расстраивайтесь, попробуйте еще раз \U0001F9DE', 'Почти угадали \U0001F40C',
            'Тут даже я бы ошибся \U0001F937', 'Сосредоточьтесь \U0001F9A5'
        )
        return choice(answer_options)


class Telebot:
    '''Статический класс для обработки сообщений Telegram-бота.

       Для инициализации класса необходимо в файл .config ввести имеющийся токен.
    
    '''
    bot = TeleBot(TGBOT_TOKEN, state_storage=StateMemoryStorage())

    @staticmethod
    @bot.message_handler(func=lambda message: message.text == Extentions.im_ready.text)
    def show_schedule_cards(message) -> None:
        '''Функция-обработчик сообщения 'Поехали! 🚀'
           Формирует интерфейс взаимодействия с пользователем, возвращает в чат
           карточки (составлены из целевого слова из персонального списка и 3-х случайных)
           Обработка ответа осуществляется функцией check_response.

           Используется при подключении модуля 'notifications.py'.

        '''
        info = DBase.planning_for_today()
        if not info:
            return
        for chat_id in info:
            target_word_id = choice(info[chat_id])
            tmp = DBase.pull_out_schedule_words_for_cards(target_word_id)
            target_word, target_word_transl, words_transl, flag = tmp

            start_cards_message = (
                f'\U0001F1F7\U0001F1FA {target_word.upper()}'
                if flag else
                f'\U0001F1EC\U0001F1E7 {target_word.upper()}'
                )

            words_buttons = (types.KeyboardButton(word) for word in words_transl)
            markup_repl = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
            markup_repl.add(*words_buttons)

            markup_repl.add(Extentions.next_cards)
            markup_repl.add(Extentions.del_word)

            Telebot.bot.set_state(message.from_user.id,
                                RegisterStates.target_word_transl, message.chat.id)
            with Telebot.bot.retrieve_data(message.from_user.id, message.chat.id) as data:
                data['target_word_transl'] = target_word_transl
                data['target_word'] = target_word
                data['words_transl'] = words_transl
                data['target_word_message'] = start_cards_message

            Telebot.bot.send_message(message.chat.id, start_cards_message, reply_markup=markup_repl)
            DBase.postpone_date(target_word_id)

    @staticmethod
    @bot.message_handler(func=lambda message: message.text == Extentions.next_cards.text)
    def next_cards(message) -> None:
        '''Функция-обработчик сообщения 'Следующее ⏩'.
           Осуществляет переход к следующей карточке.

        '''
        Telebot.show_cards(message)

    @staticmethod
    @bot.message_handler(func=lambda message: message.text == Extentions.del_word.text)
    def del_word(message) -> None:
        '''Функция-обработчик сообщения 'Удалить 🗑'..
           Удаляет целевое слово из персонального списка пользователя.
           Возвращает в чат уведомление о результатах выполнения.
        
        '''
        try:
            with Telebot.bot.retrieve_data(message.from_user.id, message.chat.id) as data:
                target_word = data['target_word']
        except KeyError:
            Telebot.bot.send_message(message.chat.id,
                                     'Извиняюсь, отвлекся \U0001F648')
            Telebot.show_cards(message)
            return
        DBase.del_word(target_word, message.chat.id)
        Telebot.bot.send_message(message.chat.id,
                                    f'Слово {target_word.upper()} удалено из '
                                    'Вашего персонального списка! \U0001F4A9')
        Telebot.show_cards(message)

    @staticmethod
    @bot.message_handler(func=lambda message: message.text == Extentions.add_word.text)
    def add_word(message) -> None:
        '''Функция-обработчик сообщения 'Добавить ➕'.
           Добавляет целевое слово в персональный список пользователя.
           Возвращает в чат уведомление о результатах выполнения.

        '''
        try:
            with Telebot.bot.retrieve_data(message.from_user.id, message.chat.id) as data:
                target_word = data['target_word']
                target_word_transl = data['target_word_transl']
        except KeyError:
            Telebot.bot.send_message(message.chat.id,
                                     'Простите, сплю на ходу \U0001F634')
            Telebot.show_cards(message)
            return

        DBase.add_word(target_word, message.chat.id)

        Telebot.bot.send_message(message.chat.id,
                                 'Запомните, а то забудете!\U0001F9D0\n')
        if BACKEND_INFO[message.chat.id] == 'english':
            reply_message = (f'\U0001F1EC\U0001F1E7 {target_word.upper()} '
                             f'\U00002194 {target_word_transl} \U0001F1F7\U0001F1FA')
        else:
            reply_message = (f'\U0001F1F7\U0001F1FA {target_word.upper()} '
                             f'\U00002194 {target_word_transl} \U0001F1EC\U0001F1E7 ')
        Telebot.bot.send_message(message.chat.id, reply_message)
        Telebot.bot.send_message(message.chat.id,
                                 'Слово добавлено в персональный список, '
                                 'я пришлю уведомление когда придет \U000023F0 его повторить')
        Telebot.show_cards(message)

    @staticmethod
    @bot.message_handler(func=lambda message: message.text == Extentions.show_users_list.text)
    def show_users_word(message) -> None:
        '''Функция-обработчик сообщения 'Ваши слова 🧠'.
           Возвращает в чат слова из персонального списка пользователя.

        '''
        words = DBase.pull_out_user_words(message.chat.id)
        if words:
            Telebot.bot.send_message(message.chat.id,
                                     'Изучаемые Вами слова: \U0001F4D6')
            user_words_message = '`'
            for pair in words:
                row = f'{pair[0].upper():>10} \U0001F501 {pair[1]:<10}\n'
                user_words_message += row
            Telebot.bot.send_message(message.chat.id,
                                     user_words_message + '`',
                                     parse_mode='Markdown')
        else:
            Telebot.bot.send_message(message.chat.id,
                                     'В настоящий момент Ваш персональный список пуст \U0001F573')

    @staticmethod
    @bot.message_handler(func=lambda message: message.text
                         in (Extentions.ru_en_change.text, Extentions.en_ru_change.text))
    def change_language(message) -> None:
        '''Функция-обработчик сообщений 'RU Сменить EN' и 'EN Сменить RU'.
           Меняет язык отображаемых в чате карточек.

        '''
        DBase.change_language(message.chat.id)
        Telebot.show_cards(message)

    @staticmethod
    @bot.message_handler(commands=['start'])
    def greeting(message) -> None:
        '''Функция-обработчик команды /start.
           Выполняет регистрацию, возвращает в чат приветствие пользователя.

        '''
        if message.chat.id not in BACKEND_INFO:
            DBase.add_new_user(message.chat.id)
        greeting_message = (
            'Доброго времени суток! \U0001F44B\n'
            'Я - бот \U0001F916, обучающий английскому лексикону \U0001F468\U0000200D\U0001F393\n'
            )
        faq_message = (
            'Для получения информации \U0001F4AC\nвведите /help\n'
            'Для начала обучения \U0001F4DA\nвведите /cards\n'
            'или просто используйте кнопки \U0001F447'
            )

        url = 'https://github.com/avsav1n/SQLTGBot_cw'
        markup_inl = types.InlineKeyboardMarkup()
        markup_inl.add(types.InlineKeyboardButton('Репозиторий в GitHub \U0001F40D', url=url))

        Telebot.bot.send_message(message.chat.id, greeting_message, reply_markup=markup_inl)

        markup_repl = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup_repl.add(types.KeyboardButton('/cards'))
        markup_repl.add(types.KeyboardButton('/help'))

        Telebot.bot.send_message(message.chat.id, faq_message, reply_markup=markup_repl)

    @staticmethod
    @bot.message_handler(commands=['help'])
    def help(message) -> None:
        '''Функция-обработчик команды /help.
           Возвращает в чат информацию о функционале Telegram-бота.

        '''
        help_message = (
            'Как уже было сказано ранее, я - бот \U0001F916, обучающий английскому лексикону.\n'
            'Обучение проходит в формате теста - я предлагаю \U0001F1EC\U0001F1E7 слово, Ваша '
            'задача выбрать его перевод на \U0001F1F7\U0001F1FA (или наоборот, язык отображения '
            'карточек Вы можете выбрать самостоятельно (\U0001F4CCСменить)) из четырех '
            'предложенных вариантов.\nТакже, за каждым пользователем закреплен список изучаемых '
            'в данный момент слов. Если в процессе обучения Вы наткнетесь на незнакомое слово '
            '\U0001F92F, Вы можете добавить (\U0001F4CCДобавить) его в персональный список (или '
            'нажать (\U0001F4CCСледующее)). При наличии слов в списке, Вам будут высылаться уведо'
            'мления для их повторения: одно случайное слово раз в день. Одно то же слово не будет'
            ' повторяться чаще одного раза в 4-е дня.'
            'Если в процессе обучения Вам повторно попадется слово, находящееся в Вашем персонал'
            'ьном списке, у Вас появится возможность его удалить из него (\U0001F4CCУдалить). '
            'При очень большом желании я также могу показать все изучаемые Вами в данный'
            ' момент слова, для этого в процессе обучения нажмите на (\U0001F4CCВаши слова).\n'
            'Давайте уже начнем! \U0001F609'
            )
        markup_repl = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup_repl.add('/cards')

        Telebot.bot.send_message(message.chat.id, help_message, reply_markup=markup_repl)

    @staticmethod
    @bot.message_handler(commands=['cards'])
    def show_cards(message) -> None:
        '''Функция-обработчик команды /cards.
           Формирует интерфейс взаимодействия с пользователем, 
           возвращает в чат карточки (составлены из 4-х случайных слов).
           Обработка ответа осуществляется функцией check_response.

        '''
        tmp = DBase.pull_out_words_for_cards(message.chat.id)
        target_word, target_word_transl, words_transl = tmp
        start_cards_message = (
            f'\U0001F1EC\U0001F1E7 {target_word.upper()}'
            if BACKEND_INFO[message.chat.id] == 'english' else
            f'\U0001F1F7\U0001F1FA {target_word.upper()}'
            )

        words_buttons = (types.KeyboardButton(word) for word in words_transl)
        markup_repl = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
        markup_repl.add(*words_buttons)

        markup_repl.add(Extentions.next_cards)
        if DBase.is_in_study(target_word, message.chat.id):
            markup_repl.add(Extentions.del_word)
        else:
            markup_repl.add(Extentions.add_word)

        if BACKEND_INFO[message.chat.id] == 'english':
            markup_repl.row(Extentions.show_users_list, Extentions.en_ru_change)
        else:
            markup_repl.row(Extentions.show_users_list, Extentions.ru_en_change)

        Telebot.bot.set_state(message.from_user.id,
                              RegisterStates.target_word_transl, message.chat.id)
        with Telebot.bot.retrieve_data(message.from_user.id, message.chat.id) as data:
            data['target_word_transl'] = target_word_transl
            data['target_word'] = target_word
            data['words_transl'] = words_transl
            data['target_word_message'] = start_cards_message

        Telebot.bot.send_message(message.chat.id, start_cards_message, reply_markup=markup_repl)

    @staticmethod
    @bot.message_handler(content_types=['text'])
    def check_response(message) -> None:
        '''Функция-обработчик любых текстовых сообщений. 
           Осуществляет проверку ответа пользователя на сгенерированнуе в функциях
           show_cards и show_schedule_cards карточку.
           Возвращает в чат уведомление о результатах выполнения.
        
        '''
        user_word = message.text
        try:
            with Telebot.bot.retrieve_data(message.from_user.id, message.chat.id) as data:
                target_word_transl = data['target_word_transl']
                words_transl = data['words_transl']
                start_cards_message = data['target_word_message']
        except KeyError:
            Telebot.bot.send_message(message.chat.id,
                                     'Простите, уснул \U0001F4A4 , продолжаем...')
            Telebot.show_cards(message)
            return
        if user_word in words_transl:
            if target_word_transl == user_word:
                Telebot.bot.send_message(message.chat.id,
                                        Extentions.random_phrase_win())
                Telebot.show_cards(message)
            else:
                Telebot.bot.send_message(message.chat.id,
                                        Extentions.random_phrase_lose())
                Telebot.bot.send_message(message.chat.id, start_cards_message)
        else:
            Telebot.bot.send_message(message.chat.id,
                                     'Выберите пожалуйста ответ из предложенных '
                                     'вариантов \U0001F9CF')
            Telebot.bot.send_message(message.chat.id, start_cards_message)


if __name__ == '__main__':
    session = DBaseConfig.Session()
    BACKEND_INFO = DBase.filling_backend_info_users()
    BACKEND_INFO['types'] = DBase.filling_backend_info_words()
    try:
        print('Bot is running...')
        Telebot.bot.infinity_polling(skip_pending=True)
    finally:
        print('Bot stopped.')
        session.close()
        print('Session closed.')
