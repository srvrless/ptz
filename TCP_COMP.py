import socket
import time


class Tms20TCP:
    """
    Управление системой по протоколу TMS-20 через TCP.

    PT Drive:  адрес по умолчанию 0x04
    EO Camera: адрес по умолчанию 0x01

    Формат пакета:
        Byte0: 0xFF
        Byte1: address
        Byte2: Cmd1 (MSB)
        Byte3: Cmd2 (LSB)
        Byte4: Data1
        Byte5: Data2
        Byte6: Sum = (address + Cmd1 + Cmd2 + Data1 + Data2) & 0xFF
    """

    def __init__(
        self,
        ip: str,
        port: int = 1470,
        pt_addr: int = 0x04,
        cam_addr: int = 0x01,
        ir_addr: int = 0x02,
        timeout: float = 2.0,
    ):
        self.ip = ip
        self.port = port
        self.pt_addr = pt_addr
        self.cam_addr = cam_addr
        self.ir_addr = ir_addr  # Адрес тепловизора (IR Cam)

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(timeout)
        self.sock.connect((self.ip, self.port))

    # ---------------- внутренние утилиты ----------------

    @staticmethod
    def _checksum(address: int, cmd1: int, cmd2: int, data1: int, data2: int) -> int:
        return (address + cmd1 + cmd2 + data1 + data2) & 0xFF

    def _send_to(self, address: int, cmd: int, data1: int, data2: int):
        """
        cmd – 16-битное значение (как в доке: 0x0002 Right, 0x004B Pan Direct, ...).
        """
        cmd1 = (cmd >> 8) & 0xFF  # MSB
        cmd2 = cmd & 0xFF  # LSB
        data1 &= 0xFF
        data2 &= 0xFF

        chksum = self._checksum(address, cmd1, cmd2, data1, data2)

        packet = bytes([0xFF, address & 0xFF, cmd1, cmd2, data1, data2, chksum])
        self.sock.sendall(packet)

    def _send_pt(self, cmd: int, data1: int, data2: int):
        self._send_to(self.pt_addr, cmd, data1, data2)

    def _send_cam(self, cmd: int, data1: int, data2: int):
        self._send_to(self.cam_addr, cmd, data1, data2)

    def _send_ir(self, cmd: int, data1: int, data2: int):
        """Отправить команду на IR камеру (тепловизор)."""
        self._send_to(self.ir_addr, cmd, data1, data2)

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass

    # ---------------- Питание ----------------

    def power_on_pt(self):
        """
        Power On (0x8800) для PT Drive.
        """
        cmd = 0x8800
        self._send_pt(cmd, 0x00, 0x00)

    def power_on_cam(self):
        """
        Power On (0x8800) для EO камеры (адрес cam_addr).
        """
        cmd = 0x8800
        self._send_cam(cmd, 0x00, 0x00)

    # ---------------- Тепловизор (IR Cam) ----------------

    def power_on_ir(self):
        """
        Power On (0x8800) для IR камеры (тепловизор).
        Включает тепловизор, не влияя на EO камеру.
        """
        cmd = 0x8800
        self._send_ir(cmd, 0x00, 0x00)

    def power_off_ir(self):
        """
        Power Off (0x0800) для IR камеры (тепловизор).
        Выключает тепловизор, не влияя на EO камеру.
        """
        cmd = 0x0800
        self._send_ir(cmd, 0x00, 0x00)

    # ---------------- PT: ручное управление ----------------

    def stop(self):
        """Остановить PT по всем осям."""
        self._send_pt(0x0000, 0x00, 0x00)

    def move_right(self, speed: int = 32):
        """Поворот вправо. Right = 0x0002."""
        speed = max(0, min(63, speed))
        self._send_pt(0x0002, speed, 0x00)

    def move_left(self, speed: int = 32):
        """Поворот влево. Left = 0x0004."""
        speed = max(0, min(63, speed))
        self._send_pt(0x0004, speed, 0x00)

    def move_up(self, speed: int = 32):
        """Наклон вверх. Up = 0x0008."""
        speed = max(0, min(63, speed))
        self._send_pt(0x0008, 0x00, speed)

    def move_down(self, speed: int = 32):
        """Наклон вниз. Down = 0x0010."""
        speed = max(0, min(63, speed))
        self._send_pt(0x0010, 0x00, speed)

    def move_up_right(self, pan_speed: int = 32, tilt_speed: int = 32):
        """Вверх + вправо. Up + Right = 0x000A."""
        pan_speed = max(0, min(63, pan_speed))
        tilt_speed = max(0, min(63, tilt_speed))
        self._send_pt(0x000A, pan_speed, tilt_speed)

    def move_up_left(self, pan_speed: int = 32, tilt_speed: int = 32):
        """Вверх + влево. Up + Left = 0x000C."""
        pan_speed = max(0, min(63, pan_speed))
        tilt_speed = max(0, min(63, tilt_speed))
        self._send_pt(0x000C, pan_speed, tilt_speed)

    def move_down_right(self, pan_speed: int = 32, tilt_speed: int = 32):
        """Вниз + вправо. Down + Right = 0x0012."""
        pan_speed = max(0, min(63, pan_speed))
        tilt_speed = max(0, min(63, tilt_speed))
        self._send_pt(0x0012, pan_speed, tilt_speed)

    def move_down_left(self, pan_speed: int = 32, tilt_speed: int = 32):
        """Вниз + влево. Down + Left = 0x0014."""
        pan_speed = max(0, min(63, pan_speed))
        tilt_speed = max(0, min(63, tilt_speed))
        self._send_pt(0x0014, pan_speed, tilt_speed)

    # ---------------- PT: абсолютное наведение ----------------

    @staticmethod
    def _deg_to_units(deg: float) -> int:
        """
        Перевод градусов в единицы протокола:
        1 единица = 0.01 градуса.
        Поддерживаются отрицательные значения, возвращаем 16-битное представление.
        """
        val = int(round(deg * 100.0))  # -7000..7000 и т.п.
        return val & 0xFFFF  # two's complement

    def goto_position(self, pan_deg: float, tilt_deg: float):
        """
        Навести PT на заданный пан/тилт в градусах.

        Pan Direct   (0x004B): диапазон −179.99 .. +180.00
        Tilt Direct  (0x004D): по доке −70 .. +45
        """
        # по желанию можно жёстко ограничить диапазон
        pan_deg = max(-179.99, min(180.0, pan_deg))
        tilt_deg = max(-70.0, min(45.0, tilt_deg))

        pan_units = self._deg_to_units(pan_deg)
        tilt_units = self._deg_to_units(tilt_deg)

        pan_msb = (pan_units >> 8) & 0xFF
        pan_lsb = pan_units & 0xFF

        tilt_msb = (tilt_units >> 8) & 0xFF
        tilt_lsb = tilt_units & 0xFF

        # Pan Direct (Cmd = 0x004B, Data = MSB/LSB)
        self._send_pt(0x004B, pan_msb, pan_lsb)

        # Tilt Direct (Cmd = 0x004D, Data = MSB/LSB)
        self._send_pt(0x004D, tilt_msb, tilt_lsb)

    # ---------------- Камера: zoom / focus ----------------
    # 4.1 Lens Manual Control (стр. 17)
    # Cmd values:
    #   0x0000 = Zoom/Focus Stop
    #   0x0020 = Zoom Tele
    #   0x0040 = Zoom Wide
    #   0x0100 = Focus Near
    #   0x0080 = Focus Far

    def zoom_stop(self, sync_ir: bool = True):
        """
        Остановить зум (Zoom/Focus Stop).
        sync_ir: если True, также останавливает зум на тепловизоре.
        """
        self._send_cam(0x0000, 0x00, 0x00)
        if sync_ir:
            self._send_ir(0x0000, 0x00, 0x00)

    def zoom_in(self, sync_ir: bool = True):
        """
        Зум в сторону Tele (приближение).
        sync_ir: если True, также зумит тепловизор.
        """
        self._send_cam(0x0020, 0x00, 0x00)
        if sync_ir:
            self._send_ir(0x0020, 0x00, 0x00)

    def zoom_out(self, sync_ir: bool = True):
        """
        Зум в сторону Wide (отдаление).
        sync_ir: если True, также зумит тепловизор.
        """
        self._send_cam(0x0040, 0x00, 0x00)
        if sync_ir:
            self._send_ir(0x0040, 0x00, 0x00)

    def focus_stop(self):
        """Остановить фокус (Zoom/Focus Stop)."""
        self._send_cam(0x0000, 0x00, 0x00)

    def focus_near(self):
        """Фокус ближе (Focus Near = 0x0100)."""
        self._send_cam(0x0100, 0x00, 0x00)

    def focus_far(self):
        """Фокус дальше (Focus Far = 0x0080)."""
        self._send_cam(0x0080, 0x00, 0x00)


    def thermal_on(self):
        """
        Включить тепловизор (IR Cam).
        Power On (0x8800) для адреса 0x02.
        """
        self.power_on_ir()

    def thermal_off(self):
        """
        Выключить тепловизор (IR Cam).
        Power Off (0x0800) для адреса 0x02.
        """
        self.power_off_ir()

    # 4.4 Auto Focus Trigger (0x002B)
    def auto_focus(self, sync_ir: bool = True):
        """
        Запуск автофокуса (Auto Focus Trigger).
        sync_ir: если True, также запускает автофокус на тепловизоре.
        """
        self._send_cam(0x002B, 0x00, 0x00)
        if sync_ir:
            self._send_ir(0x002B, 0x00, 0x00)

    def auto_focus_ir(self):
        """Запуск автофокуса только для тепловизора (IR Cam)."""
        self._send_ir(0x002B, 0x00, 0x00)

    # --------- при желании: абсолютный zoom/focus ---------
    # Zoom Direct (0x004F) / Focus Direct (0x005F)
    def set_zoom_raw(self, value: int):
        """
        Установить зум по «сырым» единицам (MSB/LSB).
        Диапазон смотришь через Call Zoom Position Min Max, если понадобится.
        """
        value &= 0xFFFF
        msb = (value >> 8) & 0xFF
        lsb = value & 0xFF
        self._send_cam(0x004F, msb, lsb)

    def set_focus_raw(self, value: int):
        """
        Установить фокус по «сырым» единицам (MSB/LSB).
        Диапазон через Call Focus Position Min Max.
        """
        value &= 0xFFFF
        msb = (value >> 8) & 0xFF
        lsb = value & 0xFF
        self._send_cam(0x005F, msb, lsb)


if __name__ == "__main__":
    ptz = Tms20TCP("192.168.1.100")

    # Включить питание PT и камеры (если нужно)
    ptz.power_on_pt()
    ptz.power_on_cam()
    time.sleep(2)

    # 1) Наведение по углам
    ptz.goto_position(pan_deg=-30.0, tilt_deg=-50.0)

    time.sleep(3.0)

    # 2) Немного докрутить вручную вправо
    ptz.move_right()
    time.sleep(2.0)
    ptz.stop()

    # 3) Зум: чуть приблизить и остановить
    ptz.zoom_in()
    time.sleep(1.0)
    ptz.zoom_stop()

    # 4) Фокус вручную + автофокус
    ptz.focus_near()
    time.sleep(0.3)
    ptz.focus_stop()
    ptz.auto_focus()

    ptz.close()
