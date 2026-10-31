import copy
import time
import threading
from typing import List, Dict, Optional
from .single_port_download import SinglePortDownload
from ..bk_log.log_utils import *
from ..common import ui_bridge
from ..common.common import DownloadInfo, ExpandData, BIN_TYPE, LINKCHECK
from ..common.bk_out_config import BkDownloadFlowConfig

def resolve_link_check_type(bin_type, link_key=None):
    """根据 bin_type 解析 linkcheck_obj，与单口逻辑(bk_loader 243-290)一致。link_key 已指定时返回 BOOTROM_EXT；无 bin_type 时默认 BOOTROM。"""
    if link_key:
        return LINKCHECK.BOOTROM_EXT
    if bin_type is None:
        return LINKCHECK.BOOTROM
    if bin_type == BIN_TYPE.TYPE_SECURE_FIX:
        return LINKCHECK.BOOTROM
    if bin_type == BIN_TYPE.TYPE_BL2_APP_BIN:
        return LINKCHECK.BL2
    if bin_type == BIN_TYPE.TYPE_BL1_ALL_BIN or bin_type == BIN_TYPE.TYPE_OTA:
        return LINKCHECK.BOOTROM
    if bin_type == BIN_TYPE.TYPE_OUTTER_FLASH:
        return LINKCHECK.BOOTROM
    if bin_type == BIN_TYPE.TYPE_BL2_OTA:
        return LINKCHECK.BL2
    if bin_type == BIN_TYPE.TYPE_NORMAL:
        return LINKCHECK.BOOTROM
    if bin_type == BIN_TYPE.TYPE_SAM_UN:
        return LINKCHECK.BOOTROM
    if bin_type == BIN_TYPE.TYPE_SAM_EN:
        return LINKCHECK.BL2
    if bin_type == BIN_TYPE.TYPE_CUSTOM_UNSECURE:
        return LINKCHECK.BOOTROM
    if bin_type == BIN_TYPE.TYPE_CUSTOM_SECURE:
        return LINKCHECK.BL2
    if bin_type in (BIN_TYPE.TYPE_BL1_SECURE_EXTENSION, BIN_TYPE.TYPE_BL1_SECURE_FIXED):
        return LINKCHECK.BOOTROM
    return LINKCHECK.BOOTROM

class BatchDownload:
    """批量烧录类，支持多端口并行烧录
    
    职责：分发逻辑、线程管理、结果汇总
    不管理串口，每个端口由 SinglePortDownload 独立管理
    """

    def __init__(self, port_list: List[str], baudrate=115200, reset_type=None, reset_baudrate=115200, getbus_times=100, reboot_after_download=True, retry=5, chipname=None, debug='3', link_key=None, bin_type=None, random_bin_path=None, link_check_type_cli=None) -> None:
        self.port_list = port_list
        self.baudrate = baudrate
        if link_key:
            self.link_check_type = LINKCHECK.BOOTROM_EXT
        elif link_check_type_cli is not None:
            self.link_check_type = link_check_type_cli
        else:
            self.link_check_type = resolve_link_check_type(bin_type, None)
        self.reset_type = reset_type
        self.reset_baudrate = reset_baudrate
        self.reboot_after_download = reboot_after_download
        self.getbus_times = getbus_times
        self.retry = retry
        self.chip_name = chipname
        self.debug = debug
        self.link_key = link_key
        self.random_bin_path = random_bin_path
        self.results = {}
        self.results_lock = threading.Lock()

    def _download_single_port(self, port: str, downloadinfo: DownloadInfo, bin_type, channel_number: int=None) -> tuple:
        """单个端口的烧录逻辑。channel_number 为工厂模式通道号（1 开始），非工厂为 None。"""
        try:
            port_prefix = f'[{port}] '
            downloader = SinglePortDownload(port=port, baudrate=self.baudrate, link_check_type=self.link_check_type, reset_type=self.reset_type, reset_baudrate=self.reset_baudrate, getbus_times=self.getbus_times, reboot_after_download=self.reboot_after_download, retry=self.retry, chipname=self.chip_name, debug=self.debug, link_key=self.link_key, random_bin_path=self.random_bin_path, port_prefix=port_prefix, channel_number=channel_number)
            if bin_type is None:
                (result, error_msg) = downloader.download_mixed_task(downloadinfo)
            elif bin_type == BIN_TYPE.TYPE_BL1_SECURE_EXTENSION:
                (result, error_msg) = downloader.download_bl1_secure_extension_task(downloadinfo)
            elif bin_type == BIN_TYPE.TYPE_BL1_SECURE_FIXED:
                (result, error_msg) = downloader.download_bl1_secure_fixed_task(downloadinfo)
            elif bin_type == BIN_TYPE.TYPE_SECURE_FIX:
                (result, error_msg) = downloader.download_secure_task(downloadinfo)
            elif bin_type == BIN_TYPE.TYPE_OUTTER_FLASH:
                (result, error_msg) = downloader.download_with_outter_flash_task(downloadinfo)
            elif bin_type == BIN_TYPE.TYPE_BL2_OTA:
                (result, error_msg) = downloader.download_bootloader_ota(downloadinfo)
            else:
                (result, error_msg) = downloader.download_base_task(downloadinfo)
            return (result, error_msg)
        except Exception as e:
            error_msg = str(e)
            BKLog.e(f'[{port}] Exception: {error_msg}')
            if channel_number is not None:
                ui_bridge.factory_channel_status(channel_number, port, 'failure', 100, 0, error_message=error_msg)
            return (False, error_msg)

    def batch_download(self, downloadinfo: DownloadInfo, bin_type=None, report_channel_progress: bool=False, expand_rolling_steps: Optional[List[int]]=None) -> Dict[str, tuple]:
        """批量烧录主入口。report_channel_progress: 为 True 时向 UI 推送每通道进度（工厂模式）。
        expand_rolling_steps: 与 expand_data_list 同长的步长列表，非 0 表示该条为滚码，端口 i 使用 baseline + i*step。"""
        threads = []
        port_list_filtered = [p.strip() for p in self.port_list if p and p.strip()]
        port_download_infos = []
        if expand_rolling_steps and len(downloadinfo.expand_data_list) == len(expand_rolling_steps):
            for idx in range(len(port_list_filtered)):
                di = copy.deepcopy(downloadinfo)
                for (j, step) in enumerate(expand_rolling_steps):
                    if step > 0 and j < len(di.expand_data_list):
                        ed = di.expand_data_list[j]
                        baseline_int = int.from_bytes(ed.value, 'big')
                        new_int = baseline_int + idx * step
                        length = ed.length
                        max_val = (1 << length * 8) - 1
                        new_int = new_int & max_val
                        di.expand_data_list[j] = ExpandData(ed.name, ed.start_addr, length, new_int.to_bytes(length, 'big'))
                port_download_infos.append(di)
        else:
            for _ in range(len(port_list_filtered)):
                port_download_infos.append(copy.deepcopy(downloadinfo))

        def download_thread(port: str, channel_number: int, port_index: int):
            ch = channel_number if report_channel_progress else None
            info = port_download_infos[port_index] if port_index < len(port_download_infos) else downloadinfo
            (success, error_msg) = self._download_single_port(port, info, bin_type, ch)
            with self.results_lock:
                self.results[port] = (success, error_msg)
        for (idx, port) in enumerate(port_list_filtered):
            ch = idx + 1
            thread = threading.Thread(target=download_thread, args=(port, ch, idx))
            thread.start()
            threads.append(thread)
        for thread in threads:
            thread.join()
        return self.results

    def print_summary(self):
        """输出汇总信息"""
        total = len(self.results)
        success_count = sum((1 for (success, _) in self.results.values() if success))
        failed_count = total - success_count
        failed_ports = [port for (port, (success, _)) in self.results.items() if not success]
        BKLog.w('==================================================')
        BKLog.w('Batch Download Summary')
        BKLog.w('==================================================')
        BKLog.w(f'Total ports: {total}')
        BKLog.w(f'Success: {success_count}')
        BKLog.w(f'Failed: {failed_count}')
        if failed_ports:
            BKLog.w(f"Failed ports: {', '.join(failed_ports)}")
        BKLog.w('==================================================')
