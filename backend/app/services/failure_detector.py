import random
import math

def detect_failure(r):
    rpm_rad = r.rotational_speed * 2 * math.pi / 60
    power = r.torque * rpm_rad
    # TWF
    if r.tool_wear >= 220:
        return "TWF"
    # HDF
    if (r.process_temp - r.air_temp) < 8.6 and r.rotational_speed < 1380:
        return "HDF"
    # PWF
    if power < 3500 or power > 9000:
        return "PWF"
    # OSF
    overload_limit = {
        "L": 11000,
        "M": 12000,
        "H": 13000
    }
    if r.torque * r.tool_wear > overload_limit.get(r.device.product_type, 11000):
        return "OSF"
    # RNF
    if random.random() < 0.001:
        return "RNF"

    return None


