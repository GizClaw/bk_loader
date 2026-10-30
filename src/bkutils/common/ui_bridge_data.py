import json
from dataclasses import dataclass
from enum import Enum


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


@dataclass
class DumpBinInfo:
    bin_path: str

    def to_json(self):
        return json.dumps({'bin_path': self.bin_path})


@dataclass
class DumpFolderInfo:
    folder_path: str

    def to_json(self):
        return json.dumps({'folder_path': self.folder_path})


@dataclass
class OutputBinInfo:
    type: str
    msg: str
    can_edit: bool

    def to_json(self):
        return json.dumps({
            'type': self.type,
            'msg': self.msg,
            'can_edit': str(self.can_edit),
        })


@dataclass
class OutputData:
    msg_type: MsgType
    msg_inner: str
    extra: str = ''

    def to_json(self):
        return json.dumps({
            'msg_type': self.msg_type.value,
            'msg_inner': self.msg_inner,
            'extra': str(self.extra),
        })


@dataclass
class TaskInfo:
    task_name: str
    task_id: int
    task_start: bool = False

    def to_json(self):
        return json.dumps({
            'task_name': self.task_name,
            'task_id': str(self.task_id),
            'task_start': str(self.task_start),
        })

    @staticmethod
    def list_to_json(task_info_list) -> str:
        return json.dumps([{
            'task_name': item.task_name,
            'task_id': str(item.task_id),
            'task_start': str(item.task_start),
        } for item in task_info_list])


@dataclass
class SerialInfo:
    port_name: str
    description: str
    hwid: str

    def to_json(self):
        return json.dumps({
            'port_name': self.port_name,
            'description': self.description,
            'hwid': self.hwid,
        })

    @staticmethod
    def list_to_json(serial_info_list):
        return json.dumps([{
            'port_name': item.port_name,
            'description': item.description,
            'hwid': item.hwid,
        } for item in serial_info_list])
