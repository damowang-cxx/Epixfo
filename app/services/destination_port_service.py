from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import bad_request
from app.models.destination_port import DestinationPort


def normalize_destination(value: str | None) -> str:
    return (value or "").strip().upper()


def receipt_destination_ports(receipt) -> list[str]:
    override = getattr(receipt, "destination_ports_override", None)
    values = override if override is not None else getattr(receipt, "channel_tags", None)
    return list(dict.fromkeys(normalize_destination(value) for value in (values or []) if normalize_destination(value)))


class DestinationPortService:
    def __init__(self, db: Session):
        self.db = db

    def list(self) -> list[DestinationPort]:
        return list(self.db.scalars(select(DestinationPort).order_by(DestinationPort.code)))

    def require(self, value: str | None) -> str:
        code = normalize_destination(value)
        if not code:
            raise bad_request("目的港为必填信息")
        if self.db.get(DestinationPort, code) is None:
            raise bad_request(f"目的港 {code} 尚未配置，请先在航司配置中添加")
        return code

    def create(self, code: str) -> DestinationPort:
        item = DestinationPort(code=code)
        self.db.add(item)
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise bad_request("目的港已存在") from None
        return item
