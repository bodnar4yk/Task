import requests
import pandas as pd

# === 1. КОНФІГУРАЦІЯ API ===


BASE_URL = "https://data.elexon.co.uk/bmrs/api/v1/forecast/indicated/day-ahead/evolution"

# Обрані дати
SELECTED_DAY_UTC = "2025-11-18"
PREVIOUS_DAY_UTC = "2025-11-17"

# Періоди розрахунку для повного дня UTC+2 (47,48 попереднього дня + 1-46 обраного дня)
periods_prev_day = [47, 48]
periods_selected_day = list(range(1, 47)) # Від 1 до 46 включно

# Параметри, спільні для обох запитів
COMMON_PARAMS = {
   # "boundary": "national", # Можна змінити на "zonal"
    "format": "json"
}

# === 2. ФУНКЦІЯ ОТРИМАННЯ ДАНИХ ===

def fetch_data(settlement_date, settlement_periods):
    """Виконує GET-запит до API та повертає JSON-відповідь."""
    
    # Перетворюємо список періодів на рядок, розділений комами
    period_str = ",".join(map(str, settlement_periods))
    
    # Параметри для поточного запиту
    params = {
        **COMMON_PARAMS,
        "settlementDate": settlement_date,
        "settlementPeriod": list(map(str, settlement_periods))
    }
    
    # Заголовки, що включають ключ API
    # headers = {
    #    "x-api-key": API_KEY
    # }
    
    print(f"-> Запит даних для {settlement_date}, періоди: {period_str}")
    
    try:
        response = requests.get(BASE_URL, params=params)#, headers=headers)
        print(response.url)
        response.raise_for_status() # Викликає HTTPError для поганих відповідей (4xx або 5xx)
        
        data = response.json()
        
        # Перевірка структури даних
        if 'data' in data and data['data']:
            print(f"<- Успішно отримано {len(data['data'])} записів.")
            return data['data']
        else:
            print("<- Успішно, але список даних порожній.")
            return []

    except requests.exceptions.RequestException as e:
        print(f"Помилка запиту до API: {e}")
        return []
    except Exception as e:
        print(f"Неочікувана помилка: {e}")
        return []

# === 3. ВИКОНАННЯ ЗАПИТІВ ТА ОБ'ЄДНАННЯ ===

# 1. Запит для попереднього дня (2025-11-17)

data_part1 = fetch_data(PREVIOUS_DAY_UTC, periods_prev_day)
#print(data_part1)

data_part2 = fetch_data(SELECTED_DAY_UTC, periods_selected_day)
#print(data_part2)

combined_data = data_part1 + data_part2
#print(combined_data)

df = pd.DataFrame(combined_data)
#print(df.head())

df['publishTime'] = pd.to_datetime(df['publishTime'])
#print(df.head())
df['settlementDate'] = pd.to_datetime(df['settlementDate'])
#print(df.head())
latest_publish_time = df['publishTime'].max()
#print(latest_publish_time)
latest_forecast = df[df['publishTime'] == latest_publish_time]
#print(latest_forecast)
