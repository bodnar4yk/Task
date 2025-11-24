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

latest_publish_time = df['publishTime'].max()
#print(latest_publish_time)
latest_forecast = df[df['publishTime'] == latest_publish_time]
#print(latest_forecast)

def clean_and_process_df(df, tz):
    """Очищує та конвертує колонки часу для візуалізації."""
    if df.empty:
        return df

    # 1. Забезпечення правильного типу datetime
    df['publishTime'] = pd.to_datetime(df['publishTime'])
    df['startTime'] = pd.to_datetime(df['startTime'])

    # 2. Обробка time-zone (для уникнення TypeError: Already tz-aware)
    # Знімаємо будь-яку TZ інформацію, якщо вона є
    df['publishTime'] = df['publishTime'].dt.tz_localize(None)
    df['startTime'] = df['startTime'].dt.tz_localize(None)

    # 3. Призначаємо UTC
    df['startTime_UTC'] = df['startTime'].dt.tz_localize('UTC')
    df['publishTime_UTC'] = df['publishTime'].dt.tz_localize('UTC')
    
    # 4. Конвертуємо у локальний час (CET/CEST)
    df['startTime_Local'] = df['startTime_UTC'].dt.tz_convert(tz)
    df['publishTime_Local'] = df['publishTime_UTC'].dt.tz_convert(tz)  

    # Створюємо єдиний індекс для графіка
    df['local_period_label'] = df['publishTime_Local'].dt.strftime('%H:%M') + ' (' + df['publishTime_Local'].dt.strftime('%d/%m') + ')'
    
    return df


# ###############################################################################
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import time
from datetime import datetime

# Інтервал оновлення у секундах (30 хвилин = 1800 секунд)
REFRESH_INTERVAL_SECONDS = 10 #1800
TARGET_TIMEZONE = 'Europe/Warsaw'

clean_and_process_df(df,TARGET_TIMEZONE)

# Групування за часом публікації (це різні версії прогнозу)
forecast_versions = df['publishTime_Local'].unique()
df['local_period_label'] = df['publishTime_Local'].dt.strftime('%H:%M') + ' (' + df['publishTime_Local'].dt.strftime('%d/%m') + ')'

# ====================================================================
# ФУНКЦІЇ ВІЗУАЛІЗАЦІЇ
# ====================================================================

def visualize_forecast_evolution(df_history, previous_publish_time):
    """
    Створює графік еволюції, порівнюючи останній і попередній прогнози з візуальним індикатором.
    """
    
    latest_publish_time = df_history['publishTime'].max()
    
    df_latest = df_history[df_history['publishTime'] == latest_publish_time].sort_values(by=['settlementPeriod'])
    df_previous = df_history[df_history['publishTime'] == previous_publish_time].sort_values(by=['settlementPeriod'])
    
    # Готуємо індекси для осі X
    x_labels = df_latest['local_period_label'].values
    x_index = np.arange(len(x_labels))

    plt.figure(figsize=(16, 9))
    
    # 1. Відображення попередньої версії
    plt.plot(x_index, 
             df_previous['indicatedImbalance'].values, 
             label=f'Попередній прогноз ({pd.to_datetime(previous_publish_time).strftime("%H:%M %d/%m")})', 
             color='gray', 
             linestyle='--', 
             alpha=0.7)

    # 2. Відображення нової версії
    plt.plot(x_index, 
             df_latest['indicatedImbalance'].values, 
             label=f'Новий прогноз ({pd.to_datetime(latest_publish_time).strftime("%H:%M %d/%m")})', 
             color='blue', 
             linewidth=2)

    # 3. Візуальний індикатор (заштриховані області)
    df_compare = pd.merge(df_latest[['settlementPeriod', 'indicatedImbalance']], 
                          df_previous[['settlementPeriod', 'indicatedImbalance']], 
                          on=['settlementPeriod'], 
                          suffixes=('_new', '_prev'))
    
    # Прогноз збільшився (зелена область)
    plt.fill_between(x_index, 
                     df_compare['indicatedImbalance_new'], 
                     df_compare['indicatedImbalance_prev'], 
                     where=(df_compare['indicatedImbalance_new'] > df_compare['indicatedImbalance_prev']), 
                     facecolor='green', 
                     alpha=0.2, 
                     label='Прогноз збільшився')

    # Прогноз зменшився (червона область)
    plt.fill_between(x_index, 
                     df_compare['indicatedImbalance_new'], 
                     df_compare['indicatedImbalance_prev'], 
                     where=(df_compare['indicatedImbalance_new'] < df_compare['indicatedImbalance_prev']), 
                     facecolor='red', 
                     alpha=0.2, 
                     label='Прогноз зменшився')
    
    # 4. Налаштування графіку
    plt.xticks(x_index[::4], x_labels[::4], rotation=45, ha='right')
    plt.title(f'Еволюція прогнозу дисбалансу для {SELECTED_DAY_UTC} (Час: {TARGET_TIMEZONE})')
    plt.xlabel('Час (Період розрахунку)')
    plt.ylabel('Indicated Imbalance (MW)')
    plt.legend()
    plt.tight_layout()
    plt.grid(True, linestyle=':', alpha=0.6)
    plt.savefig('forecast_evolution_plot.png')
    plt.show()
    # 


def create_current_day_graph(df):
    """Створює окремий графік для поточного (останнього) прогнозу."""
    # Оскільки цей датасет оновлюється двічі на годину, 
    # ми показуємо останню версію як "поточний прогноз".

    latest_publish_time = df['publishTime'].max()
    df_current = df[df['publishTime'] == latest_publish_time].sort_values(by=['settlementPeriod'])
    
    x_labels = df_current['local_period_label'].values
    x_index = np.arange(len(x_labels))

    plt.figure(figsize=(12, 7))
    
    plt.plot(x_index, 
             df_current['indicatedImbalance'].values, 
             label=f'Остання версія ({pd.to_datetime(latest_publish_time).strftime("%H:%M %d/%m")})', 
             color='orange', 
             linewidth=2)

    plt.xticks(x_index[::4], x_labels[::4], rotation=45, ha='right')
    plt.title(f'Поточний (останній) прогноз дисбалансу для {SELECTED_DAY_UTC}')
    plt.xlabel('Час (CET)')
    plt.ylabel('Indicated Imbalance (MW)')
    plt.legend()
    plt.tight_layout()
    plt.grid(True, linestyle=':', alpha=0.6)
    plt.savefig('current_forecast_plot.png')
    plt.show()

import pmdarima as pm
from statsmodels.tools.sm_exceptions import HessianInversionWarning
import warnings

######For cast use Arima######## 
def forecast_next_periods(df_history, periods_to_forecast=4):
    """
    Виконує прогнозування методом Auto ARIMA на основі останнього прогнозу
    у DataFrame історії.
    """
    
    warnings.filterwarnings('ignore', category=HessianInversionWarning)
    
    # 1. Вибираємо останній (найактуальніший) прогноз
    latest_publish_time = df_history['publishTime'].max()
    df_latest = df_history[df_history['publishTime'] == latest_publish_time].copy()
    
    if df_latest.empty:
        return pd.DataFrame()

    # 2. Перетворюємо дані на часовий ряд для моделювання
    # Використовуємо 'indicatedImbalance' як цільову змінну
    time_series = df_latest.set_index('startTime_Local')['indicatedImbalance']
    
    # Модель Auto ARIMA автоматично знаходить найкращі параметри (p, d, q)
    try:
        model = pm.auto_arima(time_series, 
                              seasonal=True,
                              m=48, # Сезонність - 48 півгодинних періодів на день
                              stepwise=True,
                              suppress_warnings=True,
                              error_action='ignore')

        # 3. Прогнозування наступних N періодів
        forecast_values, conf_int = model.predict(n_periods=periods_to_forecast, 
                                                  return_conf_int=True)
        
        # 4. Створення DataFrame для результатів
        last_time = time_series.index[-1]
        
        # Генеруємо мітки часу для прогнозованих періодів (кожні 30 хвилин)
        forecast_index = pd.date_range(start=last_time, periods=periods_to_forecast + 1, freq='30min')[1:]
        
        forecast_df = pd.DataFrame({
            'startTime_Local': forecast_index,
            'PredictedImbalance': forecast_values,
            'LowerBound': conf_int[:, 0],
            'UpperBound': conf_int[:, 1]
        })
        
        print(f"✅ Прогноз розраховано для {periods_to_forecast} наступних періодів.")
        return forecast_df
        
    except Exception as e:
        print(f"❌ Помилка при розрахунку ARIMA: {e}")
        return pd.DataFrame()

# ====================================================================
# ПЕТЛЯ ОНОВЛЕННЯ (ЗАПУСК)
# ====================================================================
HISTORY_FILE=df

def run_refresh_loop():
    """Головна функція, що реалізує петлю оновлення."""
    
    # Спроба завантажити історію, якщо вона існує
    try:
        history_df = HISTORY_FILE
        history_df = clean_and_process_df(history_df, TARGET_TIMEZONE)
        print(f"Завантажено попередню історію. Кількість версій: {history_df['publishTime'].nunique()}")
    except FileNotFoundError:
        history_df = pd.DataFrame()
        print("Історія прогнозу не знайдена. Створення нової.")

    while True:
        print(f"\n=== ПОЧАТОК ЦИКЛУ ОНОВЛЕННЯ: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")
        
        # 1. Отримання даних
        data_part1 = fetch_data(PREVIOUS_DAY_UTC, periods_prev_day)
        data_part2 = fetch_data(SELECTED_DAY_UTC, periods_selected_day)
        combined_data = data_part1 + data_part2
        
        if not combined_data:
            print("❌ Не вдалося отримати дані. Очікування перед повторною спробою.")
            time.sleep(REFRESH_INTERVAL_SECONDS)
            continue
            
        new_df = pd.DataFrame(combined_data)
        new_df = clean_and_process_df(new_df, TARGET_TIMEZONE)
        
        # Визначення останнього отриманого прогнозу
        current_latest_publish_time = new_df['publishTime'].max()
        current_latest_forecast = new_df[new_df['publishTime'] == current_latest_publish_time].copy()
        
        if history_df.empty:
            # Перший запуск
            history_df = current_latest_forecast
            history_df.to_csv(HISTORY_FILE, index=False)
            print(f"Перший прогноз збережено. Час публікації: {current_latest_publish_time}")
            create_current_day_graph(history_df)
        else:
            last_saved_publish_time = history_df['publishTime'].max()
            
            if current_latest_publish_time > last_saved_publish_time:
                # Знайдено нові дані!
                print(f"🆕 ЗНАЙДЕНО НОВИЙ ПРОГНОЗ! Час публікації: {current_latest_publish_time}")
                
                # Додавання нової версії до історії
                history_df = pd.concat([history_df, current_latest_forecast], ignore_index=True)
                history_df = history_df.drop_duplicates(subset=['settlementPeriod', 'publishTime'], keep='last')
                history_df.to_csv(HISTORY_FILE, index=False)
                
                # Візуалізація: Еволюція та поточний стан
                visualize_forecast_evolution(history_df, last_saved_publish_time)
                # Викликаємо функцію для прогнозування
            forecast_data = forecast_next_periods(history_df, periods_to_forecast=4)
            
            if not forecast_data.empty:
                # Зберігаємо прогноз у окремий файл
                FORECAST_OUTPUT_FILE = 'short_term_forecast.csv'
                forecast_data.to_csv(FORECAST_OUTPUT_FILE, index=False)
                print(f"Прогноз на наступні 2 години збережено у {FORECAST_OUTPUT_FILE}")
                create_current_day_graph(current_latest_forecast)
            else:
                print(f"☑️ Прогноз не оновлювався. Остання версія: {current_latest_publish_time}")
                # Все одно створюємо поточний графік, навіть якщо не було змін
                create_current_day_graph(current_latest_forecast)

        print(f"\nОчікування {REFRESH_INTERVAL_SECONDS} секунд перед наступним опитуванням...")
        
        time.sleep(REFRESH_INTERVAL_SECONDS)

# === ЗАПУСК ===
#run_refresh_loop()