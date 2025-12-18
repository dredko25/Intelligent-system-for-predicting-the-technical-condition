from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from backend.app.database import get_db
from backend.models import SensorReading, Device, Prediction
from backend.app.services.auth import allow_analyst_access
import csv
import io
from datetime import datetime
from typing import Optional
import zoneinfo

router = APIRouter(prefix="/api/export", tags=["Export"])

@router.get("/history/{device_uid}")
def export_device_history(
    device_uid: str, 
    start_date: Optional[str] = None, 
    end_date: Optional[str] = None, 
    db: Session = Depends(get_db),
    user = Depends(allow_analyst_access)
):
    device = db.query(Device).filter(Device.device_uid == device_uid).first()
    if not device:
        return {"error": "Device not found"}

    query = (
        db.query(SensorReading, Prediction)
        .outerjoin(Prediction, SensorReading.id == Prediction.reading_id)
        .filter(SensorReading.device_id == device.id)
    )

    # Визначаємо зони
    kyiv_tz = zoneinfo.ZoneInfo("Europe/Kyiv")
    utc_tz = zoneinfo.ZoneInfo("UTC")

    if start_date and end_date:
        try:
            # 1. Отримуємо час від браузера (наприклад, 14:00)
            start_naive = datetime.fromisoformat(start_date)
            end_naive = datetime.fromisoformat(end_date)
            
            # 2. Кажемо це час у Києві (14:00 Kyiv)
            start_kyiv = start_naive.replace(tzinfo=kyiv_tz)
            end_kyiv = end_naive.replace(tzinfo=kyiv_tz)
            
            # 3. Конвертуємо в UTC для бази даних (12:00 UTC)
            start_utc = start_kyiv.astimezone(utc_tz)
            end_utc = end_kyiv.astimezone(utc_tz)

            # 4. Фільтруємо базу по UTC
            query = query.filter(SensorReading.timestamp >= start_utc, SensorReading.timestamp <= end_utc)
            query = query.order_by(SensorReading.timestamp.asc())
            
            filename_dates = f"_{start_naive.strftime('%Y%m%d')}-{end_naive.strftime('%Y%m%d')}"
        except ValueError:
            return {"error": "Invalid date format"}
    else:
        query = query.order_by(SensorReading.timestamp.desc()).limit(5000)
        filename_dates = "_FULL"

    def iter_csv():
        output = io.StringIO()
        writer = csv.writer(output)
        
        writer.writerow([
            "Timestamp (Kyiv)", "Air Temp [K]", "Process Temp [K]", 
            "Speed [rpm]", "Torque [Nm]", "Tool Wear [min]", 
            "Predicted RUL [h]", "Failure Status"
        ])
        yield output.getvalue()
        output.seek(0)
        output.truncate(0)

        for reading, pred in query:
            # --- Конвертація UTC з бази назад у Київ для звіту ---
            if reading.timestamp.tzinfo:
                local_time = reading.timestamp.astimezone(kyiv_tz)
            else:
                local_time = reading.timestamp.replace(tzinfo=utc_tz).astimezone(kyiv_tz)
            
            ts_str = local_time.strftime("%Y-%m-%d %H:%M:%S")

            writer.writerow([
                ts_str,
                reading.air_temp,
                reading.process_temp,
                reading.rotational_speed,
                reading.torque,
                reading.tool_wear,
                f"{pred.predicted_rul:.2f}" if pred else "",
                pred.class_failure_type if pred else "Normal"
            ])
            yield output.getvalue()
            output.seek(0)
            output.truncate(0)

    filename = f"history_{device_uid}{filename_dates}.csv"
    
    return StreamingResponse(
        iter_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )