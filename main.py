from fastapi import FastAPI, Depends, HTTPException, Header, status
from sqlmodel import Session, select
from typing import List
from datetime import datetime
from contextlib import asynccontextmanager
import math

from models import (
    User, Zone, Vehicle, ParkingSession,
    VehicleCreate, VehicleResponse, SessionStart, SessionStop,
    SessionResponse, WalletDeposit, ZoneResponse
)
from database import create_db_and_tables, get_session, seed_data

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicializa la base de datos y carga datos semilla al arrancar"""
    create_db_and_tables()
    seed_data()
    yield

app = FastAPI(
    title="ParkiLite API",
    version="1.0",
    description="Sistema de gestión de estacionamiento por zonas",
    lifespan=lifespan
)

# Este es el auth:)
def get_current_user(
    x_api_key: str = Header(..., alias="x-api-key"),
    session: Session = Depends(get_session)
) -> User:
    """Valida la API key y retorna el usuario autenticado"""
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key requerida"
        )
    
    user = session.exec(select(User).where(User.api_key == x_api_key)).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key inválida"
        )
    
    return user

#Empezamos los endopoints
@app.get("/", tags=["Root"])
def root():
    """Endpoint raíz con información de la API"""
    return {
        "message": "ParkiLite API",
        "version": "1.0",
        "docs": "/docs"
    }

@app.get("/zones", response_model=List[ZoneResponse], tags=["Zones"])
def get_zones(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Lista todas las zonas de estacionamiento disponibles"""
    zones = session.exec(select(Zone)).all()
    return zones


@app.post("/vehicles", response_model=VehicleResponse, status_code=status.HTTP_201_CREATED, tags=["Vehicles"])
def create_vehicle(
    vehicle_data: VehicleCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Crea un nuevo vehículo para el usuario autenticado"""
    existing = session.exec(
        select(Vehicle).where(
            Vehicle.user_id == current_user.id,
            Vehicle.plate == vehicle_data.plate
        )
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"El vehículo con placa {vehicle_data.plate} ya existe"
        )
    
    vehicle = Vehicle(
        user_id=current_user.id,
        plate=vehicle_data.plate
    )
    session.add(vehicle)
    session.commit()
    session.refresh(vehicle)
    return vehicle

@app.get("/vehicles", response_model=List[VehicleResponse], tags=["Vehicles"])
def get_vehicles(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Lista todos los vehículos del usuario autenticado"""
    vehicles = session.exec(
        select(Vehicle).where(Vehicle.user_id == current_user.id)
    ).all()
    return vehicles

@app.post("/sessions/start", response_model=SessionResponse, status_code=status.HTTP_201_CREATED, tags=["Sessions"])
def start_session(
    session_data: SessionStart,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Inicia una nueva sesión de estacionamiento"""
    vehicle = session.exec(
        select(Vehicle).where(
            Vehicle.user_id == current_user.id,
            Vehicle.plate == session_data.plate
        )
    ).first()
    
    if not vehicle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vehículo con placa {session_data.plate} no encontrado"
        )
    
    active_session = session.exec(
        select(ParkingSession).where(
            ParkingSession.vehicle_id == vehicle.id,
            ParkingSession.status == "active"
        )
    ).first()
    
    if active_session:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ya existe una sesión activa para el vehículo {session_data.plate}"
        )
    
    zone = session.get(Zone, session_data.zone_id)
    if not zone:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Zona {session_data.zone_id} no encontrada"
        )
    
    new_session = ParkingSession(
        user_id=current_user.id,
        vehicle_id=vehicle.id,
        zone_id=session_data.zone_id,
        started_at=datetime.now(),
        status="active"
    )
    session.add(new_session)
    session.commit()
    session.refresh(new_session)
    
    return SessionResponse(
        id=new_session.id,
        user_id=new_session.user_id,
        vehicle_id=new_session.vehicle_id,
        zone_id=new_session.zone_id,
        started_at=new_session.started_at,
        ended_at=new_session.ended_at,
        minutes=new_session.minutes,
        cost=new_session.cost,
        status=new_session.status
    )

@app.post("/sessions/stop", response_model=SessionResponse, tags=["Sessions"])
def stop_session(
    stop_data: SessionStop,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Detiene una sesión de estacionamiento y calcula el costo"""
    parking_session = session.get(ParkingSession, stop_data.session_id)
    
    if not parking_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sesión {stop_data.session_id} no encontrada"
        )
    
    if parking_session.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para detener esta sesión"
        )
    
    if parking_session.status != "active":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"La sesión ya fue finalizada con status: {parking_session.status}"
        )
    
#Funciones 
    ended_at = datetime.now()
    duration_seconds = (ended_at - parking_session.started_at).total_seconds()
    minutes = math.ceil(duration_seconds / 60)
    
    zone = session.get(Zone, parking_session.zone_id)
    cost = 0.0
    cost_total = 0.0
    final_status = "completed"
    
    if minutes <= 3:
        cost = 0.0
        cost_total = 0.0
    else:
        cost = minutes * zone.rate_per_min
        cost_total = cost
        
        if minutes > zone.max_minutes:
            final_status = "fined"
            cost_total = cost + 100.0
        elif current_user.balance < cost:
            final_status = "pending_payment"
        else:
            current_user.balance -= cost
    
    parking_session.ended_at = ended_at
    parking_session.minutes = minutes
    parking_session.cost = cost
    parking_session.status = final_status
    
    session.add(parking_session)
    session.add(current_user)
    session.commit()
    session.refresh(parking_session)
    session.refresh(current_user)
    
    return SessionResponse(
        id=parking_session.id,
        user_id=parking_session.user_id,
        vehicle_id=parking_session.vehicle_id,
        zone_id=parking_session.zone_id,
        started_at=parking_session.started_at,
        ended_at=parking_session.ended_at,
        minutes=parking_session.minutes,
        cost=parking_session.cost,
        status=parking_session.status,
        cost_total=cost_total if final_status == "fined" else None
    )

@app.get("/sessions/{session_id}", response_model=SessionResponse, tags=["Sessions"])
def get_session(
    session_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Obtiene los detalles de una sesión específica"""
    parking_session = session.get(ParkingSession, session_id)
    
    if not parking_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sesión {session_id} no encontrada"
        )
    
    if parking_session.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para ver esta sesión"
        )
    
    cost_total = None
    if parking_session.status == "fined" and parking_session.cost is not None:
        cost_total = parking_session.cost + 100.0
    
    return SessionResponse(
        id=parking_session.id,
        user_id=parking_session.user_id,
        vehicle_id=parking_session.vehicle_id,
        zone_id=parking_session.zone_id,
        started_at=parking_session.started_at,
        ended_at=parking_session.ended_at,
        minutes=parking_session.minutes,
        cost=parking_session.cost,
        status=parking_session.status,
        cost_total=cost_total
    )

@app.post("/wallet/deposit", tags=["Wallet"])
def deposit_to_wallet(
    deposit_data: WalletDeposit,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Deposita fondos en la billetera del usuario"""
    if deposit_data.amount <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El monto debe ser mayor a 0"
        )
    
    current_user.balance += deposit_data.amount
    session.add(current_user)
    session.commit()
    session.refresh(current_user)
    
    return {
        "message": "Depósito exitoso",
        "balance": current_user.balance
    }