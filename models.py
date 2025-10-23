from sqlmodel import Field, SQLModel, Relationship
from typing import Optional, List
from datetime import datetime

class User(SQLModel, table=True):
    __tablename__ = "users"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)
    api_key: str = Field(unique=True, index=True)
    balance: float = Field(default=0.0)
    
    vehicles: List["Vehicle"] = Relationship(back_populates="user")
    sessions: List["ParkingSession"] = Relationship(back_populates="user")


class Zone(SQLModel, table=True):
    __tablename__ = "zones"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True)
    rate_per_min: float
    max_minutes: int
    
    sessions: List["ParkingSession"] = Relationship(back_populates="zone")


class Vehicle(SQLModel, table=True):
    __tablename__ = "vehicles"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id")
    plate: str = Field(index=True)
    
    user: Optional[User] = Relationship(back_populates="vehicles")
    sessions: List["ParkingSession"] = Relationship(back_populates="vehicle")


class ParkingSession(SQLModel, table=True):
    __tablename__ = "parking_sessions"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id")
    vehicle_id: int = Field(foreign_key="vehicles.id")
    zone_id: int = Field(foreign_key="zones.id")
    started_at: datetime
    ended_at: Optional[datetime] = None
    minutes: Optional[int] = None
    cost: Optional[float] = None
    status: str = Field(default="active")
    
    user: Optional[User] = Relationship(back_populates="sessions")
    vehicle: Optional[Vehicle] = Relationship(back_populates="sessions")
    zone: Optional[Zone] = Relationship(back_populates="sessions")


class VehicleCreate(SQLModel):
    plate: str


class VehicleResponse(SQLModel):
    id: int
    plate: str
    user_id: int


class SessionStart(SQLModel):
    plate: str
    zone_id: int


class SessionStop(SQLModel):
    session_id: int


class SessionResponse(SQLModel):
    id: int
    user_id: int
    vehicle_id: int
    zone_id: int
    started_at: datetime
    ended_at: Optional[datetime]
    minutes: Optional[int]
    cost: Optional[float]
    status: str
    cost_total: Optional[float] = None


class WalletDeposit(SQLModel):
    amount: float


class ZoneResponse(SQLModel):
    id: int
    name: str
    rate_per_min: float
    max_minutes: int