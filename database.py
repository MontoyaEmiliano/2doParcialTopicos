from sqlmodel import SQLModel, create_engine, Session, select
from models import User, Zone

DATABASE_URL = "sqlite:///./parkilite.db"
engine = create_engine(DATABASE_URL, echo=True)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session

def seed_data():
    with Session(engine) as session:
        existing_user = session.exec(
            select(User).where(User.email == "demo@iberopuebla.mx")
        ).first()
        
        if not existing_user:
            demo_user = User(
                email="demo@iberopuebla.mx",
                api_key="testkey",
                balance=300.0
            )
            session.add(demo_user)
            print("Usuario demo creado")
        
        existing_zones = session.exec(select(Zone)).all()
        
        if not existing_zones:
            zone_a = Zone(name="A", rate_per_min=1.5, max_minutes=120)
            zone_b = Zone(name="B", rate_per_min=1.0, max_minutes=180)
            session.add(zone_a)
            session.add(zone_b)
            print("Zonas A y B creadas")
        
        session.commit()