import zoneinfo
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from backend.app.database import get_db, SessionLocal
from backend.models import SensorReading, Prediction, Device
from backend.app.services.failure_detector import detect_failure
from backend.app.services.status import determine_status
import json
import asyncio
from datetime import datetime
from pydantic import BaseModel
from typing import Optional
import paho.mqtt.client as mqtt
from backend.app.services.auth import allow_manager_only, allow_any_staff
from typing import Optional
import os
from backend.app.services.auth import SECRET_KEY, ALGORITHM
from jose import jwt, JWTError

router = APIRouter(prefix="/api", tags=["live"])

# Модель для валідації вхідних даних
class ControlCommand(BaseModel):
    device_uid: str
    action: str
    scenario: Optional[str] = None

# Функція для форматування відповіді
def format_reading_response(reading, prediction=None):
    """Форматує дані з БД у JSON для фронтенду"""
    if not reading:
        return None
        
    # Визначаємо статус
    failure = detect_failure(reading)
    status = determine_status(failure, prediction)
    
    return {
        "device_uid": reading.device.device_uid,
        "air_temp": reading.air_temp,
        "process_temp": reading.process_temp,
        "rotational_speed": reading.rotational_speed,
        "torque": reading.torque,
        "tool_wear": reading.tool_wear,
        "timestamp": reading.timestamp.isoformat(),
        "prediction": {
            # Якщо прогнозу ще немає, вказуємо null
            "rul": prediction.predicted_rul if prediction else None,
            "failure_pred": prediction.class_failure_type if prediction else None
        },
        "detected_failure": failure,
        "status": status
    }

# Вебсокетний менеджер
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []
        self.is_broadcasting = False

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        
        # Запускаємо цикл розсилки, якщо він ще не працює
        if not self.is_broadcasting:
            self.is_broadcasting = True
            asyncio.create_task(self.broadcast_loop())

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        if not self.active_connections: return
            
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)
        
        for connection in disconnected:
            self.disconnect(connection)
    
    async def broadcast_loop(self):
        """
        Оптимізований цикл:
        1. Опитує ВСІ активні пристрої.
        2. Використовує LEFT JOIN, щоб не чекати на Predictor.
        3. Спить всього 0.1с для плавності.
        """
        last_sent_ids = {}

        while self.is_broadcasting:
            if not self.active_connections:
                await asyncio.sleep(1)
                continue

            db = SessionLocal()
            try:
                devices = db.query(Device).all()
                
                for device in devices:
                    latest = (
                        db.query(SensorReading, Prediction)
                        .outerjoin(Prediction, SensorReading.id == Prediction.reading_id)
                        .filter(SensorReading.device_id == device.id)
                        .order_by(SensorReading.timestamp.desc())
                        .first()
                    )
                    
                    if latest:
                        reading, prediction = latest
                        
                        # Відправляємо тільки якщо це нові дані (або якщо з'явився прогноз для старих)
                        last_id = last_sent_ids.get(device.device_uid)
                        current_id_sig = f"{reading.id}_{prediction.id if prediction else 'no'}"
                        
                        if last_id != current_id_sig:
                            data = format_reading_response(reading, prediction)
                            data["type"] = "live_data"
                            await self.broadcast(data)
                            last_sent_ids[device.device_uid] = current_id_sig

            except Exception as e:
                print(f"Error in broadcast loop: {e}")
            finally:
                db.close()
            
            await asyncio.sleep(0.1) 

manager = ConnectionManager()

# API ендпоінти
@router.get("/latest")
def get_latest_readings(db: Session = Depends(get_db)):
    """Повертає останні дані для ВСІХ пристроїв миттєво"""
    devices = db.query(Device).all()
    results = []
    
    for device in devices:
        # Використовуємо outerjoin (LEFT JOIN), щоб не чекати предиктора
        latest = (
            db.query(SensorReading, Prediction)
            .outerjoin(Prediction, SensorReading.id == Prediction.reading_id)
            .filter(SensorReading.device_id == device.id)
            .order_by(SensorReading.timestamp.desc())
            .first()
        )
        
        if latest:
            reading, prediction = latest
            data = format_reading_response(reading, prediction)
            results.append(data)
    
    if not results:
        return {"error": "No data available"}
    
    if len(results) == 1:
        return results[0]
        
    return results[0] 

@router.websocket("/ws/live")
async def websocket_endpoint(websocket: WebSocket):
    # Перевірка токена
    token = websocket.cookies.get("access_token")
    
    if not token:
        # Якщо токена немає - закриваємо з'єднання (Policy Violation)
        await websocket.close(code=1008)
        return

    try:
        # Перевіряємо валідність токена
        jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        # Якщо токен підроблений або прострочений
        await websocket.close(code=1008)
        return
    await manager.connect(websocket)
    try:
        # При підключенні відразу відправляємо останні наявні дані по ВСІХ девайсах
        db = SessionLocal()
        devices = db.query(Device).all()
        for device in devices:
             latest = (
                db.query(SensorReading, Prediction)
                .outerjoin(Prediction, SensorReading.id == Prediction.reading_id)
                .filter(SensorReading.device_id == device.id)
                .order_by(SensorReading.timestamp.desc())
                .first()
            )
             if latest:
                 reading, prediction = latest
                 data = format_reading_response(reading, prediction)
                 data["type"] = "live_data"
                 await websocket.send_json(data)
        db.close()
        
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@router.post("/device/control")
def control_device(command: ControlCommand, user = Depends(allow_any_staff)):
    try:
        client = mqtt.Client()
        
        # Беремо хост з Docker-змінної ("mosquitto"), 
        # або "localhost" якщо запускаємо локально без докера.
        mqtt_host = os.getenv("MQTT_HOST", "localhost")
        
        client.connect(mqtt_host, 1883, 60)
        
        payload = {"action": command.action, "scenario": command.scenario}
        client.publish(f"commands/{command.device_uid}", json.dumps(payload))
        client.disconnect()
        
        msg = "Виконано"
        if command.action == "change_scenario":
            names = {
                "normal": "Нормальний", 
                "twf": "Знос", 
                "hdf": "Перегрів", 
                "pwf": "Живлення", 
                "osf": "Перевантаження", 
                "rnf": "Випадкова", 
                "worn_stress": "Навантаження"
            }
            sc_name = names.get(command.scenario, command.scenario)
            msg = f"Сценарій: {sc_name}"
        elif command.action == "repair":
            msg = "Ремонт завершено"
            
        return {"status": "success", "message": msg, "user": user.username}
    except Exception as e:
        print(f"MQTT Error: {e}")
        return {"status": "error", "message": str(e)}

@router.get("/device/{device_uid}/charts")
def get_device_charts(
    device_uid: str, 
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db),
    user = Depends(allow_any_staff)
):
    # 1. Знаходимо пристрій
    device = db.query(Device).filter(Device.device_uid == device_uid).first()
    if not device: return {"error": "Device not found"}
    
    # 2. Базовий запит
    query = db.query(SensorReading).filter(SensorReading.device_id == device.id)
    
    # Визначаємо зони
    kyiv_tz = zoneinfo.ZoneInfo("Europe/Kyiv")
    utc_tz = zoneinfo.ZoneInfo("UTC")
    
    # 3. Логіка фільтрації
    if start_date and end_date:
        # --- РЕЖИМ ІСТОРІЇ ---
        try:
            # Input (Kyiv) -> DB (UTC)
            start_naive = datetime.fromisoformat(start_date)
            end_naive = datetime.fromisoformat(end_date)
            
            # Додаємо часовий пояс Київ
            start_kyiv = start_naive.replace(tzinfo=kyiv_tz)
            end_kyiv = end_naive.replace(tzinfo=kyiv_tz)

            # Конвертуємо в UTC для пошуку в базі
            start_utc = start_kyiv.astimezone(utc_tz)
            end_utc = end_kyiv.astimezone(utc_tz)
            
            query = query.filter(SensorReading.timestamp >= start_utc, SensorReading.timestamp <= end_utc)
            query = query.order_by(SensorReading.timestamp.asc()) # Для історії - від старого до нового
            limit = 2000
        except ValueError:
            return {"error": "Invalid date format"}
    else:
        # --- LIVE РЕЖИМ (Останні дані) ---
        query = query.order_by(SensorReading.timestamp.desc()) # Спочатку найновіші
        limit = 100
    
    # 4. Виконуємо запит (ОДИН РАЗ!)
    readings = query.limit(limit).all()
    
    # Якщо це був запит останніх даних (Live), перевертаємо їх, щоб графік малювався зліва направо
    if not (start_date and end_date):
        readings = list(reversed(readings))
    
    # 5. Формуємо відповідь
    charts_data = {
        "device_uid": device_uid,
        "product_type": device.product_type,
        "charts": {
            "air_temp": {"title": "Температура повітря", "data": []},
            "process_temp": {"title": "Температура процесу", "data": []},
            "rotational_speed": {"title": "Швидкість обертання", "data": []},
            "torque": {"title": "Крутний момент", "data": []},
            "tool_wear": {"title": "Знос інструменту", "data": []},
            "power": {"title": "Потужність", "data": []},
            "temp_difference": {"title": "Різниця температур", "data": []}
        }
    }
    
    for r in readings:
        ts = r.timestamp.isoformat()
        
        charts_data["charts"]["air_temp"]["data"].append({"x": ts, "y": r.air_temp})
        charts_data["charts"]["process_temp"]["data"].append({"x": ts, "y": r.process_temp})
        charts_data["charts"]["rotational_speed"]["data"].append({"x": ts, "y": r.rotational_speed})
        charts_data["charts"]["torque"]["data"].append({"x": ts, "y": r.torque})
        charts_data["charts"]["tool_wear"]["data"].append({"x": ts, "y": r.tool_wear})
        
        power = r.torque * r.rotational_speed * 2 * 3.14159 / 60
        charts_data["charts"]["power"]["data"].append({"x": ts, "y": power})
        charts_data["charts"]["temp_difference"]["data"].append({"x": ts, "y": r.process_temp - r.air_temp})
        
    return charts_data

@router.post("/device/control")
def control_device(command: ControlCommand):
    try:
        # Підключаємося
        client = mqtt.Client()
        client.connect("localhost", 1883, 60)
        
        # Відправляємо
        payload = {"action": command.action, "scenario": command.scenario}
        client.publish(f"commands/{command.device_uid}", json.dumps(payload))
        client.disconnect()
        
        # Формуємо відповідь
        msg = "Виконано"
        if command.action == "change_scenario":
            msg = f"Сценарій: {command.scenario}"
        elif command.action == "repair":
            msg = "Ремонт завершено"
            
        return {"status": "success", "message": msg}
        
    except Exception as e:
        print(f"MQTT Error: {e}")
        return {"status": "error", "message": "Помилка сервера"}