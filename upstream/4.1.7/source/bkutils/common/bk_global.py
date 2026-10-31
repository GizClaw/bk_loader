import logging
import os
from bkutils.common.common import INITIATOR

class BkInitiator(object):
    initiator_global = INITIATOR.CLI

    @staticmethod
    def set_initiator(initiator: INITIATOR) -> None:
        """设置全局启动器类型

        Args:
            initiator: 启动器类型，必须是 INITIATOR 枚举的成员
        """
        BkInitiator.initiator_global = initiator

class BkGlobalLogConfig(object):
    global_log_level = None
    global_log_folder_path = None
    global_enable_print_sensitive_information = None

    @staticmethod
    def enable_print_sensitive_information(enable):
        """设置全局是否打印敏感信息

        Args:
            enable: 是否打印敏感信息
        """
        if enable is None:
            return False
        BkGlobalLogConfig.global_enable_print_sensitive_information = enable

    @staticmethod
    def set_log_level(log_level) -> None:
        """设置全局日志级别

        Args:
            log_level: 日志级别，必须是 logging 模块定义的级别
        """
        if log_level is None:
            return
        log_level_map = {'-1': logging.NOTSET, '0': logging.CRITICAL, '1': logging.ERROR, '2': logging.WARNING, '3': logging.INFO, '999': logging.DEBUG}
        BkGlobalLogConfig.global_log_level = log_level_map.get(log_level)

    @staticmethod
    def set_log_folder_path(log_folder_path: str) -> None:
        """设置全局日志文件夹路径

        Args:
            log_folder_path: 日志文件夹路径
        """
        if log_folder_path is None:
            return
        BkGlobalLogConfig.global_log_folder_path = log_folder_path

    @staticmethod
    def has_file_permission(file_path: str, permission_type: str='read') -> bool:
        """判断当前程序是否有操作某个文件的权限

        Args:
            file_path: 文件路径
            permission_type: 权限类型，可选值为 'read', 'write', 'execute'

        Returns:
            bool: 是否有权限
        """
        if not os.path.exists(file_path):
            return False
        elif permission_type == 'read':
            return os.access(file_path, os.R_OK)
        elif permission_type == 'write':
            return os.access(file_path, os.W_OK)
        elif permission_type == 'execute':
            return os.access(file_path, os.X_OK)
        raise ValueError(f'Unsupported permission type: {permission_type}')

class BkFlashConfigOut(object):
    """bk flash配置文件"""
    flash_config_path_out = None

    def __init__(self, flash_config_path_out) -> None:
        if flash_config_path_out is None:
            return
        elif not os.path.isfile(flash_config_path_out):
            return
        BkFlashConfigOut.flash_config_path_out = flash_config_path_out

    @staticmethod
    def set_flash_config_path_out(flash_config_path_out: str):
        """设置bk flash配置文件路径

        Args:
            path: bk flash配置文件路径
        """
        BkFlashConfigOut(flash_config_path_out)
