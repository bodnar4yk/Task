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

###############################################################################
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# Групування за часом публікації (це різні версії прогнозу)
forecast_versions = df['publishTime'].unique()

plt.figure(figsize=(14, 8))
    
for version_time in forecast_versions:
    version_data = df[df['publishTime'] == version_time].sort_values(by=['settlementDate', 'settlementPeriod'])
        
        # Створюємо унікальний часовий індекс для кожного періоду
        # Це спрощений підхід, який вимагає доопрацювання для точного відображення UTC->UTC+2
    x_axis_labels = version_data['settlementPeriod'].astype(str) + " (" + version_data['settlementDate'].dt.strftime('%d.%m') + ")"
        
        # Відображаємо прогноз для цієї версії
    plt.plot(version_data['settlementPeriod'].values, 
            version_data['indicatedImbalance'].values)
            #label=f"Опубліковано: {pd.to_datetime(version_time).strftime('%H:%M %d.%m')}", 
            #alpha=0.6)

plt.title('Еволюція прогнозу індикативного дисбалансу (indicatedImbalance)')
plt.xlabel('Період розрахунку')
plt.ylabel('Дисбаланс')
plt.legend(title="Версія прогнозу", loc='best')
plt.grid(True)
plt.show()

####################################################
import time
import requests
import pandas as pd
# ... (весь ваш попередній код і функції fetch_data) ...

# === КОНФІГУРАЦІЯ ОНОВЛЕННЯ ===
# Інтервал оновлення у секундах (30 хвилин = 1800 секунд)
REFRESH_INTERVAL_SECONDS = 10##1800 
# Файл для зберігання історії прогнозу
HISTORY_FILE = 'forecast_history.csv' 
# ==============================

def run_refresh_loop():
    """Запускає петлю оновлення, яка періодично опитує API."""
    
    # Спроба завантажити попередню історію, якщо вона існує
    try:
        history_df = pd.read_csv(HISTORY_FILE)
        print(f"Завантажено попередню історію з {HISTORY_FILE}.")
    except FileNotFoundError:
        history_df = pd.DataFrame()
        print("Історія прогнозу не знайдена. Створення нової.")

    while True:
        print("\n=== ПОЧАТОК НОВОГО ЦИКЛУ ОНОВЛЕННЯ ===")
        
        # 1. Виконання обох запитів для 24-годинного покриття
        data_part1 = fetch_data(PREVIOUS_DAY_UTC, periods_prev_day)
        data_part2 = fetch_data(SELECTED_DAY_UTC, periods_selected_day)
        
        combined_data = data_part1 + data_part2
        
        if combined_data:
            new_df = pd.DataFrame(combined_data)
            new_df['publishTime'] = pd.to_datetime(new_df['publishTime'])
            
            # 2. Визначення останньої версії прогнозу, яку ми щойно отримали
            current_latest_publish_time = new_df['publishTime'].max()
            current_latest_forecast = new_df[new_df['publishTime'] == current_latest_publish_time].copy()
            
            # 3. Перевірка, чи це нова версія
            if not history_df.empty:
                # Знаходимо час публікації останньої збереженої версії
                last_saved_publish_time = history_df['publishTime'].max()
                
                if current_latest_publish_time > last_saved_publish_time:
                    print(f"🆕 ЗНАЙДЕНО НОВИЙ ПРОГНОЗ! Час публікації: {current_latest_publish_time}")
                    
                    # Додаємо нову версію до історії
                    history_df = pd.concat([history_df, current_latest_forecast], ignore_index=True)
                    
                    # Зберігаємо оновлену історію
                    history_df.to_csv(HISTORY_FILE, index=False)
                    
                    # Тут викликаємо функцію візуалізації
                    visualize_forecast_evolution(history_df, last_saved_publish_time)
                else:
                    print(f"☑️ Прогноз не оновлювався. Остання версія: {current_latest_publish_time}")
            else:
                # Перший запуск
                history_df = current_latest_forecast
                history_df.to_csv(HISTORY_FILE, index=False)
                print(f"Перший прогноз збережено. Час публікації: {current_latest_publish_time}")

        else:
            print("❌ Не вдалося отримати дані. Очікування перед повторною спробою.")

        print(f"\nОчікування {REFRESH_INTERVAL_SECONDS} секунд...")
        time.sleep(REFRESH_INTERVAL_SECONDS)

# Щоб запустити петлю:
#run_refresh_loop()


def visualize_forecast_evolution(df_history, previous_publish_time):
    """
    Відображає останній прогноз і порівнює його з попереднім.
    """
    
    # 1. Знаходимо дві останні версії
    latest_publish_time = df_history['publishTime'].max()
    
    # Фільтруємо дані тільки для двох останніх версій
    df_latest = df_history[df_history['publishTime'] == latest_publish_time].sort_values(by=['settlementPeriod'])
    df_previous = df_history[df_history['publishTime'] == previous_publish_time].sort_values(by=['settlementPeriod'])

    plt.figure(figsize=(14, 8))
    
    # 2. Відображення попередньої версії (як фон)
    plt.plot(df_previous['settlementPeriod'], 
             df_previous['indicatedImbalance'], 
             label=f'Попередній прогноз ({pd.to_datetime(previous_publish_time).strftime("%H:%M")})', 
             color='gray', 
             linestyle='--', 
             alpha=0.7)

    # 3. Відображення нової версії (яскравіше)
    plt.plot(df_latest['settlementPeriod'], 
             df_latest['indicatedImbalance'], 
             label=f'Новий прогноз ({pd.to_datetime(latest_publish_time).strftime("%H:%M")})', 
             color='blue', 
             linewidth=2)

    # 4. Візуальний індикатор зміни (Виділення області між двома версіями)
    # Щоб порівняння було коректним, потрібно об'єднати дані по settlementPeriod
    df_compare = pd.merge(df_latest, df_previous, 
                          on=['settlementPeriod'], 
                          suffixes=('_new', '_prev'))
    
    # Виділення кольором області, де прогноз зріс або впав
    plt.fill_between(df_compare['settlementPeriod'], 
                     df_compare['indicatedImbalance_new'], 
                     df_compare['indicatedImbalance_prev'], 
                     where=(df_compare['indicatedImbalance_new'] > df_compare['indicatedImbalance_prev']), 
                     facecolor='green', 
                     alpha=0.2, 
                     label='Прогноз збільшився')

    plt.fill_between(df_compare['settlementPeriod'], 
                     df_compare['indicatedImbalance_new'], 
                     df_compare['indicatedImbalance_prev'], 
                     where=(df_compare['indicatedImbalance_new'] < df_compare['indicatedImbalance_prev']), 
                     facecolor='red', 
                     alpha=0.2, 
                     label='Прогноз зменшився')

    plt.title(f'Еволюція прогнозу дисбалансу: {SELECTED_DAY_UTC}')
    plt.xlabel('Період розрахунку (UTC+2)')
    plt.ylabel('Indicated Imbalance')
    plt.legend()
    plt.grid(True)
    plt.show()
