'''
Модуль присылающий уведомления пользователю для повторения слов, 
находящихся у него в персональном списке.

'''
from datetime import date
from time import sleep

from schedule import repeat, run_pending, every
from telebot import types, TeleBot
from sqlalchemy import distinct, func

from models import DBaseConfig, Study, User
from config import TGBOT_TOKEN

def check_in() -> list:
    '''Функция выборки информации о пользователях (chat_id).
       Выборка осуществляется по дате ('date') таблицы "study": дата меньше текущей.
       Возвращает список идентификаторов чата: [chat_id, chat_id,...]

    '''
    with DBaseConfig.Session() as session:
        query = session.query(Study).with_entities(distinct(User.id_chat))\
                        .join(User.study).filter(Study.date < date.today()).group_by.all()
    return [chat_id[0] for chat_id in query] if query else None


def activate_notifications() -> None:
    '''Функция рассылки уведомлений о повторении слов, 
       находящиеся в персональном списке пользователя и
       соответствующие условию: добавлены в персональный список ранее текущей даты.

    '''
    bot = TeleBot(TGBOT_TOKEN)
    plan = check_in()
    if not plan:
        return
    for chat_id in plan:
        im_ready_button = types.KeyboardButton('Поехали! \U0001F680')
        markup_repl = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
        markup_repl.add(im_ready_button)
        notification_message = 'Пришло время повторить слово из Вашего списка \U0001F556'
        bot.send_message(chat_id, notification_message, reply_markup=markup_repl)


# Декоратор настоен на запуск функции notification ежедневно в 19.00
# Для проведения тестов можно заменить декоратор на другой,
# активирующий скрипт рассылки уведомлений каждые 30 секунд:
#    @repeat(every(30).seconds)

@repeat(every().day.at('19:00'))
def notifications():
    '''Функция-таймер.
       Запускает скрипт рассылки уведомлений по расписанию.

    '''
    activate_notifications()


if __name__ == '__main__':
    print('Notifications are running...')
    try:
        while True:
            run_pending()
            sleep(1)
    finally:
        print('Notifications stopped.')
