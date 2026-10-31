import time
import os
from .action_base import ActionBase
from ..chip_controller import BaseController
from ..chip_controller import get_chip_set_with_chip_id
from ..bk_log import BKLog
from ..common.common import SecureDebugInfo
from ..protocol.bootrom import v2_0 as V2_0_BOOTROM_PROTOCOL
from ..secure_debug.secure_debug import SD


class SecDebug(ActionBase):
    def __init__(self, port='/dev/ttyUSB0', baudrate=115200, link_check_type=None, reset_type=None, reset_baudrate=115200, getbus_times=100, reboot_after_donwload=True, recnt=5, chipid=None, debug='3', link_key=None) -> None:
        super().__init__(port, baudrate)
        self.link_check_type = link_check_type
        self.reset_type = reset_type
        self.reset_baudrate = reset_baudrate
        self.reboot_after_donwload = reboot_after_donwload
        self.getbus_times = getbus_times
        self.retry = recnt
        self.chip_id = chipid
        self.debug = debug
        self.link_key = link_key

    def enter_secure_debug(self, pubkey: bytes):
        entersec = V2_0_BOOTROM_PROTOCOL.ChipEnterSecureDebugProtocol()
        tmp_res, content = self.ser.write_cmd_and_wait_response(entersec.cmd(pubkey), entersec.expect_length(), 1.0)
        if tmp_res and entersec.response_check(content):
            return entersec.get_rdm_data(content)

    def request_secure_debug(self, mode, sign_data: bytes):
        requestsec = V2_0_BOOTROM_PROTOCOL.ChipRequestSecureDebugProtocol()
        self.ser.write_cmd(requestsec.cmd(mode, sign_data))

    def get_pubkey_secure_debug(self, filepath):
        sd = SD(filepath)
        return sd.gen_sd_pk()

    def get_random_data_secure_debug(self):
        return os.urandom(32)

    def sign_hash(self, pubkey_path, privkey_path, data):
        sd = SD(pubkey_path, privkey_path)
        return sd.sign_hash_bootrom(data)

    def verify_hash(self, pubkey_path, data, sign):
        sd = SD(pubkey_path)
        return sd.verify_hash(pubkey_path, data, sign)

    def secure_debug_task(self, secdbginfo: SecureDebugInfo):
        result = False
        start_time = time.time()
        base_controller = BaseController(serial_instance=self.ser)
        self._init_log_level(self.ser.ser.name, self.debug)
        try:
            tmp_res, linktype = base_controller.get_bus(reset_type=self.reset_type, linkcheck_obj=None, reset_baudrate=self.reset_baudrate, max_try_count=self.getbus_times, link_key=self.link_key)
            if not tmp_res:
                raise Exception('get bus fail.')
            sec_id = 0
            time.sleep(0.1)
            if self.chip_id is None:
                self.chip_id = base_controller.get_chip_id_retry(self.retry)
                if self.chip_id is None:
                    raise Exception('get chip id fail.')
                if self.chip_id == 29238 or self.chip_id >> 16 == 29238:
                    sec_id = base_controller.get_second_chip_id()
                    if sec_id is None:
                        raise Exception('get sec chip id fail.')
            BKLog.w('chip id is 0x{:x}'.format(self.chip_id))
            chip_set = get_chip_set_with_chip_id(self.chip_id, sec_id)
            if chip_set is None:
                raise Exception('get chip set fail.')
            chip_set.update_serial_instance(self.ser)
            BKLog.i('set baudrate to {0}...'.format(secdbginfo.work_baudrate))
            if not chip_set.set_baudrate(baudrate=secdbginfo.work_baudrate, delay_ms=20):
                raise Exception('set baudrate {0} fail.'.format(secdbginfo.work_baudrate))
            pubkey_data, pubkey_path, privkey_path = self.get_pubkey_secure_debug(secdbginfo.key_path)
            BKLog.d(f'pubkey_len = {len(pubkey_data)}')
            BKLog.d(' '.join(f'{byte:02x}' for byte in pubkey_data))
            BKLog.d(' +++++++++++ ')
            for _ in range(15):
                ret, rdm_data = self.enter_secure_debug(pubkey_data)
                if ret and rdm_data and len(rdm_data) == 32:
                    BKLog.d(' enter success +++++++++ ')
                    break
            else:
                BKLog.d(' ------ 1111 ----- ')
                return
            BKLog.d(' ------ rdm_data : ----- ')
            BKLog.d(' '.join(f'{byte:02x}' for byte in rdm_data))
            usr_cmd = 0
            dat = usr_cmd.to_bytes(1, 'big') + rdm_data
            sign_len, sign_dat, r_s_dat = self.sign_hash(pubkey_path, privkey_path, dat)
            BKLog.d('\n')
            BKLog.d(f'sign_len = {sign_len}')
            BKLog.d(' '.join(f'{data:02x}' for data in r_s_dat))
            BKLog.d('\n')
            aaa = self.verify_hash(pubkey_path, dat, sign_dat)
            dat = usr_cmd.to_bytes(1, 'big') + sign_len.to_bytes(1, 'big') + r_s_dat
            BKLog.d(f' ------ usr_cmd ,len: {len(dat)}----- ')
            BKLog.d(' '.join(f'{data:02x}' for data in dat))
            self.request_secure_debug(usr_cmd, dat)
            BKLog.d('\n OK \n')
            result = True
        except Exception as e:
            result = False
            BKLog.e(str(e))
        finally:
            if self.reboot_after_donwload:
                BKLog.i('do reboot from bootrom.')
                base_controller.do_reboot()
            self.ser.disconnect()
            end_time = time.time()
            elapsed_time = end_time - start_time
            if result:
                BKLog.w('Test complete, all pass.')
                BKLog.w('done.')
            else:
                BKLog.e('Test fail.')
            BKLog.i(f'Elapse time: {elapsed_time:.6f} seconds.\n')
            return result
