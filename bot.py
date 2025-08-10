from flask import Flask, request, jsonify
import requests
import json
import os

TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
WIRECRM_API_KEY = os.environ.get('WIRECRM_API_KEY')

if not TELEGRAM_BOT_TOKEN or not WIRECRM_API_KEY:
    raise ValueError("Необходимо установить переменные окружения TELEGRAM_BOT_TOKEN и WIRECRM_API_KEY")

app = Flask(__name__)

def get_worker_telegram_id(worker_id):
    if not worker_id:
        print("Ошибка: ID работника не передан.")
        return None

    url = f"https://wirecrm.com/api/v1/workers/{worker_id}"
    headers = {'X-API-KEY': WIRECRM_API_KEY}
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            worker_data = response.json().get('data', {})
            if not worker_data:
                 print(f"ОШИБКА: Не найдены данные для работника {worker_id}")
                 return None
            
            print(f"Получены данные по работнику ID {worker_id}: {worker_data}")
            
            telegram_id = worker_data.get('phone')
            
            if telegram_id:
                print(f"Найден Telegram ID в поле 'phone': {telegram_id}")
                return telegram_id
            else:
                print(f"ОШИБКА: В карточке работника {worker_id} не заполнено поле 'Телефон'.")
                return None
        else:
            print(f"Ошибка запроса данных работника {worker_id} из CRM: {response.text}")
            return None
    except Exception as e:
        print(f"Критическая ошибка при запросе работника из CRM: {e}")
        return None

def send_telegram_message(chat_id, text, keyboard=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {'chat_id': chat_id, 'text': text, 'parse_mode': 'Markdown'}
    if keyboard:
        payload['reply_markup'] = json.dumps(keyboard)
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200 and response.json().get('ok'):
            print(f"Сообщение успешно отправлено пользователю {chat_id}")
            return True
        else:
            print(f"Ошибка отправки сообщения: {response.text}")
            return False
    except Exception as e:
        print(f"Критическая ошибка при отправке сообщения: {e}")
        return False

def create_new_order_keyboard(order_id):
    return {"inline_keyboard": [[{"text": "✅ Принять", "callback_data": f"accept_order_{order_id}"}, {"text": "❌ Отклонить", "callback_data": f"decline_order_{order_id}"}]]}

@app.route('/webhook', methods=['POST'])
def wirecrm_webhook():
    print("\n--- Получен новый вебхук от WireCRM! ---")
    
    # ИЗМЕНЕНИЕ: Добавляем подробное логирование для диагностики
    print("--- Заголовки запроса (Headers): ---")
    print(request.headers)
    print("--- Сырые данные запроса (Raw Data): ---")
    print(request.data)
    
    # Пытаемся получить JSON, как и раньше
    data = request.get_json(force=True, silent=True) # silent=True чтобы не вызывать ошибку сразу
    
    if not data:
        print("ОШИБКА: Не удалось автоматически распознать JSON. Возможно, данные в другом формате.")
        # Пытаемся обработать данные как форму, если JSON не сработал
        if request.form:
            print("Обнаружены данные в формате формы. Пытаемся обработать...")
            # WireCRM может отправлять JSON строкой в одном из полей формы
            form_data_str = list(request.form.keys())[0]
            print(f"Строка из формы: {form_data_str}")
            try:
                data = json.loads(form_data_str)
            except json.JSONDecodeError:
                print("Критическая ошибка: не удалось преобразовать данные из формы в JSON.")
                return jsonify({"status": "error", "message": "Invalid form data format"}), 400
        else:
            return jsonify({"status": "error", "message": "No data received or format not recognized"}), 400

    print("Полные данные от CRM (после обработки):", json.dumps(data, indent=2, ensure_ascii=False))
    
    try:
        order_info = data.get('msg', {})
        order_id = order_info.get('id', 'Неизвестный ID')
        order_name = order_info.get('name', 'Без названия')
        
        worker_id = order_info.get('worker')
        
        if not worker_id:
            print("ОШИБКА: В данных вебхука отсутствует ID работника ('worker').")
            return jsonify({"status": "error", "message": "worker_id not found"}), 400

        print(f"Заказ №{order_id}. Назначен работник с ID: {worker_id}")

        master_telegram_id = get_worker_telegram_id(worker_id)
        
        if master_telegram_id:
            order_text = (
                f"*Новый заказ №{order_id}*\n\n"
                f"Название: {order_name}\n\n"
                f"Вам назначен новый заказ. Пожалуйста, подтвердите получение."
            )
            keyboard = create_new_order_keyboard(order_id)
            send_telegram_message(master_telegram_id, order_text, keyboard)
            return jsonify({"status": "success"}), 200
        else:
            print(f"Не удалось отправить уведомление, так как не найден Telegram ID для работника {worker_id}.")
            return jsonify({"status": "error", "message": "telegram_id not found for worker"}), 404
        
    except Exception as e:
        print(f"Критическая ошибка при обработке вебхука: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/')
def index():
    return "Сервер для Telegram-бота работает!"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
