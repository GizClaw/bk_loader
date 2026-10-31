# Decompiled with PyLingual (https://pylingual.io)
# Internal filename: 'bkutils/common/random_bin_verify.py'
# Bytecode version: 3.9.0beta5 (3425)
# Source timestamp: 1970-01-01 00:00:00 UTC (0)

"""random.bin 校验：总闸为 YAML 顶层 enable_random_bin_verify；BL2 时要求设备校验通过。"""
import os
import time
from typing import Optional
from bkutils.bk_log.log_utils import BKLog
from bkutils.common.bk_out_config import BkDownloadFlowConfig
from bkutils.common.common import LINKCHECK
from bkutils.protocol.app.verify_random_bin_protocol import VerifyRandomBinProtocol, VerifyRandomBinResult
RANDOM_BIN_MAX_BYTES = 192
def _effective_random_bin_path(random_bin_path: Optional[str]) -> Optional[str]:
    """None / 纯空白视为未传路径；否则返回 strip 后的字符串。"""
    if random_bin_path is None:
        return
    else:
        s = random_bin_path.strip()
        if s:
            return s
def maybe_verify_random_bin_after_get_bus(ser, linktype, random_bin_path: Optional[str]) -> None:
    """握手成功后调用：非 BL2 跳过；BL2 须带有效路径；发送 0x30 直至 ret==0。\n\n    判断顺序（短路）：① enable_random_bin_verify 为 false → 返回；\n    ② 若非 BL2 → 返回；③ BL2 且路径未传或为空 → 报错（与「文件不存在」区分）；\n    ④ 路径已传但文件不存在 → 日志与异常中打印绝对路径；⑤ 可读且长度合法后下发并校验 ret。\n    """
    if not BkDownloadFlowConfig.cli_enable_random_bin_verify:
        return
    else:
        if linktype != LINKCHECK.BL2:
            return
        else:
            eff = _effective_random_bin_path(random_bin_path)
            if eff is None:
                raise Exception('random.bin verify: BL2 requires --random_bin_path (parameter not passed or empty).')
            else:
                if not os.path.isfile(eff):
                    abs_path = os.path.abspath(eff)
                    BKLog.e(f'random.bin verify: file not found, path={abs_path}')
                    raise Exception(f'random.bin verify: random.bin file not found at path: {abs_path}')
                else:
                    with open(eff, 'rb') as f:
                        data = f.read()
                if len(data) > RANDOM_BIN_MAX_BYTES:
                    raise Exception(f'random.bin exceeds {RANDOM_BIN_MAX_BYTES} bytes (got {len(data)})')
                else:
                    time.sleep(0.1)
                    proto = VerifyRandomBinProtocol()
                    cmd = proto.cmd(data)
                    max_attempts = 5
                    retry_delay_sec = 0.1
                    last_error = ''
                    for attempt in range(max_attempts):
                        if attempt > 0:
                            time.sleep(retry_delay_sec)
                        ok, resp = ser.write_cmd_and_wait_response(cmd, proto.expect_length, timeout_sec=2.0)
                        if not ok or not resp:
                            last_error = 'random.bin verify: no valid response from device'
                            BKLog.w(f'{last_error} (attempt {attempt + 1}/{max_attempts})')
                            continue
                        else:
                            valid, ret = proto.response_check(resp)
                            if not valid:
                                last_error = 'random.bin verify: invalid response frame'
                                BKLog.w(f'{last_error} (attempt {attempt + 1}/{max_attempts})')
                                continue
                            else:
                                if ret != VerifyRandomBinResult.OK:
                                    last_error = f'random.bin verify failed: ret={int(ret)}'
                                    BKLog.w(f'{last_error} (attempt {attempt + 1}/{max_attempts})')
                                else:
                                    BKLog.i('random.bin verify OK')
                                    return
                    raise Exception(f'{last_error} (after {max_attempts} attempts)')