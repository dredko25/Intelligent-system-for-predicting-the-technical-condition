import json
import random
import time
import threading
import argparse
from datetime import datetime, timezone
import numpy as np
import sys
import signal
import paho.mqtt.client as mqtt
from typing import Dict, Tuple, Optional

# -----------------------------
# Конфігураційні параметри симуляції
# -----------------------------
TWF_MIN = 200
TWF_MAX = 240
HDF_TEMP_DIFF = 8.6
HDF_RPM_THRESHOLD = 1380
PWF_POWER_MIN = 3500
PWF_POWER_MAX = 9000

OSF_THRESHOLDS = {
    "L": 11000,
    "M": 12000,
    "H": 13000
}

RNF_PROB = 0.001

WEAR_VARIANTS = {
    "L": 0.2,  # Повільний знос для низької якості
    "M": 0.3,  # Середній знос для середньої якості
    "H": 0.5   # Швидкий знос для високої якості
}

PRODUCT_VARIANTS = {
    "L": {"prob": 0.50},
    "M": {"prob": 0.30},
    "H": {"prob": 0.20},
}

# Знос інструменту множник
WEAR_MULTIPLIER = 1.0

# -----------------------------
# Симулятор промислових датчиків
# -----------------------------

class IndustrialSensorSimulator:
    
    def __init__(self, seed: int = None):
        self.seed = seed or random.randint(1, 10000)
        np.random.seed(self.seed)
        
        # Базові параметри
        self.base_air_temp = 300.0
        self.base_process_temp = 310.0
        self.base_rotational_speed = 1500.0
        self.base_torque = 40.0
        
        # Шум вимірювань
        self.air_temp_std = 2.0
        self.process_temp_std = 1.0
        self.speed_std = 50.0
        self.torque_std = 5.0
        
        # Стан симуляції
        self.current_tool_wear = 0.0
        self.cycle_count = 0
        
    def _add_measurement_noise(self, value: float, std: float) -> float:
        # Додає реалістичний вимірювальний шум
        return value + np.random.normal(0, std)
    
    def _random_walk(self, current_value: float, std: float, bounds: Tuple[float, float]) -> float:
        # Random walk з обмеженнями для реалістичних дрейфів
        change = np.random.normal(0, std * 0.3)  # Менш агресивні зміни
        new_value = current_value + change
        return np.clip(new_value, bounds[0], bounds[1])
    
    def generate_normal_operation(self, n_samples: int = 100) -> tuple:
        # Генерація нормальної роботи з реалістичними коливаннями
        air_temp = self.base_air_temp
        process_temp = self.base_process_temp
        
        air_data, process_data, speed_data, torque_data, wear_data = [], [], [], [], []
        
        for i in range(n_samples):
            # Random walk для температур
            air_temp = self._random_walk(air_temp, self.air_temp_std, (295, 305))
            process_temp = air_temp + 10 + self._add_measurement_noise(0, self.process_temp_std)
            
            # Швидкість з коливаннями
            speed = self._add_measurement_noise(self.base_rotational_speed, self.speed_std)
            speed = np.clip(speed, 1200, 2800)
            
            # Крутний момент
            torque = self._add_measurement_noise(self.base_torque, self.torque_std)
            torque = np.clip(torque, 10, 70)
            
            # Поступовий знос
            self.current_tool_wear += 0.1 + np.random.normal(0, 0.02)
            wear = max(0, self.current_tool_wear)
            
            air_data.append(air_temp)
            process_data.append(process_temp)
            speed_data.append(speed)
            torque_data.append(torque)
            wear_data.append(wear)
        
        return (
            np.array(air_data),
            np.array(process_data), 
            np.array(speed_data),
            np.array(torque_data),
            np.array(wear_data)
        )
    
    def generate_tool_wear_failure(self, n_samples: int = 100, accelerated_wear: float = 3.0) -> tuple:
        # Сценарій прискореного зносу інструменту
        air_temp = self.base_air_temp
        process_temp = self.base_process_temp
        tool_wear = 0.0
        
        air_data, process_data, speed_data, torque_data, wear_data = [], [], [], [], []
        
        for i in range(n_samples):
            air_temp = self._random_walk(air_temp, self.air_temp_std, (295, 305))
            process_temp = air_temp + 10 + self._add_measurement_noise(0, self.process_temp_std)
            
            # Підвищені параметри для прискореного зносу
            speed = self._add_measurement_noise(self.base_rotational_speed * 1.2, self.speed_std * 1.5)
            speed = np.clip(speed, 1500, 2800)
            
            torque = self._add_measurement_noise(self.base_torque * 1.3, self.torque_std * 1.2)
            torque = np.clip(torque, 20, 70)
            
            # Прискорений знос
            wear_increment = 0.1 * accelerated_wear + np.random.normal(0, 0.05)
            tool_wear += wear_increment
            
            air_data.append(air_temp)
            process_data.append(process_temp)
            speed_data.append(speed)
            torque_data.append(torque)
            wear_data.append(tool_wear)
            
            if tool_wear >= 200:  # Ранній поріг для демонстрації
                break
        
        # Доповнюємо до n_samples якщо потрібно
        while len(air_data) < n_samples:
            air_data.append(air_data[-1])
            process_data.append(process_data[-1])
            speed_data.append(speed_data[-1])
            torque_data.append(torque_data[-1])
            wear_data.append(wear_data[-1])
        
        return (
            np.array(air_data),
            np.array(process_data),
            np.array(speed_data),
            np.array(torque_data),
            np.array(wear_data)
        )
    
    def generate_heat_dissipation_failure(self, n_samples: int = 100) -> tuple:
        # Сценарій проблеми з охолодженням
        air_temp = self.base_air_temp
        cooling_efficiency = 1.0
        cooling_degradation = 0.01
        
        air_data, process_data, speed_data, torque_data, wear_data = [], [], [], [], []
        
        for i in range(n_samples):
            air_temp = self._random_walk(air_temp, self.air_temp_std, (298, 308))
            
            # Погіршення охолодження
            cooling_efficiency = max(0.3, cooling_efficiency - cooling_degradation)
            
            # Низька швидкість охолодження
            speed = self._add_measurement_noise(1250, self.speed_std * 0.8)
            speed = np.clip(speed, 1100, 1379)
            
            # Температура процесу знижується через погане охолодження
            temp_delta = 10.0 * cooling_efficiency + np.random.normal(0, 0.5)
            process_temp = air_temp + temp_delta
            
            torque = self._add_measurement_noise(self.base_torque, self.torque_std)
            torque = np.clip(torque, 10, 70)
            
            tool_wear = i * 0.1 + np.random.normal(0, 0.5)
            
            air_data.append(air_temp)
            process_data.append(process_temp)
            speed_data.append(speed)
            torque_data.append(torque)
            wear_data.append(tool_wear)
        
        return (
            np.array(air_data),
            np.array(process_data),
            np.array(speed_data),
            np.array(torque_data),
            np.array(wear_data)
        )
    
    def generate_power_failure(self, n_samples: int = 100) -> tuple:
        # Сценарій проблеми з живленням
        air_temp = self.base_air_temp
        voltage_stability = 1.0
        
        air_data, process_data, speed_data, torque_data, wear_data = [], [], [], [], []
        
        mode = random.choice(["low", "high"])
        
        for i in range(n_samples):
            air_temp = self._random_walk(air_temp, self.air_temp_std, (295, 305))
            
            # Гарантуємо, що різниця температур > 9.0,
            # щоб випадково не спрацював HDF (який вимагає різницю < 8.6),
            # оскільки в цьому сценарії оберти можуть падати низько.
            temp_diff = 10.0 + abs(np.random.normal(0, 0.5)) 
            process_temp = air_temp + temp_diff
            
            # Нестабільність живлення
            voltage_stability = max(0.6, voltage_stability - 0.005 + np.random.normal(0, 0.03))
            
            if mode == "low":
                # Низька потужність (< 3500 W)
                # Знижуємо швидкість і момент
                speed = self._add_measurement_noise(1100 * voltage_stability, self.speed_std)
                torque = self._add_measurement_noise(20 * voltage_stability, self.torque_std)
            else:
                # Висока потужність (> 9000 W)
                speed = self._add_measurement_noise(2900, self.speed_std) 
                # Щоб отримати > 9000W при 2900rpm, треба момент > 30Nm
                torque = self._add_measurement_noise(65, self.torque_std) 
            
            # Фізичні обмеження
            speed = np.clip(speed, 1000, 3500)
            torque = np.clip(torque, 5, 85)
            
            # Малий знос, щоб не викликати TWF
            tool_wear = i * 0.05 
            
            air_data.append(air_temp)
            process_data.append(process_temp)
            speed_data.append(speed)
            torque_data.append(torque)
            wear_data.append(tool_wear)
        
        return (
            np.array(air_data),
            np.array(process_data),
            np.array(speed_data),
            np.array(torque_data),
            np.array(wear_data)
        )
    
    def reset(self):
        # Скидання стану симулятора
        self.current_tool_wear = 0.0
        self.cycle_count = 0

# -----------------------------
# Стан обладнання та керування сценаріями
# -----------------------------

class EquipmentState:
    def __init__(self, device_uid, scenario_type=None):
        self.device_uid = device_uid
        self.lock = threading.Lock()
        self.simulator = IndustrialSensorSimulator()
        self.reset(scenario_type or random.choice(list(scenario_funcs.keys())))
        
    def reset(self, new_scenario=None):
        # Повне скидання стану (викликається при зміні сценарію)
        with self.lock:
            if new_scenario:
                self.current_scenario = new_scenario
            self.is_failed = False
            self.failure_type = None
            self.failure_time = None
            self.accumulated_wear = 0.0
            self.product_variant = choose_product_variant()
            self.twf_limit = random.randint(TWF_MIN, TWF_MAX)
            self.simulator.reset()
            print(f"[{self.device_uid}] RESET: Scenario='{self.current_scenario}', Variant={self.product_variant}, TWF Limit={self.twf_limit}")

def choose_product_variant():
    r = random.random()
    cumulative = 0
    for variant, data in PRODUCT_VARIANTS.items():
        cumulative += data["prob"]
        if r <= cumulative: 
            return variant
    return "L"

# -----------------------------
# функції сценаріїв
# -----------------------------

def scenario_normal(length):
    """
    Генерація нормальних даних, які гарантовано залишаються в межах норми
    """
    simulator = IndustrialSensorSimulator()
    air, process, speed, torque, wear = simulator.generate_normal_operation(length)
    
    # Корекція для уникнення випадкових помилок (PWF, OSF) у нормальному режимі
    # Потужність має бути від 3500 до 9000
    power = torque * speed * (2 * np.pi / 60)
    
    # Якщо потужність вийшла за межі, коригуємо крутний момент
    mask_low = power < 3550  # Запас 50 Вт
    mask_high = power > 8950 # Запас 50 Вт
    
    # Коригуємо torque, щоб повернути потужність в норму
    torque[mask_low] = 3600 / (speed[mask_low] * (2 * np.pi / 60))
    torque[mask_high] = 8900 / (speed[mask_high] * (2 * np.pi / 60))
    
    # Перевірка на HDF (Temp diff >= 8.6 або Speed >= 1380)
    temp_diff = process - air
    mask_hdf = (temp_diff < 8.7) & (speed < 1390)
    # Якщо випадково випали умови HDF, піднімаємо різницю температур
    process[mask_hdf] = air[mask_hdf] + 9.0

    return air, process, speed, torque, wear

def scenario_twf(length):
    """
    Tool Wear Failure: Знос досягає критичної межі (200-240).
    """
    simulator = IndustrialSensorSimulator()
    # Прискорюємо знос у 5 разів, щоб гарантовано дійти до відмови за короткий час
    return simulator.generate_tool_wear_failure(length, accelerated_wear=5.0)

def scenario_hdf(length):
    """
    Heat Dissipation Failure:
    Різниця температур < 8.6 K І швидкість < 1380 rpm.
    """
    simulator = IndustrialSensorSimulator()
    air, process, speed, torque, wear = simulator.generate_normal_operation(length)
    
    # Створюємо умови для HDF в другій половині сценарію
    failure_idx = int(length * 0.7)
    
    # Знижуємо швидкість обертання нижче порогу 1380
    speed[failure_idx:] = np.random.uniform(1100, 1350, length - failure_idx)
    
    # Зменшуємо різницю температур
    # Робимо різницю маленькою, наприклад 5-8 градусів
    process[failure_idx:] = air[failure_idx:] + np.random.uniform(2.0, 8.0, length - failure_idx)
    
    return air, process, speed, torque, wear

def scenario_pwf(length):
    """
    Power Failure: Power < 3500 або > 9000 Вт.
    """
    simulator = IndustrialSensorSimulator()
    air, process, speed, torque, wear = simulator.generate_normal_operation(length)
    
    failure_idx = int(length * 0.8)
    
    # Вирішуємо, який тип збою живлення (низька або висока потужність)
    if random.random() > 0.5:
        # Overpower (> 9000 W)
        # Піднімаємо момент і швидкість
        target_power = np.random.uniform(9100, 10000, length - failure_idx)
        speed[failure_idx:] = np.random.uniform(2800, 3000, length - failure_idx) # Висока швидкість
        # Torque = Power / (Speed * factor)
        factor = 2 * np.pi / 60
        torque[failure_idx:] = target_power / (speed[failure_idx:] * factor)
    else:
        # Underpower (< 3500 W)
        target_power = np.random.uniform(2000, 3400, length - failure_idx)
        speed[failure_idx:] = np.random.uniform(1200, 1300, length - failure_idx) # Низька швидкість
        factor = 2 * np.pi / 60
        torque[failure_idx:] = target_power / (speed[failure_idx:] * factor)

    return air, process, speed, torque, wear

def scenario_osf(length):
    """
    Overstrain Failure: Tool Wear * Torque > Threshold (мін 11000).
    """
    simulator = IndustrialSensorSimulator()
    air, process, speed, torque, wear = simulator.generate_normal_operation(length)
    
    failure_idx = int(length * 0.6)
    
    # Для OSF нам потрібен значний знос та високий крутний момент.
    # Штучно збільшуємо знос у другій половині
    wear[failure_idx:] = np.linspace(wear[failure_idx], 200, length - failure_idx)
    
    # Розраховуємо необхідний момент для поломки
    # Беремо поріг для продукту L (найменший = 11000), щоб гарантувати спрацювання
    threshold = 11000
    
    # Створюємо пік крутного моменту, який гарантує (Wear * Torque > 11000)
    # Torque = (Threshold / Wear) + запас
    required_torque = (threshold / wear[failure_idx:]) + 5.0
    
    # Обмежуємо макс. момент реалістичними значеннями (наприклад, до 70-80 Nm)
    torque[failure_idx:] = np.clip(required_torque, 0, 80)
    
    # Додаємо трохи шуму
    torque[failure_idx:] += np.random.normal(0, 1.0, length - failure_idx)

    return air, process, speed, torque, wear

def scenario_rnf(length):
    simulator = IndustrialSensorSimulator()
    # RNF - це випадкова помилка, параметри можуть бути нормальними,
    # але прапорець failure ставиться випадково в детекторі.
    # Тому генеруємо нормальні дані.
    return simulator.generate_normal_operation(length)

def scenario_worn_stress(length):
    """
    Сценарій "Старе обладнання під навантаженням"
    """
    simulator = IndustrialSensorSimulator()
    air, process, speed, torque, wear = simulator.generate_normal_operation(length)
    
    # 1. Знос: 150-180 хв
    base_wear = np.random.uniform(150, 180)
    wear[:] = np.linspace(base_wear, base_wear + 2, length)
    
    # 2. Крутний момент:
    # Максимально допустимий для PWF при 1500 rpm: ~55 Nm (55 * 1500 * 0.105 = 8660 < 9000)
    # Максимально допустимий для OSF при 180 wear: ~60 Nm (11000 / 180 = 61)
    # ТОМУ: ставимо середнє 48, обрізаємо на 53.
    torque[:] = np.random.normal(48, 2, length)
    torque = np.clip(torque, 42, 53)
    
    # 3. Швидкість: трохи нижча за середню, щоб зменшити ротужність
    speed[:] = np.random.normal(1450, 15, length)

    return air, process, speed, torque, wear

scenario_funcs = {
    "normal": scenario_normal,
    "twf": scenario_twf,
    "hdf": scenario_hdf,
    "pwf": scenario_pwf,
    "osf": scenario_osf,
    "rnf": scenario_rnf,
    "worn_stress": scenario_worn_stress
}

# -----------------------------
# Детектор відмов
# -----------------------------

def detect_failure(air, process, speed, torque, wear, product_variant, twf_limit, current_scenario="normal"):
    
    rpm_rad = speed * 2 * np.pi / 60
    power = torque * rpm_rad
    temp_diff = process - air
    osf_threshold = OSF_THRESHOLDS.get(product_variant, 11000)

    # 1. TWF
    if wear >= twf_limit:
        return "TWF"
    
    # 2. OSF
    if (wear * torque) > osf_threshold:
        return "OSF"
    
    # 3. HDF
    if temp_diff < HDF_TEMP_DIFF and speed < HDF_RPM_THRESHOLD:
        return "HDF"
    
    # 4. PWF
    if power < PWF_POWER_MIN or power > PWF_POWER_MAX:
        return "PWF"
    
    # 5. RNF (Випадкова відмова)
    # Дозволяємо RNF тільки якщо це "normal" або явно "rnf" сценарій.
    # В інших сценаріях (osf, pwf, hdf, twf) ми хочемо бачити цільову помилку, а не випадкову.
    if current_scenario in ["normal", "rnf"]:
        if random.random() < RNF_PROB:
            return "RNF"
    
    return "Normal"

def apply_post_failure_behavior(air, process, speed, torque, wear, failure_type, time_after_failure):
    # Реалістична поведінка після поломки
    decay = min(1.0, time_after_failure / 20.0)
    
    if failure_type == "TWF":
        new_speed = max(0, speed * (1 - decay * 0.8))
        new_torque = max(0, torque * (1 - decay * 0.9))
    elif failure_type == "HDF":
        new_speed = max(0, speed * (1 - decay))
        new_torque = max(0, torque * (1 - decay * 0.7))
    elif failure_type == "PWF":
        new_speed = max(0, speed * (1 - decay * 0.6))
        new_torque = max(0, torque * (1 - decay * 0.8))
    else:  # OSF, RNF
        new_speed = max(0, speed * (1 - decay * 0.9))
        new_torque = max(0, torque * (1 - decay * 0.9))
    
    # Температури також змінюються
    new_process = process - min(20, time_after_failure * 0.8)
    new_air = air - min(10, time_after_failure * 0.3)
    
    return (
        max(295, new_air),
        max(new_air + 5, new_process),
        max(0, new_speed),
        max(0, new_torque)
    )

# -----------------------------
# Публікація даних пристрою
# -----------------------------

class DevicePublisher(threading.Thread):
    def __init__(self, device_uid, interval, mqtt_client=None, mqtt_topic_prefix="sensors"):
        super().__init__(daemon=True)
        self.device_uid = device_uid
        self.interval = interval
        self.mqtt_client = mqtt_client
        self.mqtt_topic = f"{mqtt_topic_prefix}/{device_uid}"
        self.stop_event = threading.Event()
        self.state = EquipmentState(device_uid)
        
        self.data_length = 2000  # Менше для більшої варіативності
        self.regenerate_scenario_data()
        self.current_index = 0

    def regenerate_scenario_data(self):
        # Генерація нових даних сценарію
        scenario_func = scenario_funcs[self.state.current_scenario]
        self.air, self.process, self.speed, self.torque, self.wear = scenario_func(self.data_length)
        self.current_index = 0
        print(f"[{self.device_uid}] Regenerated data for scenario: {self.state.current_scenario}")

    def generate_sensor_data(self):
        # Генерація даних датчиків
        with self.state.lock:
            
            # Накопичення зносу (тільки якщо обладнання працює)
            if not self.state.is_failed:
                wear_rate = WEAR_VARIANTS[self.state.product_variant] * WEAR_MULTIPLIER
                self.state.accumulated_wear += wear_rate

            # Отримання базових даних
            idx = self.current_index % self.data_length
            base_air = float(self.air[idx])
            base_process = float(self.process[idx])
            base_speed = float(self.speed[idx])
            base_torque = float(self.torque[idx])
            base_wear = float(self.wear[idx])
            
            # Комбінування базових даних з поточним станом
            current_wear = self.state.accumulated_wear + base_wear * 0.3
            
            # Додавання реального шуму
            air = base_air + random.gauss(0, 0.5)
            process = base_process + random.gauss(0, 0.3)
            speed = base_speed + random.gauss(0, 10)
            torque = base_torque + random.gauss(0, 1)
            
            # Обробка поломок
            if self.state.is_failed:
                time_after_failure = time.time() - self.state.failure_time
                air, process, speed, torque = apply_post_failure_behavior(
                    air, process, speed, torque, current_wear, 
                    self.state.failure_type, time_after_failure
                )
            else:
                # Перевірка на нову поломку
                failure = detect_failure(
                    air, process, speed, torque, current_wear,
                    self.state.product_variant, self.state.twf_limit
                )
                
                if failure != "Normal":
                    self.state.is_failed = True
                    self.state.failure_type = failure
                    self.state.failure_time = time.time()
                    print(f"[{self.device_uid}] FAILURE DETECTED: {failure}")
                    print(f"    Parameters: Air={air:.1f}K, Process={process:.1f}K, "
                          f"Speed={speed:.0f}rpm, Torque={torque:.1f}Nm, Wear={current_wear:.1f}")

            # Розрахунок потужності
            power = torque * speed * (2 * np.pi / 60)
            
            # Формування даних
            return {
                "device_uid": self.device_uid,
                "product_type": self.state.product_variant,
                "air_temp": round(air, 2),
                "process_temp": round(process, 2),
                "rotational_speed": round(speed, 0),
                "torque": round(torque, 2),
                "tool_wear": round(current_wear, 1),
                "power": round(power, 0),
                "failure_type": self.state.failure_type if self.state.is_failed else "Normal",
                "scenario": self.state.current_scenario,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "is_failed": self.state.is_failed,
                "time_elapsed": round(current_wear, 1)
            }

    def run(self):
        # Основний цикл публікації даних
        while not self.stop_event.is_set():
            data = self.generate_sensor_data()
            if data:
                json_data = json.dumps(data)
                if self.mqtt_client:
                    try:
                        self.mqtt_client.publish(self.mqtt_topic, json_data, qos=1)
                    except Exception as e:
                        print(f"[{self.device_uid}] MQTT publish error: {e}")
                else:
                    print(f"{self.device_uid}: {json_data}")
            
            self.current_index += 1
            if self.stop_event.wait(timeout=self.interval):
                break

    def stop(self):
        # Зупинка publisher
        self.stop_event.set()

    def handle_control_command(self, command):
        # Обробка команд керування з покращеною логікою
        action = command.get("action")
        scenario = command.get("scenario", "normal")
        
        if action == "repair":
            self.state.reset(scenario)
            self.regenerate_scenario_data()
            return {"status": "success", "message": f"Повний ремонт виконано. Сценарій: {scenario}"}
        
        elif action == "repair_partial":
            self.state.repair_partial()
            return {"status": "success", "message": "Частковий ремонт виконано"}
        
        elif action == "change_scenario":
            if scenario not in scenario_funcs:
                return {"status": "error", "message": f"Невідомий сценарій: {scenario}"}
            
            # Повне скидання при зміні сценарію.
            # Це гарантує, що старий знос не викличе TWF, коли ми хочемо тестувати HDF/PWF.
            self.state.reset(scenario)
            self.regenerate_scenario_data()
            
            return {"status": "success", "message": f"Сценарій встановлено: {scenario} (стан скинуто)"}
        
        else:
            return {"status": "error", "message": f"Невідома команда: {action}"}

# -----------------------------
# Головна функція
# -----------------------------

def main():
    parser = argparse.ArgumentParser(description="Enhanced Industrial Equipment Simulator")
    parser.add_argument("--num-devices", type=int, default=1, help="Кількість пристроїв")
    parser.add_argument("--interval", type=float, default=2.0, help="Інтервал публікації (секунди)")
    parser.add_argument("--wear-rate", type=float, default=1.0, help="Множник швидкості зносу")
    parser.add_argument("--mqtt", action="store_true", help="Використовувати MQTT")
    parser.add_argument("--mqtt-host", type=str, default="localhost", help="MQTT брокер")
    parser.add_argument("--mqtt-port", type=int, default=1883, help="MQTT порт")
    parser.add_argument("--mqtt-topic-prefix", type=str, default="sensors", help="Префікс MQTT топіку")
    
    args = parser.parse_args()
    global WEAR_MULTIPLIER
    WEAR_MULTIPLIER = args.wear_rate

    print(f"Інтелектуальна система прогнозування технічного стану обладнання")
    print(f"Пристроїв: {args.num_devices}, Інтервал: {args.interval}с")
    print(f"Множник зносу: {WEAR_MULTIPLIER}x")
    print(f"MQTT: {'Так' if args.mqtt else 'Ні'}")
    if args.mqtt:
        print(f"MQTT Broker: {args.mqtt_host}:{args.mqtt_port}")

    # Налаштування MQTT
    mqtt_client = None
    devices = {}

    if args.mqtt:
        try:
            client_id = f"sim-{random.randint(1000, 9999)}"
            mqtt_client = mqtt.Client(client_id=client_id)
            
            def on_message(client, userdata, msg):
                try:
                    target_device = msg.topic.split('/')[-1]
                    payload = json.loads(msg.payload.decode())
                    if target_device in devices:
                        result = devices[target_device].handle_control_command(payload)
                        print(f"[{target_device}] Command: {payload.get('action')} -> {result['status']}")
                except Exception as e:
                    print(f"MQTT msg error: {e}")

            mqtt_client.on_message = on_message
            mqtt_client.connect(args.mqtt_host, args.mqtt_port, 60)
            mqtt_client.subscribe("commands/+")
            mqtt_client.loop_start()
            print(f"Connected to MQTT Broker at {args.mqtt_host}:{args.mqtt_port}")
            
        except Exception as e:
            print(f"MQTT connection failed: {e}")
            sys.exit(1)

    publishers = []
    for i in range(1, args.num_devices + 1):
        device_uid = f"dev-{i}"
        publisher = DevicePublisher(device_uid, args.interval, mqtt_client, args.mqtt_topic_prefix)
        devices[device_uid] = publisher
        publishers.append(publisher)
        publisher.start()

    def shutdown(signum=None, frame=None):
        print(f"\nЗавершення роботи симулятора...")
        for pub in publishers: pub.stop()
        if mqtt_client: mqtt_client.loop_stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    print("Симулятор запущено... Натисніть Ctrl+C, щоб зупинити.")
    
    try:
        while True: time.sleep(1)
    except KeyboardInterrupt:
        shutdown()

if __name__ == "__main__":
    main()