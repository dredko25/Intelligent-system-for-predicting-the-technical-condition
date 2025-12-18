# backend/models.py
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from backend.app.database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default="viewer")

class Device(Base):
    __tablename__ = "devices"
    id = Column(Integer, primary_key=True)
    device_uid = Column(String, unique=True)
    product_type = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    readings = relationship("SensorReading", back_populates="device")

class SensorReading(Base):
    __tablename__ = "sensor_readings"
    id = Column(Integer, primary_key=True)
    device_id = Column(Integer, ForeignKey("devices.id"))
    air_temp = Column(Float)
    process_temp = Column(Float)
    rotational_speed = Column(Float)
    torque = Column(Float)
    tool_wear = Column(Float)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    device = relationship("Device", back_populates="readings")
    prediction = relationship("Prediction", back_populates="reading", uselist=False)

class Prediction(Base):
    __tablename__ = "predictions"
    id = Column(Integer, primary_key=True)
    reading_id = Column(Integer, ForeignKey("sensor_readings.id"))
    predicted_rul = Column(Float)
    class_failure_type = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    reading = relationship("SensorReading", back_populates="prediction")