from abc import ABC, abstractmethod
import logging

class ALog(ABC):

    def __init__(self, logger_level=logging.INFO, log_folder_path=None, threading_id=None, COM_PORT=''):
        pass

    @abstractmethod
    def i(self, msg, *args, **kwargs):
        pass

    @abstractmethod
    def d(self, msg, *args, **kwargs):
        pass

    @abstractmethod
    def w(self, msg, *args, **kwargs):
        pass

    @abstractmethod
    def e(self, msg, *args, **kwargs):
        pass

    @abstractmethod
    def progress_log(self, device: str, status: str, progress: int, task_progress: bool=False):
        pass

    @abstractmethod
    def detail(self, out: bool, data_bytes: bytes):
        pass

    @abstractmethod
    def check_detail_logger(self) -> bool:
        pass
