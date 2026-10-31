import time
import os
import json
import re
from typing import Optional
from ..common import ui_bridge
from ..common.ui_bridge_data import TaskInfo
from .action_base import ActionBase
from ..bk_log.log_utils import *
from bkutils.protocol.app import InjectKeyStartProtocol, InjectKeyHandshakeProtocol, InjectKeySetSecureBootProtocol, InjectKeyWriteAesKeyProtocol, InjectKeyWriteRandomKeyProtocol, InjectKeyFinishHandshakeProtocol

def _remove_comments(content: str) -> str:
    """移除以 # 开头的注释行"""
    lines = content.split('\n')
    cleaned_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped and (not stripped.startswith('#')):
            cleaned_lines.append(line)
    return '\n'.join(cleaned_lines)

def parse_aes_key_file(aes_key_path: str) -> bytes:
    """
    解析 AES 密钥文件
    
    Args:
        aes_key_path: AES密钥JSON文件路径
        
    Returns:
        bytes: 密钥的字节数组
        
    Raises:
        Exception: 文件不存在、格式错误或密钥格式无效
    """
    if not os.path.exists(aes_key_path):
        raise Exception(f'AES key file not found: {aes_key_path}')
    with open(aes_key_path, 'r', encoding='utf-8') as f:
        content = f.read()
    content = _remove_comments(content)
    try:
        decoder = json.JSONDecoder()
        (jroot, idx) = decoder.raw_decode(content)
    except json.JSONDecodeError as e:
        try:
            jroot = json.loads(content)
        except json.JSONDecodeError:
            raise Exception(f'Invalid JSON in AES key file {aes_key_path}: {str(e)}')
    jroot = dict(jroot)
    if 'AES_KEY' not in jroot:
        raise Exception(f'AES_KEY field not found in file {aes_key_path}')
    aes_key_str = jroot['AES_KEY']
    if not isinstance(aes_key_str, str):
        raise Exception(f'AES_KEY must be a string in file {aes_key_path}')
    aes_key_str = re.sub('\\s+', '', aes_key_str)
    if len(aes_key_str) % 2 != 0:
        raise Exception(f'AES_KEY length must be even (each 2 chars = 1 byte), got {len(aes_key_str)} chars')
    if len(aes_key_str) > 131070:
        raise Exception('AES_KEY too long, max 65535 bytes (131070 hex chars)')
    try:
        aes_key_bytes = bytes.fromhex(aes_key_str)
    except ValueError as e:
        raise Exception(f'Invalid hex string in AES_KEY: {str(e)}')
    BKLog.i(f'Parsed AES key: {len(aes_key_bytes)} bytes')
    return aes_key_bytes

def parse_random_key_file(random_key_path: str) -> bytes:
    """
    解析 Random 密钥文件

    Args:
        random_key_path: Random密钥JSON文件路径

    Returns:
        bytes: 密钥的字节数组（ASCII字符串转换为bytes）

    Raises:
        Exception: 文件不存在、格式错误或密钥格式无效
    """
    if not os.path.exists(random_key_path):
        raise Exception(f'Random key file not found: {random_key_path}')
    with open(random_key_path, 'r', encoding='utf-8') as f:
        content = f.read()
    content = _remove_comments(content)
    try:
        decoder = json.JSONDecoder()
        (jroot, idx) = decoder.raw_decode(content)
    except json.JSONDecodeError as e:
        try:
            jroot = json.loads(content)
        except json.JSONDecodeError:
            raise Exception(f'Invalid JSON in Random key file {random_key_path}: {str(e)}')
    jroot = dict(jroot)
    if 'RANDOM_KEY' not in jroot:
        raise Exception(f'RANDOM_KEY field not found in file {random_key_path}')
    random_key_array = jroot['RANDOM_KEY']
    if not isinstance(random_key_array, list):
        raise Exception(f'RANDOM_KEY must be an array in file {random_key_path}')
    random_key_str = ''.join((str(item) for item in random_key_array))
    if len(random_key_str) > 65535:
        raise Exception(f'RANDOM_KEY too long after concatenation, max 65535 bytes, got {len(random_key_str)}')
    random_key_bytes = random_key_str.encode('ascii')
    BKLog.i(f'Parsed Random key: {len(random_key_bytes)} bytes (from {len(random_key_array)} parts)')
    return random_key_bytes

class InjectKey(ActionBase):
    """密钥注入服务类（日志方式与 Download 一致：通过 debug 参数，在任务内 _init_log_level(port, debug)）"""
    INJECT_KEY_BAUDRATE = 115200

    def __init__(self, port='/dev/ttyUSB0', debug='3') -> None:
        super().__init__(port, baudrate=115200)
        self.debug = debug
        self.task_list = []
        self.task_index = -1

    def task_flag(self, start: bool):
        """标记任务开始或结束"""
        if start:
            self.task_index += 1
        if self.task_index < len(self.task_list):
            task = self.task_list[self.task_index]
            task.task_start = start
            ui_bridge.task_flag(task)

    def append_task(self, task_name: str):
        task_info = TaskInfo(task_name=task_name, task_id=len(self.task_list))
        self.task_list.append(task_info)

    def combine_inject_key_task_list(self, have_aes: bool=True, have_random: bool=True):
        """构建注入密钥的任务列表（根据是否有对应 key 决定是否加入写 key 任务）"""
        self.append_task('Parse key files')
        self.append_task('Start inject key mode')
        self.append_task('Handshake')
        self.append_task('Set Secure Boot')
        if have_aes:
            self.append_task('Write AES key')
        if have_random:
            self.append_task('Write Random key')
        self.append_task('Finish handshake')
        ui_bridge.task_list(self.task_list)

    def _start_inject_key_mode(self) -> bool:
        """
        启动 Inject Key 模式
        发送 ASCII 命令: "insert_key_start\r
"
        等待 1 秒
        """
        try:
            BKLog.i('Starting inject key mode...')
            start_protocol = InjectKeyStartProtocol()
            start_cmd = start_protocol.cmd()
            self.ser.write_cmd(start_cmd)
            time.sleep(1.0)
            BKLog.i('Inject key mode started')
            return True
        except Exception as e:
            BKLog.e(f'Start inject key mode failed: {str(e)}')
            return False

    def _handshake(self, max_retry: int=20) -> bool:
        """
        握手协议
        命令: 0x01 0xE0 0xFC 0x01 0x00
        响应: 0x04 0x0E 0x05 0x01 0xE0 0xFC 0x01 0x00
        """
        BKLog.i('Handshaking...')
        handshake_protocol = InjectKeyHandshakeProtocol()
        cmd = handshake_protocol.cmd()
        expected_length = handshake_protocol.expect_length
        for retry in range(max_retry):
            (success, response) = self.ser.write_cmd_and_wait_response(cmd, expected_length, timeout_sec=1.0)
            if success and response:
                (valid, _) = handshake_protocol.response_check(response)
                if valid:
                    BKLog.i('Handshake successful')
                    return True
            BKLog.w(f'Handshake failed (retry {retry + 1}/{max_retry})')
            if retry < max_retry - 1:
                time.sleep(0.1)
        BKLog.e('Handshake failed after all retries')
        return False

    def _set_secure_boot(self, enable: bool=True) -> bool:
        """
        设置 Secure Boot 标志
        下发: 0x01 0xE0 0xFC 0x02 0x29 [0x01/0x00]  （0x01=enable, 0x00=disable）
        回复: 0x04 0x0E 0x05 0x01 0xE0 0xFC 0x29 [0x01/0x00]  （8 字节；格式正确即视为成功，不判最后一字节）
        """
        BKLog.i(f"Setting Secure Boot: {('enable' if enable else 'disable')}")
        set_secure_boot_protocol = InjectKeySetSecureBootProtocol()
        cmd = set_secure_boot_protocol.cmd(enable)
        expected_length = set_secure_boot_protocol.expect_length
        (success, response) = self.ser.write_cmd_and_wait_response(cmd, expected_length, timeout_sec=1.0)
        if success and response:
            (valid, _) = set_secure_boot_protocol.response_check(response)
            if valid:
                BKLog.i('Set Secure Boot successful')
                return True
            status_code = set_secure_boot_protocol.get_response_status_code(response, is_long_cmd=False)
            resp_hex = ' '.join((f'{b:02x}' for b in response))
            BKLog.e(f'Set Secure Boot failed: response_check failed. response_hex={resp_hex}, status_code=0x{status_code or 0:02x}, len={len(response)}')
        else:
            resp_hex = ' '.join((f'{b:02x}' for b in response or b''))
            BKLog.e(f'Set Secure Boot failed: no valid response. response_hex={resp_hex}, success={success}, expected_len={expected_length}')
        return False

    def _write_aes_key(self, aes_key_bytes: bytes, max_retry: int=5) -> bool:
        """
        写入 AES 密钥
        命令: 长命令格式，命令码 0x26
        """
        BKLog.i(f'Writing AES key ({len(aes_key_bytes)} bytes)...')
        write_aes_key_protocol = InjectKeyWriteAesKeyProtocol()
        cmd = write_aes_key_protocol.cmd(aes_key_bytes)
        expected_length = write_aes_key_protocol.expect_length(len(aes_key_bytes))
        for retry in range(max_retry):
            (success, response) = self.ser.write_cmd_and_wait_response(cmd, expected_length, timeout_sec=2.0)
            if success and response:
                (valid, _) = write_aes_key_protocol.response_check(response, aes_key_bytes)
                if valid:
                    BKLog.i('Write AES key successful')
                    return True
                BKLog.w(f'AES key response check failed (retry {retry + 1}/{max_retry})')
            else:
                BKLog.w(f'Write AES key failed (retry {retry + 1}/{max_retry})')
            if retry < max_retry - 1:
                time.sleep(0.1)
        BKLog.e('Write AES key failed after all retries')
        return False

    def _write_random_key(self, random_key_bytes: bytes, max_retry: int=5) -> bool:
        """
        写入 Random 密钥
        命令: 长命令格式，命令码 0x27
        """
        BKLog.i(f'Writing Random key ({len(random_key_bytes)} bytes)...')
        write_random_key_protocol = InjectKeyWriteRandomKeyProtocol()
        cmd = write_random_key_protocol.cmd(random_key_bytes)
        expected_length = write_random_key_protocol.expect_length(len(random_key_bytes))
        for retry in range(max_retry):
            (success, response) = self.ser.write_cmd_and_wait_response(cmd, expected_length, timeout_sec=2.0)
            if success and response:
                (valid, echo_data) = write_random_key_protocol.response_check(response, random_key_bytes)
                if valid:
                    BKLog.i('Write Random key successful (echo verified)')
                    return True
                BKLog.w(f'Random key echo verification failed (retry {retry + 1}/{max_retry})')
                if echo_data:
                    BKLog.d(f'Expected: {random_key_bytes.hex()}')
                    BKLog.d(f'Got:      {echo_data.hex()}')
            else:
                BKLog.w(f'Write Random key failed (retry {retry + 1}/{max_retry})')
            if retry < max_retry - 1:
                time.sleep(0.1)
        BKLog.e('Write Random key failed after all retries')
        return False

    def _finish_handshake(self) -> bool:
        """
        完成握手
        命令: 0x01 0xE0 0xFC 0x01 0x28
        响应: 0x04 0x0E 0x04 0x01 0xE0 0xFC 0x28
        """
        BKLog.i('Finishing handshake...')
        finish_handshake_protocol = InjectKeyFinishHandshakeProtocol()
        cmd = finish_handshake_protocol.cmd()
        expected_length = finish_handshake_protocol.expect_length
        (success, response) = self.ser.write_cmd_and_wait_response(cmd, expected_length, timeout_sec=1.0)
        if success and response:
            (valid, _) = finish_handshake_protocol.response_check(response)
            if valid:
                BKLog.i('Finish handshake successful')
                return True
        BKLog.e('Finish handshake failed')
        return False

    def inject_key_task(self, aes_key_path: Optional[str]=None, random_key_path: Optional[str]=None):
        """
        执行密钥注入任务。
        根据参数处理：参数中携带了则解析并注入，未携带则不做任何处理；两个 key 至少携带一个即可。
        日志与 Download 一致：使用 self.debug，按串口 _init_log_level(port, debug)。

        Args:
            aes_key_path: AES密钥JSON文件路径，可选
            random_key_path: Random密钥JSON文件路径，可选

        Returns:
            bool: 成功返回True，失败返回False
        """
        result = False
        start_time = time.time()
        have_aes = bool(aes_key_path and aes_key_path.strip())
        have_random = bool(random_key_path and random_key_path.strip())
        if not have_aes and (not have_random):
            BKLog.e('At least one of aes_key_path or random_key_path must be provided')
            ui_bridge.end_flag('inject_key_task', False)
            return False
        BKLog.i('================================================================================')
        BKLog.i('Inject Key Task Started')
        BKLog.i('================================================================================')
        port_name = getattr(self.ser.ser, 'name', None) or getattr(self.ser.ser, 'port', str(self.ser.ser))
        self._init_log_level(port_name, self.debug)
        try:
            try:
                self.combine_inject_key_task_list(have_aes=have_aes, have_random=have_random)
                BKLog.i(f'Setting baudrate to {self.INJECT_KEY_BAUDRATE}...')
                if self.ser.baudrate != self.INJECT_KEY_BAUDRATE:
                    self.ser.switch_baudrate(self.INJECT_KEY_BAUDRATE)
                BKLog.i(f'Baudrate set to {self.INJECT_KEY_BAUDRATE}')
                self.task_flag(True)
                BKLog.i('Parsing key files...')
                aes_key_bytes = None
                random_key_bytes = None
                if have_aes:
                    aes_key_bytes = parse_aes_key_file(aes_key_path)
                    BKLog.i(f'AES key: {len(aes_key_bytes)} bytes')
                if have_random:
                    random_key_bytes = parse_random_key_file(random_key_path)
                    BKLog.i(f'Random key: {len(random_key_bytes)} bytes')
                self.task_flag(False)
                self.task_flag(True)
                if not self._start_inject_key_mode():
                    raise Exception('Start inject key mode failed')
                self.task_flag(False)
                self.task_flag(True)
                if not self._handshake(max_retry=20):
                    raise Exception('Handshake failed')
                self.task_flag(False)
                self.task_flag(True)
                if not self._set_secure_boot(enable=True):
                    raise Exception('Set Secure Boot failed')
                self.task_flag(False)
                aes_ok = True
                if have_aes:
                    self.task_flag(True)
                    aes_ok = self._write_aes_key(aes_key_bytes, max_retry=5)
                    self.task_flag(False)
                random_ok = True
                if have_random:
                    self.task_flag(True)
                    random_ok = self._write_random_key(random_key_bytes, max_retry=5)
                    self.task_flag(False)
                result = aes_ok and random_ok
                if result:
                    BKLog.w('================================================================================')
                    BKLog.w('Inject Key Task Completed Successfully')
                    BKLog.w('================================================================================')
                else:
                    BKLog.e('Inject key write failed (AES or Random)')
                self.task_flag(True)
                if not self._finish_handshake():
                    BKLog.w('Finish handshake failed (key write result already determined)')
                self.task_flag(False)
            except Exception as e:
                result = False
                BKLog.e('================================================================================')
                BKLog.e(f'Inject Key Task Failed: {str(e)}')
                BKLog.e('================================================================================')
        finally:
            end_time = time.time()
            elapsed_time = end_time - start_time
            BKLog.i(f'Elapse time: {elapsed_time:.6f} seconds')
            self.ser.disconnect()
            ui_bridge.end_flag('inject_key_task', result)
        return result
