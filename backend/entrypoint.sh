#!/bin/bash
set -e

echo "Створення таблиць БД..."
python -m backend.create_tables

echo "Створення користувачів..."
python -m backend.create_users

echo "Запуск сервісу прогнозування..."
python -m backend.app.services.predictor &

echo "Запуск MQTT Consumer..."
python -m backend.mqtt_consumer &

echo "Запуск симулятора..."
python -u -m backend.simulator_publish --num-devices 2 --interval 2 --mqtt --mqtt-host mosquitto &

echo "Запуск вебсервера"
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload