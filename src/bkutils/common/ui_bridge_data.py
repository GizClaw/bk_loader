import json
from enum import Enum
from dataclasses import dataclass

class MsgType(Enum):
    NORMAL = 'normal'
    PROGRESS = 'progress'
    TASK_LIST = 'task_list'
    END_FLAG = 'end_flag'
    TASK_FLAG = 'task_flag'
    PORT_INFO = 'port_info'
    BIN_INFO = 'bin_info'
    DUMP_BIN_INFO = 'dump_bin_info'
    DUMP_FOLDER_INFO = 'dump_folder_info'
    FACTORY_CHANNEL_STATUS = 'factory_channel_status'

@dataclass
class DumpBinInfo:
    bin_path: str

    def to_json(self):
        json_dict = {'bin_path': self.bin_path}
        return json.dumps(json_dict)

@dataclass
class DumpFolderInfo:
    folder_path: str

    def to_json(self):
        json_dict = {'folder_path': self.folder_path}
        return json.dumps(json_dict)

@dataclass
class OutputBinInfo:
    type: str
    msg: str
    can_edit: bool
    supported: bool

    def to_json(self):
        json_dict = {'type': self.type, 'msg': self.msg, 'can_edit': str(self.can_edit), 'supported': str(self.supported)}
        return json.dumps(json_dict)

@dataclass
class OutputData:
    msg_type: MsgType
    msg_inner: str
    extra: str = ''

    def to_json(self):
        json_dict = {'msg_type': self.msg_type.value, 'msg_inner': self.msg_inner, 'extra': str(self.extra)}
        return json.dumps(json_dict)

@dataclass
class TaskInfo:
    task_name: str
    task_id: int
    task_start: bool = False

    def to_json(self):
        log_data = {'task_name': self.task_name, 'task_id': str(self.task_id), 'task_start': str(self.task_start)}
        return json.dumps(log_data)

    @staticmethod
    def list_to_json(task_info_list) -> str:
        """将TaskInfo对象列表转换为JSON字符串"""
        task_dicts = []
        for task_info in task_info_list:
            task_dict = {'task_name': task_info.task_name, 'task_id': str(task_info.task_id), 'task_start': str(task_info.task_start)}
            task_dicts.append(task_dict)
        return json.dumps(task_dicts)

@dataclass
class SerialInfo:
    port_name: str
    description: str
    hwid: str

    def to_json(self):
        log_data = {'port_name': self.port_name, 'description': self.description, 'hwid': self.hwid}
        return json.dumps(log_data)

    @staticmethod
    def list_to_json(serial_info_list):
        """将SerialInfo对象列表转换为JSON字符串"""
        serial_info_dicts = []
        for serial_info in serial_info_list:
            serial_info_dict = {'port_name': serial_info.port_name, 'description': serial_info.description, 'hwid': serial_info.hwid}
            serial_info_dicts.append(serial_info_dict)
        return json.dumps(serial_info_dicts)
