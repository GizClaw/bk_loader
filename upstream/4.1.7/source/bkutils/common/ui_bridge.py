global _factory_stop_channels
global _factory_stop_all
import json
import os
import signal
import sys
import threading
import serial
import serial.tools.list_ports
from bkutils.bk_log.log_utils import BKLog
from bkutils.common.bk_global import BkInitiator
from bkutils.common.common import BIN_TYPE, get_os_type, parse_binfile_info, parse_binfile_info_json
from bkutils.common.ui_bridge_data import DumpBinInfo, DumpFolderInfo, MsgType, OutputBinInfo, OutputData, SerialInfo, TaskInfo
from bkutils.common.common import INITIATOR, ExtraData
_factory_stop_lock = threading.Lock()
_factory_stop_all = False
_factory_stop_channels = set()

def reset_factory_stop():
    """工厂烧录开始时重置停止标志"""
    global _factory_stop_channels
    global _factory_stop_all
    with _factory_stop_lock:
        _factory_stop_all = False
        _factory_stop_channels = set()

def set_stop_all():
    """请求停止所有通道"""
    global _factory_stop_all
    with _factory_stop_lock:
        _factory_stop_all = True

def add_stop_channel(channel_number: int):
    """请求停止指定通道（通道编号，1 开始）"""
    with _factory_stop_lock:
        _factory_stop_channels.add(channel_number)

def should_stop_factory(channel_number: int) -> bool:
    """是否应停止该通道（含 stop_all 或 stop_channel）"""
    with _factory_stop_lock:
        if _factory_stop_all:
            return True
        return channel_number in _factory_stop_channels

def factory_channel_status(channel_number: int, com_port: str, status: str, progress: int, elapsed_seconds: int, error_message=None, phase: str=None):
    """推送工厂通道状态到前端（用于多通道烧录进度）。phase 为当前阶段，如 get_bus/erase/write/write_expand_data/write_safe_json。"""
    if not check():
        return
    extra = {'channel_number': channel_number, 'com_port': com_port, 'status': status, 'progress': progress, 'elapsed_seconds': elapsed_seconds, 'error_message': error_message, 'phase': phase}
    outdata = OutputData(msg_type=MsgType.FACTORY_CHANNEL_STATUS, msg_inner='channel progress', extra=json.dumps(extra))
    BKLog.w('', outdata)

def check() -> bool:
    return BkInitiator.initiator_global == INITIATOR.FLUTTER_UI

def end_flag(msg: str, ret: bool, error_message=None):
    """通知 UI 任务结束。ret 为是否成功；error_message 为失败时的错误信息，会带给 UI 展示。"""
    if not check():
        return
    if error_message and (not ret):
        import json as _json
        extra = _json.dumps({'success': False, 'error': error_message})
    else:
        extra = str(ret)
    outdata = OutputData(msg_type=MsgType.END_FLAG, msg_inner=msg, extra=extra)
    BKLog.i('', outdata)

def task_flag(task_info: TaskInfo):
    if not check():
        return
    outdata = OutputData(msg_type=MsgType.TASK_FLAG, msg_inner='task flag', extra=task_info.to_json())
    BKLog.w('', outdata)

def task_list(task_list):
    if not check():
        return
    msg = TaskInfo.list_to_json(task_list)
    outdata = OutputData(msg_type=MsgType.TASK_LIST, msg_inner='task list', extra=msg)
    BKLog.w('', outdata)

def port_info():
    if not check():
        return
    ports = serial.tools.list_ports.comports()
    serial_info_list = []
    for port in ports:
        if len(port.hwid) <= 0:
            continue
        serial_info_list.append(SerialInfo(port.device, port.description, port.hwid))
    outdata = OutputData(msg_type=MsgType.PORT_INFO, msg_inner='port info', extra=SerialInfo.list_to_json(serial_info_list))
    BKLog.i('', outdata)

def bin_info(infile: str, infile_json: str=None):
    if not check():
        return
    try:
        extra_data = ExtraData(just_read_file_info=True)
        if infile_json:
            (bin_type, binlist, pathlist) = parse_binfile_info_json(infile_json, 0, extra_data=extra_data)
        else:
            (bin_type, binlist, pathlist) = parse_binfile_info(infile, 0, extra_data=extra_data)
    except Exception as e:
        output_bin_info = OutputBinInfo(type='unknown', msg=str(e), can_edit=False, supported=False)
        outdata = OutputData(msg_type=MsgType.BIN_INFO, msg_inner='bin info', extra=output_bin_info.to_json())
        BKLog.i('', outdata)
        return
    if bin_type == BIN_TYPE.TYPE_NORMAL:
        linkcheck = 'bootrom or bootloader'
        type = 'normal'
    elif bin_type == BIN_TYPE.TYPE_OTA:
        linkcheck = 'bootrom or bootloader'
        type = 'ota'
    elif bin_type == BIN_TYPE.TYPE_BL1_ALL_BIN:
        linkcheck = 'bootrom or bootloader'
        type = 'bootrom all'
    elif bin_type == BIN_TYPE.TYPE_BL2_APP_BIN:
        linkcheck = 'bootloader'
        type = 'bootloader app'
    elif bin_type == BIN_TYPE.TYPE_SECURE_FIX:
        linkcheck = 'bootrom or bootloader'
        type = 'secure fix'
    elif bin_type == BIN_TYPE.TYPE_OUTTER_FLASH:
        linkcheck = 'bootrom'
        type = 'outter'
    elif bin_type == BIN_TYPE.TYPE_NORMAL_FIXED:
        linkcheck = 'bootrom or bootloader'
        type = 'normal fixed'
    elif bin_type == BIN_TYPE.TYPE_BL2_OTA:
        linkcheck = 'bootloader'
        type = 'bootloader ota'
    elif bin_type == BIN_TYPE.TYPE_SAM_UN:
        linkcheck = 'bootrom'
        type = 'unsecurity'
    elif bin_type == BIN_TYPE.TYPE_SAM_EN:
        linkcheck = 'bootloader'
        type = 'security'
    elif bin_type == BIN_TYPE.TYPE_CUSTOM_UNSECURE:
        linkcheck = 'bootrom'
        type = 'unsecurity'
    elif bin_type == BIN_TYPE.TYPE_CUSTOM_SECURE:
        linkcheck = 'bootloader'
        type = 'security'
    elif bin_type == BIN_TYPE.TYPE_BL1_SECURE_EXTENSION:
        linkcheck = 'bootrom'
        type = 'BL1 secure extension'
    elif bin_type == BIN_TYPE.TYPE_BL1_SECURE_FIXED:
        linkcheck = 'bootrom'
        type = 'BL1 secure fixed'
    elif bin_type is None:
        linkcheck = 'bootrom'
        type = 'mixed'
    else:
        linkcheck = 'nothing'
        type = 'nothing'
    can_edit = bin_type == BIN_TYPE.TYPE_NORMAL
    image_count = sum((len(single_type_bin.binList) for single_type_bin in binlist))
    msg = f'type:{type}\nlinkcheck:{linkcheck}\nimage:{image_count} '
    output_type = bin_type.name if bin_type is not None else 'MIXED'
    output_bin_info = OutputBinInfo(type=output_type, msg=msg, can_edit=can_edit, supported=True)
    outdata = OutputData(msg_type=MsgType.BIN_INFO, msg_inner='bin info', extra=output_bin_info.to_json())
    BKLog.i('', outdata)

def dump_bin_info(bin_path: str):
    if not check():
        return
    dump_bin_info = DumpBinInfo(bin_path=bin_path)
    outdata = OutputData(msg_type=MsgType.DUMP_BIN_INFO, msg_inner='read bin path:', extra=dump_bin_info.to_json())
    BKLog.i('', outdata)

def dump_folder_info(folder_path: str):
    if not check():
        return
    dump_folder_info = DumpFolderInfo(folder_path=folder_path)
    outdata = OutputData(msg_type=MsgType.DUMP_FOLDER_INFO, msg_inner='read folder path:', extra=dump_folder_info.to_json())
    BKLog.i('', outdata)

class MonitorStdin:

    def __init__(self):
        return

    def start(self):
        self.monitor_thread = threading.Thread(target=self.monitor_cmd)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()

    def monitor_cmd(self):
        for line in sys.stdin:
            command = line.strip()
            cmd_lower = command.lower()
            if cmd_lower in ['exit', 'exit_from_flutter']:
                BKLog.i('exit by user')
                self.stop_process()
            elif cmd_lower == 'stop_all':
                set_stop_all()
                BKLog.i('factory: stop_all received')
            elif cmd_lower.startswith('stop_channel'):
                parts = command.split()
                if len(parts) == 2:
                    try:
                        ch = int(parts[1])
                        add_stop_channel(ch)
                        BKLog.i('factory: stop_channel %d received' % ch)
                    except ValueError:
                        BKLog.i('factory: invalid stop_channel argument')
            else:
                BKLog.i('unknown command')

    def stop_process(self):
        os_type = get_os_type()
        if os_type == 'Windows':
            os._exit(0)
        else:
            os.kill(os.getpid(), signal.SIGTERM)
