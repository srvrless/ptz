import numpy as np


class MockCamera:
    """Mock для cv2.VideoCapture."""

    def __init__(self, url: str, frame_shape=(480, 640, 3)):
        self.url = url
        self.frame_shape = frame_shape
        self.frame_counter = 0
        self.is_opened_flag = True
        self.frames = [
            np.random.randint(0, 255, frame_shape, dtype=np.uint8) for _ in range(10)
        ]

    def isOpened(self) -> bool:
        return self.is_opened_flag

    def read(self):
        if not self.is_opened_flag:
            return False, None

        frame = self.frames[self.frame_counter % len(self.frames)]
        self.frame_counter += 1
        return True, frame.copy()

    def release(self):
        self.is_opened_flag = False

    def get(self, prop_id):
        if prop_id == 3:  # CV_CAP_PROP_FRAME_WIDTH
            return self.frame_shape[1]
        elif prop_id == 4:  # CV_CAP_PROP_FRAME_HEIGHT
            return self.frame_shape[0]
        elif prop_id == 5:  # CV_CAP_PROP_FPS
            return 30.0
        return None


class MockSocket:
    """Mock для socket connection."""

    def __init__(self):
        self.sent_data = []
        self.closed = False

    def sendall(self, data: bytes) -> None:
        if self.closed:
            raise ConnectionResetError("Socket is closed")
        self.sent_data.append(data)

    def close(self) -> None:
        self.closed = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
