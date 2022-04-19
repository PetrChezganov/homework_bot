import logging
import os
import sys
import time
from http import HTTPStatus
from logging import StreamHandler

import requests
import telegram
from dotenv import load_dotenv

from exceptions import EndpointError, HomeworkStatuseError

logger = logging.getLogger(__name__)

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
SECONDS_IN_MINUTE = 60
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

KEY_HOMEWORKS = 'homeworks'
KEY_CURRENT_DATE = 'current_date'
KEY_HOMEWORK_NAME = 'homework_name'
KEY_STATUS = 'status'


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    bot.send_message(TELEGRAM_CHAT_ID, message)
    logger.info(f'Сообщение "{message}" отправлено.')


def get_api_answer(current_timestamp):
    """Делает запрос к единственному эндпоинту API-сервиса."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    logger.info(f'Подключаемся к API: {ENDPOINT}.')
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    except ConnectionError as error:
        logger.error(f'Ошибка {error} при подключения к API: {ENDPOINT}.')
        raise ConnectionError
    if response.status_code != HTTPStatus.OK:
        logger.error(
            f'Сбой в работе программы: Эндпоинт {ENDPOINT} недоступен.\n'
            f'Код ответа API: {response.status_code}.\n'
            f'Параметры запроса: {params}.\n'
            f'Текст ответа API: {response.text}.'
        )
        raise EndpointError
    try:
        return response.json()
    except ValueError:
        logger.error('Ошибка преобразования ответа API из формата json')
        raise ValueError


def check_response(response):
    """Проверяет ответ API на корректность."""
    logger.info(f'Проверяем ответ API: {ENDPOINT}')
    if not isinstance(response, dict):
        logger.error('Тип данных ответа API должен быть словарь.')
        raise TypeError
    if KEY_HOMEWORKS not in response:
        logger.error(
            'Сбой в работе программы: Ключ словаря ответа API '
            f' {KEY_HOMEWORKS} неверен.'
        )
        raise KeyError
    homeworks = response.get(KEY_HOMEWORKS)
    if KEY_CURRENT_DATE not in response:
        logger.error(
            'Сбой в работе программы: Ключ словаря ответа API '
            f'{KEY_CURRENT_DATE} неверен.'
        )
        raise KeyError
    if not isinstance(homeworks, list):
        logger.error(
            'Домашние работы в ответе API должны быть упакованы в список.'
        )
        raise TypeError
    return homeworks


def parse_status(homework):
    """Извлекает из ответа API информацию о конкретной домашней работе.
    И статус этой работы.
    """
    if not isinstance(homework, dict):
        logger.error('Тип данных информации о работе должен быть словарь.')
        raise TypeError
    if KEY_HOMEWORK_NAME not in homework:
        logger.error(
            'Сбой в работе программы: Ключ словаря ответа API '
            f'{KEY_HOMEWORK_NAME} неверен.'
        )
        raise KeyError
    if KEY_STATUS not in homework:
        logger.error(
            f'Сбой в работе программы: Ключ словаря ответа API {KEY_STATUS} '
            'неверен.'
        )
        raise KeyError
    homework_name = homework.get(KEY_HOMEWORK_NAME)
    homework_status = homework.get(KEY_STATUS)
    if homework_status not in HOMEWORK_VERDICTS:
        logger.error(
            'Сбой в работе программы: в ответе API обнаружен '
            'недокументированный статус домашней работы.'
        )
        raise HomeworkStatuseError
    verdict = HOMEWORK_VERDICTS.get(homework_status)
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяет доступность переменных окружения."""
    if all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]):
        return True


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logger.critical(
            'Отсутствует обязательная переменная окружения!\n'
            'Программа принудительно остановлена.'
        )
        exit()

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    LAST_ERROR_MESSAGE = ''

    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            if not homeworks:
                logger.info('Обновлений нет')
            else:
                for homework in homeworks:
                    message = parse_status(homework)
                    send_message(bot, message)
            current_timestamp = response.get(KEY_CURRENT_DATE)
        except Exception as error:
            error_message = f'Сбой в работе программы: {error}'
            if error_message != LAST_ERROR_MESSAGE:
                send_message(bot, error_message)
                LAST_ERROR_MESSAGE = error_message
            logger.error(error_message)
        time.sleep(RETRY_TIME)


if __name__ == '__main__':
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - модуль: %(module)s - функция: '
        '%(funcName)s - номер строки: %(lineno)d - %(message)s'
    )
    handler = StreamHandler(sys.stdout)
    logger.setLevel(logging.INFO)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    main()
