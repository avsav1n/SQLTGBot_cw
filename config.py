'''
Модуль констант для инициализации программы и 
ее подключения к Telegram-боту и базе данных PostgreSQL

'''
import os 

# Токен Telegram-бота
TGBOT_TOKEN = os.getenv('TGBOTOKEN') 

# Параметры подключения к базе данных
DB_DRIVER = 'postgresql'
DB_LOGIN = 'postgres'
DB_PASSWORD = os.getenv('PSQLPASS')
DB_CONNECTION = 'localhost'
DB_PORT = '5432'
DB_NAME = 'pyCards'
