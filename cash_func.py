'''
Модуль кеширования.

'''
import os
import json

def cash_func(function):
    '''Функция-декоратор для кеширования запросов вспомогательных функций 
       _pulling_info_user_id, _pulling_info_word_id.
       Информация по осуществленным запросам хранится в файле data\\cash.json

    '''
    def wrapper(*args):
        param = str(args[0])
        path = os.path.join(os.getcwd(), 'data', 'cash.json')
        try:
            with open(path, 'r', encoding='utf-8') as fr:
                data = json.load(fr)
            if data.get(param):
                return data[param]
        except (json.decoder.JSONDecodeError, FileNotFoundError):
            data = {}
        data.update({param: (result := function(*args))})
        with open(path, 'w', encoding='utf-8') as fw:
            json.dump(data, fw, ensure_ascii=False, indent=2)
        return result
    return wrapper
