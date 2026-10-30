"""Runtime tuning configuration recovered from the packaged loader."""

import os

import yaml

from ..bk_log.log_utils import BKLog


class BkOutConfig:
    check_response_code = True
    chip_name = ''

    @staticmethod
    def set_bk_loader_config_path_out(path):
        try:
            BkOutConfig(path)
        except Exception as error:
            BKLog.e(f'set bk loader config path failed, error: {error}')

    def __init__(self, outer_path=None):
        inner_path = self.get_config_file_path()
        if outer_path and os.path.isfile(outer_path):
            path = outer_path
        elif os.path.isfile(inner_path):
            path = inner_path
        else:
            return

        BKLog.i(f'load config file: {path}')
        with open(path, 'r', encoding='utf-8') as stream:
            self.cfg_info = yaml.safe_load(stream)
        if not self.cfg_info.get('enable', False):
            return

        BkOutConfig.chip_name = self.cfg_info.get('chip_name', BkOutConfig.chip_name)
        BkOutConfig.check_response_code = self.cfg_info.get(
            'check_response_code', BkOutConfig.check_response_code
        )
        sections = (
            ('linkcheck', BklinkcheckConfig),
            ('read_flash', BkReadFlashConfig),
            ('set_baudrate', BkSetBaudrateConfig),
            ('download_flow', BkDownloadFlowConfig),
            ('erase_flow', BkEraseFlowConfig),
            ('otp_config', BKOTPConfig),
        )
        for name, config_type in sections:
            values = self.cfg_info.get(name, {})
            if values:
                config_type(values)

    @staticmethod
    def get_config_file_path():
        return os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'config',
            'bk_loader_config_inner.yaml',
        )


class BkSetBaudrateConfig:
    cmd_delay_ms = 90
    switch_delay_ms = 50
    wait_response_timeout_ms = 200

    def __init__(self, values):
        for name in ('cmd_delay_ms', 'switch_delay_ms', 'wait_response_timeout_ms'):
            setattr(type(self), name, values.get(name, getattr(type(self), name)))


class BkReadFlashConfig:
    retry_count = 10
    fixed_timeout_ms = 1000
    delay_after_fail_ms = 100
    timeout_factor = 2

    def __init__(self, values):
        for name in ('retry_count', 'fixed_timeout_ms', 'delay_after_fail_ms', 'timeout_factor'):
            setattr(type(self), name, values.get(name, getattr(type(self), name)))


class BklinkcheckConfig:
    use_version = 2

    def __init__(self, values):
        type(self).use_version = values.get('use_version', 2)
        if self.use_version == 2 and values.get('version_2'):
            BklinkcheckConfigV2(values['version_2'])
        elif self.use_version == 3 and values.get('version_3'):
            BklinkcheckConfigV3(values['version_3'])


class BklinkcheckConfigV2:
    max_recycle_count = 2
    max_retry_interval = 80
    max_wait_time = 10
    use_mixed_detection = True

    def __init__(self, values):
        for name in ('max_recycle_count', 'max_retry_interval', 'max_wait_time', 'use_mixed_detection'):
            setattr(type(self), name, values.get(name, getattr(type(self), name)))


class BklinkcheckConfigV3:
    max_recycle_count = 30
    max_retry_interval = 200
    line_break_timeout_ms = 1
    delay_time_before_reboot = 10
    delay_time_after_reboot = 5
    use_mixed_detection = True

    def __init__(self, values):
        for name in (
            'max_recycle_count', 'max_retry_interval', 'line_break_timeout_ms',
            'delay_time_before_reboot', 'delay_time_after_reboot', 'use_mixed_detection',
        ):
            setattr(type(self), name, values.get(name, getattr(type(self), name)))


class BkDownloadFlowConfig:
    check_bin_board_crc_sync = True
    verify_product_id = True
    allow_change_linkcheck_obj = False

    def __init__(self, values):
        for name in ('check_bin_board_crc_sync', 'verify_product_id', 'allow_change_linkcheck_obj'):
            setattr(type(self), name, values.get(name, getattr(type(self), name)))


class BkEraseFlowConfig:
    allow_change_linkcheck_obj = True

    def __init__(self, values):
        type(self).allow_change_linkcheck_obj = values.get(
            'allow_change_linkcheck_obj', type(self).allow_change_linkcheck_obj
        )


class BKOTPConfig:
    must_use_bl1 = False

    def __init__(self, values):
        type(self).must_use_bl1 = values.get('must_use_bl1', type(self).must_use_bl1)
