import numpy as np

def fake_imencode(ext, img, params=None):
    fake_buffer = np.frombuffer(b"fake_jpeg_data", dtype=np.uint8)
    return True, fake_buffer