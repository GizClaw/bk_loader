import json
import logging
import os
import sys
from bkutils.bk_log.base_bk_log import ALog
from logging.handlers import RotatingFileHandler
from bkutils.common.bk_global import BkGlobalLogConfig
from bkutils.common.ui_bridge_data import MsgType, OutputData, TaskInfo

def _print_log_warning(message):
    try:
        print(message, file=sys.stderr)
    except Exception:
        pass

class FlutterUiLog(ALog):

    def __init__(self, logger_level=logging.INFO, log_folder_path=None, COM_PORT=''):
        self.port = COM_PORT
        self.pre_percent = -1
        self.logger = logging.getLogger(f'BKLog_{COM_PORT}')
        self.logger.setLevel(logger_level)
        formatter = logging.Formatter(f'%(asctime)s %(levelname)-7s {COM_PORT} # %(message)s')
        stdout_formatter = JSONFormatter(COM_PORT)
        stdout_handler = logging.StreamHandler(sys.stdout)
        stdout_handler.setLevel(logger_level)
        stdout_handler.setFormatter(stdout_formatter)
        self.logger.addHandler(stdout_handler)
        if log_folder_path is not None and logger_level < logging.WARNING:
            try:
                if not os.path.exists(log_folder_path):
                    os.makedirs(log_folder_path)
            except Exception as e:
                _print_log_warning(f'Failed to create log folder: {e}')
                return
            if not BkGlobalLogConfig.has_file_permission(log_folder_path, 'write'):
                _print_log_warning(f'Log folder {log_folder_path} does not have write permission')
                return
            log_file_name = (f'bk_flash{COM_PORT}.log' if COM_PORT.startswith('/') or len(COM_PORT) == 0 else f'bk_flash_{COM_PORT}.log').replace('/', '_')
            log_file_path = os.path.join(log_folder_path, log_file_name)
            try:
                file_handler = RotatingFileHandler(log_file_path, maxBytes=10485760, backupCount=10)
                file_handler.setLevel(logger_level)
                file_handler.setFormatter(formatter)
                self.logger.addHandler(file_handler)
            except Exception as e:
                _print_log_warning(f'Failed to open log file {log_file_path}: {e}')
                return
            if logger_level == logging.DEBUG:
                detail_formatter = logging.Formatter('%(asctime)s  %(message)s')
                debug_file_name = f'Debug_{log_file_name}'
                debug_file_path = os.path.join(log_folder_path, debug_file_name)
                try:
                    detail_file_handler = RotatingFileHandler(debug_file_path, maxBytes=10485760, backupCount=10)
                    detail_file_handler.setLevel(logger_level)
                    detail_file_handler.setFormatter(detail_formatter)
                    self.detail_logger = logging.getLogger(f'BKLogDetail_{COM_PORT}')
                    self.detail_logger.setLevel(logger_level)
                    self.detail_logger.addHandler(detail_file_handler)
                    self.detail_log_start()
                except Exception as e:
                    _print_log_warning(f'Failed to open detail log file {debug_file_path}: {e}')

    def detail_log_start(self):
        if not self.check_detail_logger():
            return
        self.detail_logger.debug('\n\n\n========================detail log start========================\n\n\n')

    def i(self, msg, *args, **kwargs):
        if len(args) > 0 and type(args[0]) is OutputData:
            outdata = args[0]
        else:
            outdata = OutputData(msg_type=MsgType.NORMAL, msg_inner=msg)
        self.logger.info(outdata.to_json())

    def d(self, msg, *args, **kwargs):
        if len(args) > 0 and type(args[0]) is OutputData:
            outdata = args[0]
        else:
            outdata = OutputData(msg_type=MsgType.NORMAL, msg_inner=msg)
        self.logger.debug(outdata.to_json())

    def w(self, msg, *args, **kwargs):
        if len(args) > 0 and type(args[0]) is OutputData:
            outdata = args[0]
        else:
            outdata = OutputData(msg_type=MsgType.NORMAL, msg_inner=msg)
        self.logger.warning(outdata.to_json())

    def e(self, msg, *args, **kwargs):
        if len(args) > 0 and type(args[0]) is OutputData:
            outdata = args[0]
        else:
            outdata = OutputData(msg_type=MsgType.NORMAL, msg_inner=msg)
        self.logger.error(outdata.to_json(), *args, **kwargs)

    def progress_log(self, device: str, status: str, progress: int, task_progress: bool=False):
        if progress != self.pre_percent and task_progress:
            self.pre_percent = progress
            msg = 'DEVICE: {0}, Status: {1}, Progress: {2}'.format(device, status, progress)
            outdata = OutputData(msg_type=MsgType.PROGRESS, msg_inner=msg, extra=progress)
            self.logger.info(outdata.to_json())

    def detail(self, out: bool, data_bytes: bytes):
        if not self.check_detail_logger():
            return
        header = '[OUT]  ' if out else '[IN]   '
        if len(data_bytes) > 200:
            data_bytes = data_bytes[:200]
        data = ' '.join((f'{byte:02x}' for byte in data_bytes))
        self.detail_logger.debug(f'{header} {data}')

    def check_detail_logger(self) -> bool:
        if not hasattr(self, 'detail_logger'):
            return False
        if self.detail_logger is None:
            return False
        return True

class JSONFormatter(logging.Formatter):

    def __init__(self, com_port=''):
        self.com_port = com_port
        super().__init__()

    def format(self, record):
        log_data = {'timestamp': self.formatTime(record, self.datefmt), 'level': record.levelname, 'com_port': self.com_port, 'message': record.getMessage()}
        if record.exc_info:
            log_data['exc_info'] = self.formatException(record.exc_info)
        return '@@@@bk_flash_flutter_ui_log_start@@@@' + json.dumps(log_data) + '@@@@bk_flash_flutter_ui_log_end@@@@'
