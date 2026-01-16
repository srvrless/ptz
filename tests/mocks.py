class MockSocketConnection:
    def __init__(self):
        self.sent_data = []

    def sendall(self, data: bytes) -> None:
        self.sent_data.append(data) 

    def close(self) -> None:
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass
