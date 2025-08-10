from flask import Flask, request, jsonify
import requests
import json
import os
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
WIRECRM_API_KEY = os.environ.get('WIRECRM_API_KEY')

if not TELEGRAM_BOT_TOKEN or not WIRECRM_API_KEY:
    raise ValueError("Необходимо установить переменные окружения TELEGRAM_BOT_TOKEN и WIRECRM_API_KEY")

app = Flask(__name__)



def send_telegram_message(chat_id, text, keyboard=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        'chat_id': chat_id,
        'text': text,
        'parse_mode': 'Markdown'
    }
    if keyboard:
        payload['reply_markup'] = json.dumps(keyboard)

    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200 and response.json().get('ok'):
            print(f"Сообщение успешно отправлено пользователю {chat_id}")
            return True
        else:
            print(f"Ошибка отправки сообщения пользователю {chat_id}: {response.text}")
            return False
    except Exception as e:
        print(f"Критическая ошибка при отправке сообщения: {e}")
        return False


def create_new_order_keyboard(order_id):
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "✅ Принять", "callback_data": f"accept_order_{order_id}"},
                {"text": "❌ Отклонить", "callback_data": f"decline_order_{order_id}"}
            ]
        ]
    }
    return keyboard



@app.route('/webhook', methods=['POST'])
def wirecrm_webhook():
    print("\n--- Получен новый вебхук от WireCRM! ---")
    data = request.json
    print("Данные от CRM:", json.dumps(data, indent=2, ensure_ascii=False))

    try:
        order_info = data.get('msg', {})
        order_id = order_info.get('id', 'Неизвестный ID')

        master_telegram_id = 2098323557

        order_text = (
            f"*Новый заказ №{order_id}*\n\n"
            f"Вам назначен новый заказ. Пожалуйста, подтвердите получение."
        )
        keyboard = create_new_order_keyboard(order_id)
        send_telegram_message(master_telegram_id, order_text, keyboard)

        return jsonify({"status": "success"}), 200

    except Exception as e:
        print(f"Ошибка при обработке вебхука: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/')
def index():
    return "Сервер для Telegram-бота работает!"


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
