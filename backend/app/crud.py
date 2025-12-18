# backend/app/crud.py
from sqlalchemy.orm import Session
from datetime import datetime
from sqlalchemy import select
from backend.models import Device, SensorReading, Prediction, User

# Створити або отримати device по device_uid
def get_or_create_device(db: Session, device_uid: str, product_type: str = None):
    device = db.query(Device).filter(Device.device_uid == device_uid).first()
    if device:
        # опціонально оновити product_type якщо прийшов новий
        if product_type and device.product_type != product_type:
            device.product_type = product_type
            db.commit()
            db.refresh(device)
        return device
    device = Device(device_uid=device_uid, product_type=product_type)
    db.add(device)
    db.commit()
    db.refresh(device)
    return device

# Вставити сенсорне reading (payload — dict)
def insert_sensor_reading(db: Session, payload: dict):
    # payload має містити ключі з назвами колонок: Air temperature [K], etc.
    device_uid = payload.get("device_uid") or payload.get("Device_UID") or payload.get("UDI")  # різні можливі імена
    product_type = payload.get("product_type") or payload.get("Product variant") or payload.get("Product_ID")
    device = get_or_create_device(db, device_uid=device_uid, product_type=product_type)

    reading = SensorReading(
        device_id = device.id,
        air_temp = payload.get("Air temperature [K]") or payload.get("air_temp"),
        process_temp = payload.get("Process temperature [K]") or payload.get("process_temp"),
        rotational_speed = payload.get("Rotational speed [rpm]") or payload.get("rotational_speed"),
        torque = payload.get("Torque [Nm]") or payload.get("torque"),
        tool_wear = payload.get("Tool wear [min]") or payload.get("tool_wear"),
        timestamp = payload.get("ts")  # SQLAlchemy автоматично підставить NOW() якщо None
    )
    db.add(reading)
    db.commit()
    db.refresh(reading)
    return reading

def get_next_unpredicted_reading(db: Session):
    """Повертає перший запис, для якого ще немає прогнозу."""
    # Використовуємо select() замість db.query().subquery()
    subq = select(Prediction.reading_id)
    
    # Фільтруємо записи, ID яких НЕМАЄ в підзапиті прогнозів
    row = db.query(SensorReading).filter(
        ~SensorReading.id.in_(subq)
    ).order_by(SensorReading.id.asc()).first()
    
    return row

def insert_prediction_for_reading(db: Session, reading_id: int, predicted_rul: float, class_failure_type: str = "Normal"):
    """
    Зберігає результат роботи моделі та детектора.
    
    Args:
        reading_id: ID запису сенсорів
        predicted_rul: Прогнозований час життя (або 0.0, якщо аварія)
        class_failure_type: Тип поломки ('Normal', 'PWF', 'TWF', 'HDF', 'OSF')
        probability: (Опціонально) Вірогідність поломки, якщо використовується класифікатор
    """
    pred = Prediction(
        reading_id = reading_id,
        predicted_rul = float(predicted_rul),
        class_failure_type = class_failure_type
    )
    db.add(pred)
    db.commit()
    db.refresh(pred)
    return pred
