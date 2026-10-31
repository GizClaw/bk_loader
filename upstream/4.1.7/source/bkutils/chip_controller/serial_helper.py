import serial
import binascii
import time
from contextlib import contextmanager
from serial import Timeout
from ..common.common import get_os_type
from ..bk_log.log_utils import BKLog

class SerialHelper(object):

    def __init__(self):
        self.ser = None
        self._reported_baudrate = None

    def connect(self, port, baudrate, timeout):
        if get_os_type() == 'Windows' and (not port.startswith('COM')):
            port = f'COM{port}'
        self.ser = serial.Serial(port, baudrate, timeout=timeout)

    @property
    def baudrate(self):
        return self.ser.baudrate

    @contextmanager
    def report_baudrate_as(self, baudrate):
        previous_baudrate = self._reported_baudrate
        self._reported_baudrate = baudrate
        try:
            yield
        finally:
            self._reported_baudrate = previous_baudrate

    def switch_baudrate(self, baudrate):
        try:
            if baudrate != self.ser.baudrate:
                self.ser.baudrate = baudrate
        except Exception:
            reported_baudrate = self._reported_baudrate or baudrate
            raise Exception(f'Please confirm whether {self.ser.port} supports this baud rate: {reported_baudrate}.If not, please set the matched baud rate and power reset the chip.')

    def disconnect(self):
        self.ser.close()

    def reset(self, baudrate=None):
        if baudrate is None:
            baudrate = self.ser.baudrate
        self.disconnect()
        time.sleep(0.01)
        self.switch_baudrate(baudrate)
        self.ser.open()

    def write_cmd(self, cmd):
        BKLog.detail(True, cmd)
        self.ser.write(cmd)

    def drain(self):
        self.ser.reset_input_buffer()

    def wait_for_cmd_response_free(self, expect_length, timeout_sec=1):
        read_buf = b''
        strat_time = time.perf_counter()
        while time.perf_counter() - strat_time < timeout_sec:
            buf = self.ser.read(expect_length - len(read_buf))
            read_buf += buf
            if len(read_buf) >= expect_length:
                break
        BKLog.detail(False, read_buf)
        return read_buf

    def wait_for_cmd_response(self, expect_length, timeout_sec=1):
        read_buf = b''
        strat_time = time.perf_counter()
        valid_head = False
        while time.perf_counter() - strat_time < timeout_sec:
            buf = self.ser.read(expect_length - len(read_buf))
            read_buf += buf
            if not valid_head and read_buf != bytes([4]):
                for idx in range(len(read_buf) - 1):
                    if read_buf[idx:idx + 2] == bytes([4, 14]):
                        valid_head = True
                        read_buf = read_buf[idx:]
                        break
                if not valid_head:
                    read_buf = b''
            if len(read_buf) >= expect_length:
                break
        BKLog.detail(False, read_buf)
        return read_buf

    def write_cmd_and_wait_response(self, cmd, expect_length, timeout_sec=0.1):
        self.drain()
        self.write_cmd(cmd)
        tmp_res = False
        ret_content = self.wait_for_cmd_response(expect_length=expect_length, timeout_sec=timeout_sec)
        if len(ret_content) == expect_length:
            tmp_res = True
        return (tmp_res, ret_content)

    def write_cmd_and_wait_response_without_drain(self, cmd, expect_length, timeout_sec=0.1):
        self.write_cmd(cmd)
        tmp_res = False
        ret_content = self.wait_for_cmd_response(expect_length=expect_length, timeout_sec=timeout_sec)
        if len(ret_content) == expect_length:
            tmp_res = True
        return (tmp_res, ret_content)
