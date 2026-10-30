import os
import signal
import sys
import threading

import serial.tools.list_ports

from ..bk_log.log_utils import BKLog
from .bk_global import BkInitiator
from .common import BIN_TYPE, INITIATOR, get_os_type, parse_binfile_info
from .ui_bridge_data import (
    DumpBinInfo,
    DumpFolderInfo,
    MsgType,
    OutputBinInfo,
    OutputData,
    SerialInfo,
    TaskInfo,
)


def check():
    return BkInitiator.initiator_global == INITIATOR.FLUTTER_UI


def end_flag(msg=None, ret=None):
    if check():
        BKLog.i('', OutputData(MsgType.END_FLAG, msg, ret))


def task_flag(task_info):
    if check():
        BKLog.w('', OutputData(MsgType.TASK_FLAG, 'task flag', task_info.to_json()))


def task_list(tasks):
    if check():
        BKLog.w('', OutputData(MsgType.TASK_LIST, 'task list', TaskInfo.list_to_json(tasks)))


def port_info():
    if not check():
        return
    ports = [
        SerialInfo(port.device, port.description, port.hwid)
        for port in serial.tools.list_ports.comports()
        if port.hwid
    ]
    BKLog.i('', OutputData(MsgType.PORT_INFO, 'port info', SerialInfo.list_to_json(ports)))


def bin_info(infile):
    if not check():
        return
    bin_type, binlist, _ = parse_binfile_info(infile, 0)
    labels = {
        BIN_TYPE.TYPE_NORMAL: ('normal', 'bootrom or bootloader'),
        BIN_TYPE.TYPE_OTA: ('ota', 'bootrom or bootloader'),
        BIN_TYPE.TYPE_BL1_ALL_BIN: ('bootrom all', 'bootrom or bootloader'),
        BIN_TYPE.TYPE_BL2_APP_BIN: ('bootloader app', 'bootloader'),
        BIN_TYPE.TYPE_SECURE_FIX: ('secure fix', 'bootrom or bootloader'),
        BIN_TYPE.TYPE_OUTTER_FLASH: ('outter', 'bootrom'),
        BIN_TYPE.TYPE_NORMAL_FIXED: ('normal fixed', 'bootrom or bootloader'),
        BIN_TYPE.TYPE_BL2_OTA: ('bootloader ota', 'bootloader'),
    }
    type_name, linkcheck = labels.get(bin_type, ('nothing', 'nothing'))
    message = f'type:{type_name}\nlinkcheck:{linkcheck}\nimage:{len(binlist)} '
    data = OutputBinInfo(bin_type.name, message, bin_type == BIN_TYPE.TYPE_NORMAL)
    BKLog.i('', OutputData(MsgType.BIN_INFO, 'bin info', data.to_json()))


def dump_bin_info(bin_path):
    if check():
        data = DumpBinInfo(bin_path)
        BKLog.i('', OutputData(MsgType.DUMP_BIN_INFO, 'read bin path:', data.to_json()))


def dump_folder_info(folder_path):
    if check():
        data = DumpFolderInfo(folder_path)
        BKLog.i('', OutputData(MsgType.DUMP_FOLDER_INFO, 'read folder path:', data.to_json()))


class MonitorStdin:
    def start(self):
        self.monitor_thread = threading.Thread(target=self.monitor_cmd, daemon=True)
        self.monitor_thread.start()

    def monitor_cmd(self):
        for line in sys.stdin:
            command = line.strip().lower()
            if command in ('exit', 'exit_from_flutter'):
                BKLog.i('exit by user')
                self.stop_process()
            else:
                BKLog.i('unknown command')

    def stop_process(self):
        if get_os_type() == 'Windows':
            os._exit(0)
        os.kill(os.getpid(), signal.SIGTERM)
