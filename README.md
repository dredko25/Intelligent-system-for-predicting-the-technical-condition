# Інтелектуальна система прогнозування технічного стану обладнання на основі сенсорних даних

##  Основний функціонал

*   **IoT Симуляція** — генерація телеметрії на основі датасету AI4I 2020.
*   **Гібридний аналіз** — поєднання детермінованих правил (для поломок) та нейромережі (для прогнозу RUL).
*   **Real-time Dashboard** — графіки та статус обладнання через WebSockets.
*   **MQTT** — надійна передача даних між сенсорами та сервером.

##  Технологічний стек

*   **Backend:** Python, FastAPI, Uvicorn, SQLAlchemy.
*   **ML:** TensorFlow/Keras, Scikit-learn, Pandas.
*   **Data:** PostgreSQL, Eclipse Mosquitto (MQTT).
*   **Frontend:** HTML5, Bootstrap 5, Jinja2.
*   **DevOps:** Docker, Docker Compose.

##  Швидкий старт

Для запуску необхідний встановлений **Docker**.

1.  **Клонуйте репозиторій:**

    ```bash
    git clone <repository_url>
    cd equipment-condition-prediction
    ```

2.  **Запустіть проєкт:**

    ```bash
    docker-compose up --build
    ```

3.  **Відкрийте в браузері:**

    Перейдіть за посиланням: [http://localhost:8000](http://127.0.0.1:8000/login)

##  Тестові доступи

Система автоматично створює користувачів при першому запуску:

| Роль      | Логін      | Пароль  | Можливості                            |
| --------- | ---------- | ------- | ------------------------------------- |
| **Manager** | `manager1` | `pass123` | Перегляд графіків, завантаження історії |
| **Analyst** | `analyst1` | `pass123` | Повний доступ          |
| **Worker**  | `worker1`  | `pass123` | Лише моніторинг поточного стану         |

##  Архітектура

*   **Simulator** → (MQTT) → **Mosquitto**
*   **Mosquitto** → (MQTT) → **Consumer Service**
*   **Consumer Service** → (SQL) → **PostgreSQL** (запис даних)
*   **Predictor Service** ↔ **PostgreSQL** (читання даних, запис прогнозів)
*   **Web Client** ↔ (WebSocket) ↔ **API Server**
*   **API Server** → (SQL) → **PostgreSQL** (читання даних для візуалізації)
