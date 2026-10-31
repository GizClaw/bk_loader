import time
from ..chip_controller import SerialHelper
from ..chip_controller import BaseController
from ..chip_controller import get_chip_set_with_chip_name, get_chip_set_with_chip_id
from ..common.bk_out_config import BkOutConfig
from ..bk_log.log_utils import *

class ActionBase(object):

    def __init__(self, port, baudrate=115200) -> None:
        self.ser = self.__init_serial(port, baudrate)

    def __init_serial(self, port, baudrate):
        tmp_ser = SerialHelper()
        tmp_ser.connect(port, baudrate, 0)
        return tmp_ser

    def _get_chip_set(self, find_sec_id=True):
        base_controller = BaseController(serial_instance=self.ser)
        chip_set = get_chip_set_with_chip_name(BkOutConfig.chip_name)
        if chip_set is None:
            sec_id = 0
            if self.chip_id is None:
                self.chip_id = base_controller.get_chip_id_retry(self.retry)
                if self.chip_id is None:
                    raise Exception('get chip id fail.')
                if find_sec_id:
                    if (self.chip_id == 29238 or self.chip_id >> 16 == 29238) and self.chip_id != 1916161540 and (self.chip_id != 1916162306):
                        sec_id = base_controller.get_second_chip_id()
                        if sec_id is None:
                            raise Exception('get sec chip id fail.')
                else:
                    sec_id = 638844960
            BKLog.sensitive_information('chip id is 0x{:x}'.format(self.chip_id))
            chip_set = get_chip_set_with_chip_id(self.chip_id, sec_id)
        if chip_set is None:
            raise Exception('get chip set fail.')
        return chip_set

    def print_sensitive_information(self, msg):
        BKLog.w(msg)

    def _init_log_level(self, port, debug):
        if debug == '0':
            BKLog(logger_level=logging.CRITICAL, log_folder_path='./', threading_id=threading.current_thread().ident, COM_PORT=port)
        elif debug == '1':
            BKLog(logger_level=logging.ERROR, log_folder_path='./', threading_id=threading.current_thread().ident, COM_PORT=port)
        elif debug == '2':
            BKLog(logger_level=logging.WARNING, log_folder_path='./', threading_id=threading.current_thread().ident, COM_PORT=port)
        elif debug == '3':
            BKLog(logger_level=logging.INFO, log_folder_path='./', threading_id=threading.current_thread().ident, COM_PORT=port)
        elif debug == '999':
            BKLog(logger_level=logging.DEBUG, log_folder_path='./', threading_id=threading.current_thread().ident, COM_PORT=port)
