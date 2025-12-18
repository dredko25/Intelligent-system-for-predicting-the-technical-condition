# backend/app/services/model_loader.py
import os
from pathlib import Path
import numpy as np
import pandas as pd
import joblib
from tensorflow.keras.models import load_model

ROOT = Path(__file__).resolve().parents[2]
MODEL_DIR = ROOT / "model"

MODEL_PATH = MODEL_DIR / "best_rul_model.keras"
SCALER_PATH = MODEL_DIR / "rul_scaler.pkl"

_model = None
_scaler = None

def _load():
    global _model, _scaler
    if _model is None:
        if not MODEL_PATH.exists():
            raise FileNotFoundError(f"Model not found at {MODEL_PATH}")
        print("Loading Keras model from:", MODEL_PATH)
        _model = load_model(str(MODEL_PATH))
        print("Model loaded")
    if _scaler is None:
        if not SCALER_PATH.exists():
            raise FileNotFoundError(f"Scaler not found at {SCALER_PATH}")
        print("Loading scaler from:", SCALER_PATH)
        _scaler = joblib.load(str(SCALER_PATH))
        print("Scaler loaded")

def predict_rul(feature_list):

    _load()
    
    rotational_speed = feature_list[2]
    if rotational_speed < 500:
        return 0.0

    feature_names = [
        'Air temperature [K]', 
        'Process temperature [K]', 
        'Rotational speed [rpm]', 
        'Torque [Nm]', 
        'Tool wear [min]'
    ]
    
    df_features = pd.DataFrame([feature_list], columns=feature_names)
    
    arr_scaled = _scaler.transform(df_features)
    
    pred = _model.predict(arr_scaled)
    
    if hasattr(pred, "flatten"):
        val = float(pred.flatten()[0])
    else:
        val = float(pred[0])
        
    return max(0.0, val)