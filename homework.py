import datetime
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
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler = StreamHandler(sys.stdout)
logger.setLevel(logging.INFO)
handler.setFormatter(formatter)
logger.addHandler(handler)

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
SECONDS_IN_MINUTE = 60
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

KEY_HOMEWORKS = 'homeworks'
KEY_HOMEWORK_NAME = 'homework_name'
KEY_STATUS = 'status'
KEY_CURRENT_DATE = 'current_date'


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    bot.send_message(TELEGRAM_CHAT_ID, message)


def get_api_answer(current_timestamp):
    """Делает запрос к единственному эндпоинту API-сервиса."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    if response.status_code != HTTPStatus.OK:
        logging.error(
            f'Сбой в работе программы: Эндпоинт {ENDPOINT} недоступен. '
            f'Код ответа API: {response.status_code}'
        )
        raise EndpointError
    try:
        return response.json()
    except ValueError:
        logger.error('Ошибка преобразования ответа API из формата json')
        raise ValueError


def check_response(response):
    """Проверяет ответ API на корректность."""
    if type(response) is not dict:
        logger.error('Тип данных ответа API должен быть словарь.')
        raise TypeError
    if KEY_HOMEWORKS not in response:
        logger.error(
            f'Сбой в работе программы: Ключ словаря ответа API {KEY_HOMEWORKS}'
            ' неверен.'
        )
        raise KeyError
    homeworks = response.get(KEY_HOMEWORKS)
    if type(homeworks) is not list:
        logger.error(
            'Домашние работы в ответе API должны быть упакованы в список.'
        )
        raise TypeError
    return homeworks


def parse_status(homework):
    """Извлекает из ответа API информацию о конкретной домашней работе.
    И статус этой работы.
    """
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
    if homework_status not in HOMEWORK_STATUSES:
        logger.error(
            'Сбой в работе программы: в ответе API обнаружен '
            'недокументированный статус домашней работы.'
        )
        raise HomeworkStatuseError
    verdict = HOMEWORK_STATUSES.get(homework_status)
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяет доступность переменных окружения."""
    if PRACTICUM_TOKEN is None:
        logger.critical(
            'Отсутствует обязательная переменная окружения: '
            '"PRACTICUM_TOKEN".\n'
            'Программа принудительно остановлена.'
        )
        return False
    elif TELEGRAM_TOKEN is None:
        logger.critical(
            'Отсутствует обязательная переменная окружения: '
            '"TELEGRAM_TOKEN".\n'
            'Программа принудительно остановлена.'
        )
        return False
    elif TELEGRAM_CHAT_ID is None:
        logger.critical(
            'Отсутствует обязательная переменная окружения: '
            '"TELEGRAM_CHAT_ID".\n'
            'Программа принудительно остановлена.'
        )
        return False
    return True


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        exit()

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    # current_timestamp = int(time.time())
    date = datetime.date(2022, 3, 1)
    current_timestamp = int(time.mktime(date.timetuple()))
    LAST_ERROR_MESSAGE = ''

    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            if homeworks == []:
                logger.info('Обновлений нет')
            else:
                for homework in homeworks:
                    message = parse_status(homework)
                    send_message(bot, message)
                    logger.info(f'Сообщение "{message}" отправлено')
            if KEY_CURRENT_DATE not in response:
                logger.error(
                    'Сбой в работе программы: Ключ словаря ответа API '
                    f'{KEY_CURRENT_DATE} неверен.'
                )
                raise KeyError
            current_timestamp = response.get(KEY_CURRENT_DATE)
            time.sleep(RETRY_TIME)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            if message != LAST_ERROR_MESSAGE:
                send_message(bot, message)
                LAST_ERROR_MESSAGE = message
            logger.error(f'Сбой в работе программы: {error}')
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
