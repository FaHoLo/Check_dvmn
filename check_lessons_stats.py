import os
import logging
import requests
import telegram
from dotenv import load_dotenv


class SendToTelegramHandler(logging.Handler):

    def emit(self, record):
        log_entry = self.format(record)   
        self.send_error_log_to_telegram(log_entry)

    #Code snippet from: https://github.com/python-telegram-bot/python-telegram-bot/issues/768
    def send_error_log_to_telegram(self, text):
        tg_bot_token = os.environ['TG_LOG_BOT_TOKEN']
        chat_id = os.environ['TG_CHAT_ID']
        bot = telegram.Bot(token=tg_bot_token)
        message_max_length = 4096

        if len(text) <= message_max_length:
            return bot.send_message(chat_id, text)

        parts = []
        while text:
            if len(text) <= message_max_length:
                parts.append(text)
                break    
            part = text[:message_max_length]
            first_lnbr = part.rfind('\n')
            if first_lnbr != -1:
                parts.append(part[:first_lnbr])
                text = text[first_lnbr+1:]
            else:
                parts.append(part)
                text = text[message_max_length:]

        for part in parts:
            bot.send_message(chat_id, part)

def main():
    load_dotenv()
    check_lessons_stats()

def check_lessons_stats():
    logger = customize_logger()
    search_start_time = get_last_check_time()
    logger.info('Бот начал работу')
    while True:
        try:
            response = make_long_polling_request(search_start_time)
        except requests.exceptions.ReadTimeout:
            continue
        except requests.exceptions.ConnectionError:
            continue
        except Exception:
            logger.info('Бот встретился с ошибкой:')
            logger.exception('')
            continue
        if response['status'] == 'found':
            send_notify_to_telegram(response['new_attempts'])
            search_start_time = response['last_attempt_timestamp']
        else:
            search_start_time = response['timestamp_to_request']

def customize_logger():
    logger = logging.getLogger()
    logger.addHandler(SendToTelegramHandler())
    logger.setLevel('INFO')
    return logger

def get_last_check_time():    
    url = 'https://dvmn.org/api/user_reviews/'
    dvmn_token = os.environ['DVMN_TOKEN']
    headers = {'Authorization': f'Token {dvmn_token}'}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()['results'][0]['timestamp']

def make_long_polling_request(search_start_time):
    url = 'https://dvmn.org/api/long_polling/'
    dvmn_token = os.environ['DVMN_TOKEN']
    headers = {'Authorization': f'Token {dvmn_token}'}
    payload = {'timestamp': search_start_time}
    response = requests.get(url, params=payload, headers=headers)
    response.raise_for_status()
    return response.json()

def send_notify_to_telegram(attempts):
    tg_bot_token = os.environ['TG_BOT_TOKEN']
    chat_id = os.environ['TG_CHAT_ID']
    bot = telegram.Bot(token=tg_bot_token)
    for attempt in attempts:
        text = collect_message(attempt)
        bot.send_message(chat_id, text, disable_web_page_preview=True)

def collect_message(attempt):
    lesson_title = attempt['lesson_title']
    lesson_url = 'https://dvmn.org{}'.format(attempt['lesson_url'])
    lesson_status = 'Работа сдана, можно приступать к следующему уроку:'
    if attempt['is_negative']:
        lesson_status = 'В работе нашлись ошибки, скорее исправляй:'
    text = f'Проверена работа «‎{lesson_title}».\n\n{lesson_status}\n{lesson_url}'
    return text

if __name__ == '__main__':
    main()