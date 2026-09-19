from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class DestinationPort(Base):
    __tablename__ = "destination_ports"

    code: Mapped[str] = mapped_column(String(16), primary_key=True)
