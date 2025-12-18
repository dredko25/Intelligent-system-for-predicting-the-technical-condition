# backend/app/services/predictor.py
import sys
import os
import time
from sqlalchemy.orm import Session

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.app.database import SessionLocal
from backend.app.crud import get_next_unpredicted_reading, insert_prediction_for_reading
from backend.app.services.model_loader import predict_rul
from backend.app.services.failure_detector import detect_failure 
from backend.models import SensorReading

def process_loop(poll_interval: float = 0.1):
    print("[PREDICTOR] Service started. Waiting for data...")
    
    while True:
        db: Session = SessionLocal()
        processed_something = False
        
        try:
            # 1. Беремо наступний запис без прогнозу
            row = get_next_unpredicted_reading(db)

            if row:
                processed_something = True
                
                # Підготовка даних для моделі
                features = [
                    getattr(row, "air_temp"),
                    getattr(row, "process_temp"),
                    getattr(row, "rotational_speed"),
                    getattr(row, "torque"),
                    getattr(row, "tool_wear")
                ]
                
                try:
                    # 2. Створюємо обгортку для детектора
                    class ReadingWrapper:
                        def __init__(self, r):
                            self.air_temp = r.air_temp
                            self.process_temp = r.process_temp
                            self.rotational_speed = r.rotational_speed
                            self.torque = r.torque
                            self.tool_wear = r.tool_wear
                            # Отримуємо тип продукту через зв'язок (якщо він завантажений) або дефолт
                            self.device = type('obj', (object,), {'product_type': 'L'}) 
                            if r.device and r.device.product_type:
                                self.device.product_type = r.device.product_type

                    # 3. Визначаємо ФАКТИЧНИЙ статус (чи є поломка прямо зараз?)
                    detected_status = detect_failure(ReadingWrapper(row))
                    
                    # 4. Логіка запису
                    if detected_status and detected_status != "Normal":
                        # Якщо Детектор знайшов поломку:
                        final_rul = 0.0
                        final_status = detected_status # Наприклад: "PWF", "TWF"
                    else:
                        # Якщо все добре, питаємо AI модель:
                        raw_rul = predict_rul(features)
                        final_rul = max(0.0, raw_rul)
                        final_status = "Normal"

                    # 5. ЗАПИС У БАЗУ ДАНИХ
                    insert_prediction_for_reading(
                        db, 
                        reading_id=row.id, 
                        predicted_rul=final_rul, 
                        class_failure_type=final_status
                    )
                    
                    if final_status != "Normal":
                         print(f"[PREDICTOR] FAILURE {final_status} SAVED! ID={row.id}")
                    
                except Exception as e:
                    print(f"Prediction error for ID {row.id}: {e}")
            
        except Exception as e:
            print("Database loop error:", e)
            time.sleep(5)
            
        finally:
            db.close()

        if not processed_something:
            time.sleep(poll_interval)

if __name__ == "__main__":
    process_loop()