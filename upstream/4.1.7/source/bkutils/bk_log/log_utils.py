import json
import os
import sys
import logging
import threading
from bkutils.bk_log.cli_log import CliLog
from bkutils.bk_log.flutter_ui_log import FlutterUiLog
from bkutils.common.bk_global import BkGlobalLogConfig, BkInitiator
from ..common.common import INITIATOR

class BKLog(object):
    log_map = {}
    ifclose = False
    default_logger = None

    def __init__(self, logger_level=logging.INFO, log_folder_path=None, threading_id=None, COM_PORT=''):
        if threading_id is None:
            threading_id = threading.current_thread().ident
        if BKLog.log_map.get(threading_id, None) is not None:
            raise Exception('logger only init once in one thread')
        if BkGlobalLogConfig.global_log_level is not None:
            logger_level = BkGlobalLogConfig.global_log_level
        if BkGlobalLogConfig.global_log_folder_path is not None:
            log_folder_path = BkGlobalLogConfig.global_log_folder_path
        if BkInitiator.initiator_global == INITIATOR.CLI:
            BKLog.log_map[threading_id] = CliLog(logger_level, log_folder_path, COM_PORT)
        elif BkInitiator.initiator_global == INITIATOR.FLUTTER_UI:
            BKLog.log_map[threading_id] = FlutterUiLog(logger_level, log_folder_path, COM_PORT)

    @staticmethod
    def _real_logger():
        if BKLog.ifclose:
            return
        threading_id = threading.current_thread().ident
        logger = BKLog.log_map.get(threading_id, None)
        if logger is not None:
            return logger
        if BKLog.default_logger is None:
            logger_level = logging.INFO
            if BkGlobalLogConfig.global_log_level is not None:
                logger_level = BkGlobalLogConfig.global_log_level
            log_folder_path = None
            if BkGlobalLogConfig.global_log_folder_path is not None:
                log_folder_path = BkGlobalLogConfig.global_log_folder_path
            else:
                log_folder_path = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            if BkInitiator.initiator_global == INITIATOR.CLI:
                BKLog.default_logger = CliLog(logger_level, log_folder_path, '')
            elif BkInitiator.initiator_global == INITIATOR.FLUTTER_UI:
                BKLog.default_logger = FlutterUiLog(logger_level, log_folder_path, '')
        return BKLog.default_logger

    @staticmethod
    def _safe_log(log_func, *args, **kwargs):
        try:
            logger = BKLog._real_logger()
            if logger is None:
                return
            log_func(logger, *args, **kwargs)
        except Exception as e:
            try:
                print(f'BKLog failed: {e}', file=sys.stderr)
            except Exception:
                pass

    @staticmethod
    def d(msg, *args, **kwargs):
        return

    @staticmethod
    def i(msg, *args, **kwargs):
        BKLog._safe_log(lambda logger: logger.i(msg, *args, **kwargs))

    @staticmethod
    def w(msg, *args, **kwargs):
        BKLog._safe_log(lambda logger: logger.w(msg, *args, **kwargs))

    @staticmethod
    def e(msg, *args, **kwargs):
        BKLog._safe_log(lambda logger: logger.e(msg, *args, **kwargs))

    @staticmethod
    def progress_log(device: str, status: str, progress: int, task_progress: bool=False):
        BKLog._safe_log(lambda logger: logger.progress_log(device, status, progress, task_progress))

    @staticmethod
    def detail(out: bool, data_bytes: bytes):
        BKLog._safe_log(lambda logger: logger.detail(out, data_bytes))

    @staticmethod
    def sensitive_information(msg: str):
        if BkGlobalLogConfig.global_enable_print_sensitive_information:
            BKLog._safe_log(lambda logger: logger.w(msg))
if __name__ == '__main__':

    def program_progress_log(device, progress):
        BKLog.progress_log(device, 'Programming', progress)

    def test_thread(com_num):
        BKLog(logger_level=logging.INFO, log_folder_path='./', threading_id=threading.current_thread().ident, COM_PORT=com_num)
        BKLog.d(f'{com_num} debug level log test')
        BKLog.i(f'{com_num} info level log test')
        BKLog.w(f'{com_num} warning level log test')
        BKLog.e(f'{com_num} errot level log test')
        for _ in range(0, 101, 10):
            BKLog.progress_log(com_num, 'Erasing', _)
        for _ in range(0, 101, 10):
            program_progress_log(com_num, _)
    BKLog(logger_level=logging.INFO, log_folder_path='./')
    BKLog.i('debug level log test')
    t_group = []
    for _ in range(5):
        t_group.append(threading.Thread(target=test_thread, args=(f'COM{_}',)))
    for tmp_t in t_group:
        tmp_t.start()
    for tmp_t in t_group:
        tmp_t.join()
    BKLog.i('finish test')
