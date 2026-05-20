from dataclasses import dataclass

from app.models.enums import NotificationChannel


@dataclass(frozen=True)
class NotificationMessage:
    channel: NotificationChannel
    title: str
    body: str | None = None


class NotificationService:
    def send(self, message: NotificationMessage) -> None:
        if message.channel == NotificationChannel.WECHAT_RESERVED:
            return
        return
