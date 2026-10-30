import logging
import os

from .common import INITIATOR


class BkInitiator:
    initiator_global = INITIATOR.CLI

    @staticmethod
    def set_initiator(initiator: INITIATOR) -> None:
        BkInitiator.initiator_global = initiator


class BkGlobalLogConfig:
    global_log_level = None
    global_log_folder_path = None
    global_enable_print_sensitive_information = None

    @staticmethod
    def enable_print_sensitive_information(enable):
        if enable is None:
            return False
        BkGlobalLogConfig.global_enable_print_sensitive_information = enable

    @staticmethod
    def set_log_level(log_level) -> None:
        if log_level is None:
            return
        levels = {
            '-1': logging.NOTSET,
            '0': logging.CRITICAL,
            '1': logging.ERROR,
            '2': logging.WARNING,
            '3': logging.INFO,
            '999': logging.DEBUG,
        }
        BkGlobalLogConfig.global_log_level = levels.get(log_level)

    @staticmethod
    def set_log_folder_path(log_folder_path: str) -> None:
        if log_folder_path is not None:
            BkGlobalLogConfig.global_log_folder_path = log_folder_path

    @staticmethod
    def has_file_permission(file_path: str, permission_type: str = 'read') -> bool:
        if not os.path.exists(file_path):
            return False
        modes = {'read': os.R_OK, 'write': os.W_OK, 'execute': os.X_OK}
        if permission_type not in modes:
            raise ValueError(f'Unsupported permission type: {permission_type}')
        return os.access(file_path, modes[permission_type])


class BkFlashConfigOut:
    flash_config_path_out = None

    def __init__(self, flash_config_path_out) -> None:
        if flash_config_path_out is not None and os.path.isfile(flash_config_path_out):
            BkFlashConfigOut.flash_config_path_out = flash_config_path_out

    @staticmethod
    def set_flash_config_path_out(flash_config_path_out: str):
        BkFlashConfigOut(flash_config_path_out)
