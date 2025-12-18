def determine_status(failure, pred):
    """
    Визначає загальний статус пристрою.
    Повертає: 'normal', 'risk', 'emergency'
    """
    # 1. Перевірка на аварію (найвищий пріоритет)
    # Важливо: перевіряємо, що це не "Normal"
    if failure and failure != "Normal":
        return "emergency"

    # 2. Перевірка на прогноз (попередження)
    if pred and pred.predicted_rul is not None:
        # Якщо RUL менше 50 годин
        if pred.predicted_rul < 50:
            return "risk"

    # 3. Якщо все добре
    return "normal"