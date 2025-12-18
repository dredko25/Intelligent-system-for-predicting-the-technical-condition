import pandas as pd
import numpy as np
import joblib
from tensorflow.keras.models import load_model
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

# -----------------------------
# 0. Конфігурація
# -----------------------------
MODEL_PATH = "model/best_rul_model.keras"
SCALER_PATH = "model/rul_scaler.pkl"
TEST_DATA_PATH = "model/rul_test_data.csv"
OUTPUT_PATH = "model/rul_predictions_output.csv"

REQUIRED_FEATURES = [
    "Air temperature [K]",
    "Process temperature [K]",
    "Rotational speed [rpm]",
    "Torque [Nm]",
    "Tool wear [min]"
]

TARGET_COLUMN = "RUL_synthetic"


# -----------------------------
# 1. Завантаження моделі
# -----------------------------
print("📌 Loading RUL model...")
model = load_model(MODEL_PATH)
print("✅ Model loaded!")


# -----------------------------
# 2. Завантаження scaler
# -----------------------------
print("📌 Loading scaler...")
scaler = joblib.load(SCALER_PATH)
print("✅ Scaler loaded!")


# -----------------------------
# 3. Завантаження CSV
# -----------------------------
df = pd.read_csv(TEST_DATA_PATH)
print(f"📌 Loaded test data: {df.shape}")

print("Columns in test data:", df.columns.tolist())


# -----------------------------
# 4. Валідація колонок
# -----------------------------
missing = [c for c in REQUIRED_FEATURES if c not in df.columns]
extra = [c for c in df.columns if c not in REQUIRED_FEATURES + [TARGET_COLUMN]]

if missing:
    raise ValueError(f"❌ Missing required features: {missing}")

if TARGET_COLUMN not in df.columns:
    raise ValueError("❌ Test file must contain RUL_synthetic column!")

if extra:
    print(f"⚠️ Extra columns will be ignored: {extra}")


# -----------------------------
# 5. Формування X і y
# -----------------------------
X = df[REQUIRED_FEATURES]
y_true = df[TARGET_COLUMN].values  # ✔️ target для оцінки моделі

# -----------------------------
# 6. Масштабування
# -----------------------------
X_scaled = scaler.transform(X)
print(f"📌 Scaled input shape: {X_scaled.shape}")

# -----------------------------
# 7. Прогноз
# -----------------------------
y_pred = model.predict(X_scaled).flatten()

# -----------------------------
# 8. Метрики
# -----------------------------
mae = mean_absolute_error(y_true, y_pred)
mse = mean_squared_error(y_true, y_pred)
r2 = r2_score(y_true, y_pred)

print("\n📊 MODEL PERFORMANCE:")
print(f"🔹 MAE = {mae:.4f}")
print(f"🔹 MSE = {mse:.4f}")
print(f"🔹 R²  = {r2:.4f}\n")

# -----------------------------
# 9. Перші 10 прогнозів
# -----------------------------
print("🔮 First 10 predictions (RUL):")
for i in range(10):
    print(f"{i+1:2d}. pred={y_pred[i]:8.2f}  | true={y_true[i]:8.2f}")

# -----------------------------
# 10. Збереження результатів
# -----------------------------
out_df = df.copy()
out_df["RUL_predicted"] = y_pred
out_df.to_csv(OUTPUT_PATH, index=False)

print(f"\n📁 Saved predictions → {OUTPUT_PATH}")
