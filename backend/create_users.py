from backend.app.database import SessionLocal
from backend.models import User
from backend.app.services.auth import get_password_hash

def create_user(username, password, role):
    db = SessionLocal()
    try:
        # Перевірка чи існує
        if db.query(User).filter(User.username == username).first():
            print(f"User {username} already exists")
            return

        new_user = User(
            username=username,
            hashed_password=get_password_hash(password),
            role=role
        )
        db.add(new_user)
        db.commit()
        print(f"User created: {username} ({role})")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    print("Creating initial users...")
    create_user("worker1", "pass123", "worker") # Оператор
    create_user("manager1", "pass123", "manager") # Інженер з технічного обслуговування
    create_user("analyst1", "pass123", "analyst") # Аналітик