'''
Основной модуль, описывающий логику работы Telegram-бота
и его взаимомействия с базой данных PostgreSQL
'''
from random import shuffle, choice
from datetime import datetime

from telebot import types, TeleBot
from telebot.storage import StateMemoryStorage
from telebot.handler_backends import State, StatesGroup

from models import Word, Study, User, DBaseConfig
from config import TGBOT_TOKEN

BACKEND_INFO = {}

class DBase:
    '''Статический класс для работы с базой данных PostgreSQL.

       База данных хранит информацию об английских словах, их частях речи, переводе на русский,
       а также информацию о чате для дальнейшего общения с пользователем.
       Для взаимодействия с базой данных необходимо в файл .config ввести параметры подключения.
       
    '''

    @staticmethod
    def _pulling_info(word, chat_id):
        '''Функция выборки идентификаторов слова (id_word) из таблицы "word" и
           пользователя (id_user) из таблицы "user".

        '''
        word_id = (
            session.query(Word).filter(Word.title == word).first().id_word
            if BACKEND_INFO[chat_id] == 'en-ru' else
            session.query(Word).filter(Word.translation == word).first().id_word
            )
        user_id = session.query(User).filter(User.id_chat == chat_id).first().id_user
        return word_id, user_id

    @staticmethod
    def pulling_out_user_words(chat_id):
        '''Функция выборки персональных слов из таблицы "study".
        
        '''
        user_id = session.query(User).filter(User.id_chat == chat_id).first().id_user
        return session.query(Study).with_entities(Word.title, Word.translation)\
                        .join(Word.study).filter(Study.id_user == user_id).all()

    @staticmethod
    def filling_backend_info_words():
        '''Функция добавления в словарь BACKEND_INFO имеющейся в базе данных
           информацией о количестве групп слов, принадлежащих к разным частям 
           речи: {'types': [id_type_1, id_type_2...]}.

        '''
        total = session.query(Word).with_entities(Word.id_type).group_by(Word.id_type).all()
        return [i[0] for i in total]

    @staticmethod
    def filling_backend_info_users():
        '''Функция заполнения словаря BACKEND_INFO имеющейся в базе данных
           информацией о пользователях, которые ранее взаимодействовали с Telegram-ботом.
           BACKEND_INFO содержит словарь {id чата пользователя: тип карточек ('ru-en'/'en-ru')}.
        
        '''
        return dict(session.query(User.id_chat, User.type_cards).all())

    @staticmethod
    def add_new_user(chat_id):
        '''Функция добавления нового пользователя в таблицу "user".
           
        '''
        model = User(id_chat=chat_id, type_cards='en-ru')
        session.add(model)
        session.commit()
        BACKEND_INFO.update({chat_id: 'en-ru'})

    @staticmethod
    def change_language(chat_id):
        '''Функция смены языка карточек
           Вносит изменения в таблицу "user" и обновляет 
           оперативный словарь BACKEND_INFO.
        '''
        options = {'en-ru':'ru-en', 'ru-en': 'en-ru'}
        session.query(User).filter(User.id_chat == chat_id)\
               .update({'type_cards': options[BACKEND_INFO[chat_id]]})
        session.commit()
        BACKEND_INFO[chat_id] = options[BACKEND_INFO[chat_id]]

    @staticmethod
    def pulling_out_words_for_cards(chat_id):
        '''Функция выборки четырех слов из базы данных.
           Возвращаемые слова принадлежат к одному, случайно выбранному, типу речи.

        '''
        words = session.query(Word)\
                        .with_entities(Word.title, Word.translation)\
                        .filter(Word.id_type == choice(BACKEND_INFO['types'])).all()
        words = [choice(words) for _ in range(4)]
        return (
            (words[i] if not i else words[i][1] for i in range(4))
            if BACKEND_INFO[chat_id] == 'en-ru' else
            (words[i] if not i else words[i][0] for i in range(4))
            )

    @staticmethod
    def add_word(target_word, chat_id):
        '''Функция добавления слова в таблицу "study". 
        
        '''
        word_id, user_id = DBase._pulling_info(target_word, chat_id)
        model = Study(id_word=word_id, id_user=user_id, date=datetime.now().date())
        session.add(model)
        session.commit()

    @staticmethod
    def del_word(target_word, chat_id):
        '''Функция удаления слова из таблицы "study".
        
        '''
        word_id, user_id = DBase._pulling_info(target_word, chat_id)
        session.query(Study).filter(Study.id_word == word_id)\
                            .filter(Study.id_user == user_id).delete()
        session.commit()

    @staticmethod
    def is_in_study(target_word, chat_id):
        '''Функция проверки наличия выбранного слова в персональном списке пользователя.
           По результатам возвращаемого даной функцией значения отображается кнопка 'Удалить 🗑'.
           True - наличие кнопки (и возможность удалить слово из таблицы "study"),
           False - отсуствие.
        '''
        word_id, user_id = DBase._pulling_info(target_word, chat_id)
        try:
            session.query(Study).filter(Study.id_user == user_id)\
                   .filter(Study.id_word == word_id).first().id_study
            return True
        except AttributeError:
            return False


class RegisterStates(StatesGroup):
    '''Класс регистрации состояний Telegram-бота, для их использования 
       в разных функциях-обработчиках.

    '''
    target_word = State()
    target_word_transl = State()
    avail_options = State()
    target_word_message= State()


class Extentions:
    '''Класс дополнительных возможностей, относящихся к Telegram-боту, в том
       числе регистрация кнопок пользователя и некоторые вспомогательные функции.

    '''
    add_word = types.KeyboardButton('Добавить \U00002795')
    del_word = types.KeyboardButton('Удалить \U0001F5D1')
    next_word = types.KeyboardButton('Следующее \U000023E9')
    ru_en_change = types.KeyboardButton('\U0001F1F7\U0001F1FA Сменить \U0001F1EC\U0001F1E7')
    en_ru_change = types.KeyboardButton('\U0001F1EC\U0001F1E7 Сменить \U0001F1F7\U0001F1FA')
    show_users_list = types.KeyboardButton('Ваши слова \U0001F9E0')

    @staticmethod
    def random_phrase_win():
        '''Функция возвращает рандомную фразу
           в случае правильного ответа пользователя
        '''
        answer_options = (
            'Да, Вы правы \U0001F44D', 'Так держать \U0001F44F',
            'Точно! \U0001F4AA', 'Прекрасно \U0001F973', 'В точку \U0001F4AF',
            'Верно \U00002705'
        )
        return choice(answer_options)

    @staticmethod
    def random_phrase_lose():
        '''Функция возвращает рандомную фразу
           в случае неверного ответа пользователя
        '''
        answer_options = (
            'К сожалению нет \U0001F648', 'Ответ неверный \U0000274C',
            'Не расстраивайтесь, попробуйте еще раз \U0001F9DE', 'Почти угадали \U0001F40C',
            'Тут даже я бы ошибся \U0001F937', 'Сосредоточьтесь \U0001F9A5'
        )
        return choice(answer_options)


class Telebot:
    '''Статический класс для обработки сообщений Telegram-бота

       Для инициализации класса необходимо в файл .config ввести имеющийся токен
    
    '''
    bot = TeleBot(TGBOT_TOKEN, state_storage=StateMemoryStorage())

    @staticmethod
    @bot.message_handler(func=lambda message: message.text == Extentions.next_word.text)
    def next_word(message):
        '''Функция пропуска незнакомого слова или продолжения работы после выполнения
        каких-либо операций.
        Выполняется при получении текстового сообщения 'Следующее ⏩'.

        '''
        Telebot.create_cards(message)

    @staticmethod
    @bot.message_handler(func=lambda message: message.text == Extentions.del_word.text)
    def del_word(message):
        '''Функция удаления слова из персонального списка пользователя.
           Выполняется при получении текстового сообщения 'Удалить 🗑'.
        
        '''
        with Telebot.bot.retrieve_data(message.from_user.id, message.chat.id) as data:
            target_word = data['target_word']
            DBase.del_word(target_word, message.chat.id)
            Telebot.bot.send_message(message.chat.id,
                                     f'Слово {target_word.upper()} удалено из '
                                     'Вашего персонального списка! \U0001F4A9')
        Telebot.create_cards(message)

    @staticmethod
    @bot.message_handler(func=lambda message: message.text == Extentions.add_word.text)
    def add_word(message):
        '''Функция добавления слова в персональный список пользователя
           Выполняется при получении текстового сообщения 'Добавить ➕'
        
        '''
        try:
            with Telebot.bot.retrieve_data(message.from_user.id, message.chat.id) as data:
                target_word = data['target_word']
                target_word_transl = data['target_word_transl']
        except KeyError:
            Telebot.bot.send_message(message.chat.id,
                                     'Простите, сплю на ходу \U0001F634')
            Telebot.create_cards(message)
            return

        DBase.add_word(target_word, message.chat.id)

        Telebot.bot.send_message(message.chat.id,
                                 'Запомните, а то забудете!\U0001F9D0\n')
        if BACKEND_INFO[message.chat.id] == 'en-ru':
            reply_message = (f'\U0001F1EC\U0001F1E7 {target_word.upper()} '
                             f'\U00002194 {target_word_transl} \U0001F1F7\U0001F1FA')
        else:
            reply_message = (f'\U0001F1F7\U0001F1FA {target_word.upper()} '
                             f'\U00002194 {target_word_transl} \U0001F1EC\U0001F1E7 ')
        Telebot.bot.send_message(message.chat.id, reply_message)
        Telebot.bot.send_message(message.chat.id,
                                 'Слово добавлено в персональный список, '
                                 'я пришлю уведомление когда придет \U000023F0 его повторить')
        Telebot.create_cards(message)

    @staticmethod
    @bot.message_handler(func=lambda message: message.text == Extentions.show_users_list.text)
    def show_users_word(message):
        '''Функция отображения слов, в настоящее время находящихся 
           в персональном списке пользователя

        '''
        words = DBase.pulling_out_user_words(message.chat.id)
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
    def change_language(message):
        '''Функция смены языка отображаемых карточек
        '''
        DBase.change_language(message.chat.id)
        Telebot.create_cards(message)

    @staticmethod
    @bot.message_handler(commands=['start'])
    def greeting(message):
        '''Функция приветствия пользователя,
           Выполняется при получении команды /start

        '''
        if message.chat.id not in BACKEND_INFO:
            DBase.add_new_user(message.chat.id)
        greeting_message = (
            'Доброго времени суток! \U0001F44B\n'
            'Я - бот \U0001F916, обучающий английскому лексикону \U0001F468\U0000200D\U0001F393\n'
            )
        faq_message = (
            'Для более подробной информации \U0001F4AC о правилах введите /help\n'
            'Для начала обучения \U0001F4DA\nвведите /cards\n'
            'или выберите кнопки ниже \U0001F447'
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
    def help(message):
        '''Функция, подробно отображающая принцип работы бота
           по взаимодействию с пользователем
           Выполняется при получении команды /help

        '''
        help_message = (
            'Как уже было сказано ранее, я - бот \U0001F916, обучающий английскому лексикону.\n'
            'Обучение проходит в формате теста - я предлагаю \U0001F1EC\U0001F1E7 слово, Ваша '
            'задача выбрать его перевод на \U0001F1F7\U0001F1FA из четырех предложенных вариантов.'
            '\nТакже, за каждым пользователем закреплен список изучаемых в данный момент слов.\n'
            'Если в процессе обучения Вы наткнетесь на незнакомое слово \U0001F92F, Вы можете '
            'добавить его в персональный список. В таком случае Вам будут высылаться уведомления '
            'для их повторения по принципу интервальных повторений: через 1 день, 7, 16 и 35.\n'
            'При очень большом желании я также могу вывести список '
            'изучаемых Вами в данный момент слов, для этого введите \nкоманду /show\n'
            'Давайте уже начнем! \U0001F609'
            )
        markup_repl = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup_repl.add('/cards')

        Telebot.bot.send_message(message.chat.id, help_message, reply_markup=markup_repl)

    @staticmethod
    @bot.message_handler(commands=['cards'])
    def create_cards(message):
        '''Функция генерации карточки
           Получает слова из базы данных и передает их пользователю
           Выполняется при получении команды /cards

        '''
        target_word, *words_transl = DBase.pulling_out_words_for_cards(message.chat.id)
        match BACKEND_INFO[message.chat.id]:
            case 'en-ru':
                target_word, target_word_transl = target_word
                start_cards_message = f'\U0001F1EC\U0001F1E7 {target_word.upper()}'
            case 'ru-en':
                target_word_transl, target_word = target_word
                start_cards_message = f'\U0001F1F7\U0001F1FA {target_word.upper()}'

        words_transl.append(target_word_transl)
        shuffle(words_transl)
        words_buttons = (types.KeyboardButton(word) for word in words_transl)
        markup_repl = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
        markup_repl.add(*words_buttons)

        markup_repl.add(Extentions.next_word)
        if DBase.is_in_study(target_word, message.chat.id):
            markup_repl.add(Extentions.del_word)
        else:
            markup_repl.add(Extentions.add_word)

        if BACKEND_INFO[message.chat.id] == 'en-ru':
            markup_repl.row(Extentions.show_users_list, Extentions.en_ru_change)
        else:
            markup_repl.row(Extentions.show_users_list, Extentions.ru_en_change)

        Telebot.bot.set_state(message.from_user.id,
                              RegisterStates.target_word_transl, message.chat.id)
        with Telebot.bot.retrieve_data(message.from_user.id, message.chat.id) as data:
            data['target_word_transl'] = target_word_transl
            data['target_word'] = target_word
            data['avail_options'] = words_transl
            data['target_word_message'] = start_cards_message

        Telebot.bot.send_message(message.chat.id, start_cards_message, reply_markup=markup_repl)

    @staticmethod
    @bot.message_handler(content_types=['text'])
    def check_response(message):
        '''Функция проверки ответа пользователя на сгенерированную в функции
           create_cards карточку
           Выполняется при получении любого текстового сообщения, по остаточному принципу
           (что не обработалось ранее, попадает в даный обработчик)
        
        '''
        user_word = message.text
        try:
            with Telebot.bot.retrieve_data(message.from_user.id, message.chat.id) as data:
                target_word_transl = data['target_word_transl']
                avail_options = data['avail_options']
                start_cards_message = data['target_word_message']
        except KeyError:
            Telebot.bot.send_message(message.chat.id,
                                     'Простите, уснул \U0001F4A4 , продолжаем...')
            Telebot.create_cards(message)
            return
        if user_word in avail_options:
            if target_word_transl == user_word:
                Telebot.bot.send_message(message.chat.id,
                                        Extentions.random_phrase_win())
                Telebot.create_cards(message)
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
    print('Bot is running...')
    session = DBaseConfig.Session()
    BACKEND_INFO = DBase.filling_backend_info_users()
    BACKEND_INFO['types'] = DBase.filling_backend_info_words()
    try:
        Telebot.bot.polling(interval=1)
    finally:
        print('Bot stopped.')
        session.close()
        print('Session close.')
