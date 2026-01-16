
import socket
import dataclasses
from typing import Optional, Protocol, Callable
from app.config.settings import config

class SocketConnection(Protocol):
    """Protocol for socket-like connection that supports sendall and close."""

    def sendall(self, data: bytes) -> None:
        ...

    def close(self) -> None:
        ...


@dataclasses.dataclass
class ConnectionConfig:
    """Configuration for socket connections."""
    host: str
    port: int
    timeout: Optional[float] = None

    @classmethod
    def default(cls) -> 'ConnectionConfig':
        return cls(
            host=config.HOST_RECV_SERVER,
            port=config.PORT_RECV_SERVER,
        )


class ConnectionManager:
    """Manages socket connections with configurable parameters."""

    def __init__(self, config: ConnectionConfig):
        self.config = config

    def create_connection(self) -> SocketConnection:
        """Create a new socket connection."""
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if self.config.timeout:
            s.settimeout(self.config.timeout)
        s.connect((self.config.host, self.config.port))
        return s

    def create_factory(self) -> Callable[[], SocketConnection]:
        """Create a connection factory function."""
        return self.create_connection


ConnectionFactory = Callable[[], SocketConnection]


