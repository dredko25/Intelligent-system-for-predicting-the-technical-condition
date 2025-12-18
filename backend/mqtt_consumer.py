import json
import time
import paho.mqtt.client as mqtt
from sqlalchemy.orm import Session
from backend.app.database import SessionLocal
from backend.models import Device, SensorReading
from datetime import datetime
import traceback
import os

MQTT_HOST = os.getenv("MQTT_HOST", "mosquitto")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_TOPIC = "sensors/#"


def save_reading_to_db(data: dict):
    """Зберігає одне вимірювання у БД."""

    db: Session = SessionLocal()

    try:
        # 1) Шукаємо пристрій
        device = db.query(Device).filter(Device.device_uid == data["device_uid"]).first()

        # Якщо не існує — створюємо
        if not device:
            device = Device(
                device_uid=data["device_uid"],
                product_type=data["product_type"]
            )
            db.add(device)
            db.commit()
            db.refresh(device)

        # 3) Створюємо вимірювання
        reading = SensorReading(
            device_id=device.id,
            air_temp=data["air_temp"],
            process_temp=data["process_temp"],
            rotational_speed=data["rotational_speed"],
            torque=data["torque"],
            tool_wear=data["tool_wear"],
        )

        db.add(reading)
        db.commit()

    except Exception as e:
        print("DB save error:", e)
        traceback.print_exc()

    finally:
        db.close()


def on_connect(client, userdata, flags, rc):
    print(f"Connected to MQTT with code {rc}")
    client.subscribe(MQTT_TOPIC)


def on_message(client, userdata, msg):
    try:
        payload = msg.payload.decode()
        data = json.loads(payload)

        # перевірка обов'язкових полів
        required = [
            "device_uid", "product_type", "air_temp", "process_temp",
            "rotational_speed", "torque", "tool_wear"
        ]
        if not all(k in data for k in required):
            print("Invalid payload:", data)
            return

        save_reading_to_db(data)


    except Exception as e:
        print("Error while handling MQTT message:", e)
        traceback.print_exc()


def run():
    client = mqtt.Client()

    client.on_connect = on_connect
    client.on_message = on_message

    while True:
        try:
            client.connect(MQTT_HOST, MQTT_PORT, 60)
            client.loop_forever()
        except Exception as e:
            print("MQTT connection error, reconnecting in 3 sec:", e)
            time.sleep(3)

async def async_notify():
    from backend.app.routers.live import notify_new_reading
    # Отримуємо останні дані з прогнозами
    from backend.app.database import SessionLocal
    from backend.app.routers.live import get_latest_readings
    db = SessionLocal()
    latest_data = get_latest_readings(db)
    db.close()
    
    if "error" not in latest_data:
        await notify_new_reading(latest_data)

if __name__ == "__main__":
    print("MQTT Consumer started. Listening for messages...")
    run()
