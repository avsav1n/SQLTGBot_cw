'''
Модуль описания моделей таблиц,
а также подготовки базы данных к работе с ней: создание таблиц, их заполнение.

'''
import os

import sqlalchemy as sqla
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from config import *

class DBaseConfig:
    '''Класс подготовки базы данных к работе.

    '''
    Base = declarative_base()
    DSN = f'{DB_DRIVER}://{DB_LOGIN}:{DB_PASSWORD}@{DB_CONNECTION}:{DB_PORT}/{DB_NAME}'
    engine = sqla.create_engine(DSN)
    Session = sessionmaker(engine)

    @staticmethod
    def create_table(engine):
        '''Функция создания таблиц, по описанным моделям.

        '''
        DBaseConfig.Base.metadata.create_all(engine)

    @staticmethod
    def delete_table(engine):
        '''Функция удаления всех созданных таблиц.

        '''
        DBaseConfig.Base.metadata.drop_all(engine)

    @staticmethod
    def filling_out_type():
        '''Функция заполнения таблицы "type".
           Заполнение осуществляется данными из кортежа types.

        '''
        types = ('verb', 'noun', 'adjective', 'adverb', 'pronoun', 'numeral')
        with DBaseConfig.Session() as session:
            for title in types:
                model = Type(title=title)
                session.add(model)
            session.commit()

    @staticmethod
    def filling_out_word():
        '''Функция заполнения таблицы "word".
           Заполнение осуществляется данными из .txt файла, 
           формата: 'часть речи';'слово';'перевод'.

        '''
        file_path = os.path.join(os.getcwd(), 'data', 'all_words.txt')
        with open(file_path, encoding='utf-8') as file:
            data = file.readlines()
        with DBaseConfig.Session() as session:
            types = session.query(Type.id_type, Type.title).all()
            types = {title: id_type for id_type, title in types}
            for line in data:
                id_type, title, translation = line.rstrip().split(';')
                model = Word(id_type=types[id_type] , title=title, translation=translation)
                session.add(model)
            session.commit()


class Type(DBaseConfig.Base):
    '''Модель таблицы "type".

       Хранит идентификатор и часть речи, 
       к которому принадлежит слово из таблицы "word" (глагол, существительное...)
       По принципу "один ко многим" связана с "word".

    '''
    __tablename__ = 'type'

    id_type = sqla.Column(sqla.Integer, primary_key=True)
    title = sqla.Column(sqla.String(length=20), unique=True, nullable=True)

    word = relationship('Word', back_populates='type')


class Word(DBaseConfig.Base):
    '''Модель таблицы "word"

       Хранит идентификатор, английское слово, его перевод и 
       ссылку на часть речи, к которому принадлежит
       По принципу "один ко многим" связана с "type"
       По принципу "один ко многим" связана с "study"

    '''
    __tablename__ = 'word'

    id_word = sqla.Column(sqla.Integer, primary_key=True)
    id_type = sqla.Column(sqla.Integer, sqla.ForeignKey(Type.id_type), nullable=False)
    title = sqla.Column(sqla.String(length=20), unique=True, nullable=False)
    translation = sqla.Column(sqla.String(length=20), nullable=True)

    type = relationship('Type', back_populates='word')
    study = relationship('Study', back_populates='word')


class User(DBaseConfig.Base):
    '''Модель таблицы "user"

       Хранит идентификатор, ID чата пользователя и язык отображения карточек.
       По принципу "один ко многим" связана с "study".

    '''
    __tablename__ = 'user'

    id_user = sqla.Column(sqla.Integer, primary_key=True)
    id_chat = sqla.Column(sqla.BigInteger, unique=True, nullable=False)
    language = sqla.Column(sqla.String(10), nullable=False)

    study = relationship('Study', back_populates='user')


class Study(DBaseConfig.Base):
    '''Модель таблицы "study"

       Хранит идентификатор, дату добавления слова,
       ID пользователя и ID слова, которые в настоящий момент он изучает.
       По принципу "один ко многим" связана с "word"
       По принципу "один ко многим" связана с "users"

    '''
    __tablename__ = 'study'

    id_study = sqla.Column(sqla.Integer, primary_key=True)
    id_word = sqla.Column(sqla.Integer, sqla.ForeignKey(Word.id_word), nullable=False)
    id_user = sqla.Column(sqla.Integer, sqla.ForeignKey(User.id_user), nullable=False)
    date = sqla.Column(sqla.Date, nullable=False)

    word = relationship('Word', back_populates='study')
    user = relationship('User', back_populates='study')

# Для создания таблиц по вышеописанным моделям и заполнения их данными,
# необходимо раскомментировать и запустить код ниже.

# if __name__ == '__main__':
#     DBaseConfig.create_table(DBaseConfig.engine)
#     DBaseConfig.filling_out_type()
#     DBaseConfig.filling_out_word()
