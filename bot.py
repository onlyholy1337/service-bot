from flask import Flask, request, jsonify
import requests
import json
import os
import re # Импортируем библиотеку для поиска по шаблону

TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
WIRECRM_API_KEY = os.environ.get('WIRECRM_API_KEY')

if not TELEGRAM_BOT_TOKEN or not WIRECRM_API_KEY:
    raise ValueError("Необходимо установить переменные окружения TELEGRAM_BOT_TOKEN и WIRECRM_API_KEY")

app = Flask(__name__)

def get_deal_details(deal_id):
    if not deal_id:
        return None
    url = f"https://wirecrm.com/api/v1/deals/{deal_id}"
    headers = {'X-API-KEY': WIRECRM_API_KEY}
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            deal_data_list = response.json().get('data', [])
            if isinstance(deal_data_list, list) and deal_data_list:
                deal_data = deal_data_list[0]
                print(f"Получены полные данные по сделке {deal_id}: {deal_data}")
                return deal_data
            else:
                print(f"Ошибка: Данные по сделке {deal_id} пришли в неожиданном формате или пусты.")
                return None
        else:
            print(f"Ошибка запроса данных сделки {deal_id}: {response.text}")
            return None
    except Exception as e:
        print(f"Критическая ошибка при запросе сделки из CRM: {e}")
        return None

def find_telegram_id_in_description(description):
    """
    Ищет в тексте описания строку "ID: {число}" и возвращает число.
    """
    if not description:
        return None
    
    # Ищем шаблон "ID: " за которым следуют цифры
    match = re.search(r'ID:\s*(\d+)', description, re.IGNORECASE)
    
    if match:
        telegram_id = match.group(1)
        print(f"Найден Telegram ID в описании: {telegram_id}")
        return telegram_id
    else:
        print("Telegram ID в описании не найден.")
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
    data = None
    
    try:
        if request.is_json:
            data = request.get_json()
        elif request.form:
            form_data_str = list(request.form.keys())[0]
            data = json.loads(form_data_str)
        else:
            raw_data = request.data
            if raw_data:
                data_str = raw_data.decode('utf-8')
                data = json.loads(data_str)
        if not data:
            print("ОШИБКА: Не удалось извлечь данные.")
            return jsonify({"status": "error", "message": "Could not extract data"}), 400
    except Exception as e:
        print(f"КРИТИЧЕСКАЯ ОШИБКА: Не удалось обработать входящие данные. Ошибка: {e}")
        return jsonify({"status": "error", "message": "Failed to parse request data"}), 400
    
    print("Данные из вебхука:", json.dumps(data, indent=2, ensure_ascii=False))
    
    try:
        order_info_from_webhook = data.get('msg', {})
        order_id = order_info_from_webhook.get('id')
        
        if not order_id:
            print("ОШИБКА: В вебхуке отсутствует ID заказа.")
            return jsonify({"status": "error", "message": "order_id not found in webhook"}), 400

        full_order_info = get_deal_details(order_id)
        if not full_order_info:
            return jsonify({"status": "error", "message": "Could not fetch full order details"}), 404

        order_name = full_order_info.get('name', 'Без названия')
        description = full_order_info.get('description', '')

        # ИЗМЕНЕНИЕ: Ищем Telegram ID прямо в описании
        master_telegram_id = find_telegram_id_in_description(description)
        
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
            print(f"Не удалось отправить уведомление, так как не найден Telegram ID в описании заказа {order_id}.")
            return jsonify({"status": "error", "message": "telegram_id not found in description"}), 404
        
    except Exception as e:
        print(f"Критическая ошибка при обработке вебхука: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/')
def index():
    return "Сервер для Telegram-бота работает!"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
