import sys
import os
from backend.app.database import engine, Base
from backend import models 

if __name__ == "__main__":
    print("Створення таблиць...")
    Base.metadata.create_all(bind=engine)
    print("Таблиці успішно створено.")