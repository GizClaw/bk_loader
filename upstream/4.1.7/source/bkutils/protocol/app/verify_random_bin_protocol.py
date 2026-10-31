"""
校验 Random Bin（短命令，命令码 0x30）

下发: 0x01 0xE0 0xFC [长度] 0x30 [payload...]  （长度 = 1 + len(payload)，例如 payload 192 字节时为 0xC1）
回复: 0x04 0x0E 0x05 0x01 0xE0 0xFC 0x30 [ret]  （共 8 字节；ret==0 表示校验通过）
"""
from enum import IntEnum
from ...bk_log import BKLog
from .base_app_protocol import BaseAppProtocol

class VerifyRandomBinResult(IntEnum):
    """与固件 verify_random_bin_result_t 一致。"""
    OK = 0
    STATE_ERROR = 1
    PARAM_ERROR = 2
    PUBKEY_ERROR = 3
    GROUP_ERROR = 4
    POINT_ERROR = 5
    HASH_ERROR = 6
    SIG_R_ERROR = 7
    SIG_S_ERROR = 8
    SIGN_ERROR = 9
_RX_LEN = 8
_RX_LEN_FIELD = 5
_CMD = 48
_RX_PREFIX = bytes([4, 14, _RX_LEN_FIELD, 1, 224, 252, _CMD])

def _warn_if_ret_error(ret: int) -> None:
    if ret == 0:
        return
    try:
        msg = VerifyRandomBinResult(ret).name
    except ValueError:
        msg = 'unknown'
    BKLog.w('Check status error: err_code: {0}  err_msg: {1}'.format(ret, msg))

class VerifyRandomBinProtocol(BaseAppProtocol):
    """Random Bin 校验协议（短命令）。"""
    CMD_CODE = _CMD

    def cmd(self, payload: bytes=b''):
        """生成校验命令。

        Args:
            payload: 下发数据（长度受短帧单字节长度域限制；业务上与 RANDOM_BIN_MAX_BYTES=192 对齐）。
        """
        return self.command_generate(self.CMD_CODE, list(payload))

    @property
    def expect_length(self):
        """期望响应长度（固定 8 字节）。"""
        return self.rx_expect_length(1)

    def response_check(self, response_content: bytes):
        """校验 HCI 帧格式，并解析 ret。

        Args:
            response_content: 原始响应

        Returns:
            tuple: (帧合法, ret)。帧不合法时为 (False, None)；合法时为 (True, ret)，ret==0 表示 VERIFY_RANDOM_BIN_OK。
        """
        if len(response_content) < _RX_LEN or response_content[:7] != _RX_PREFIX:
            return (False, None)
        ret = response_content[7]
        _warn_if_ret_error(ret)
        return (True, ret)
