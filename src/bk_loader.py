# bk_loader
#
# Copyright (c) BekenCorp. All rights reserved.
#
# This software may be distributed under the terms of the BSD license.
# See README for more details.
import json
import sys
import os
import threading
from bkutils.common import ui_bridge
from bkutils.action_service.secure import SecDebug
sys.path.append(os.path.dirname(__file__))
import click
from bkutils.bk_log.log_utils import *
from bkutils.common.common import BIN_TYPE, RESET_TYPE, LINKCHECK, AuthorizeInfo, DownloadInfo, ReadInfo, EraseInfo, BinInfo, SecureDebugInfo, parse_binfile_info, parse_binfile_info_json, parse_device_name_info, parse_device_mac_info, parse_erase_info, parse_dump_info, available_serial_ports, crc32_ver2, crc32bytes, parse_safe_json_file, parse_expand_data, parse_expand_data_batch, ExtraData
from bkutils.common.version import *
from bkutils.action_service.download import Download
from bkutils.action_service.erase import Erase
from bkutils.action_service.dump import Dump
from bkutils.action_service.authorize import Authorize
from bkutils.action_service.inject_key import InjectKey
from bkutils.action_service.batch_download import BatchDownload
from bkutils.chip_controller.base_controller import BaseController
from bkutils.chip_controller.serial_helper import SerialHelper
from bkutils.common.ui_bridge import MonitorStdin, reset_factory_stop
from bkutils.common import bk_global
from bkutils.common.bk_global import BkInitiator
from bkutils.common.common import INITIATOR
from bkutils.common import bk_out_config
CLI_LINK_TYPE_CHOICE = ('0', '1', '2', '3', '4', '5')
CLI_LINK_TYPE_HELP = 'LINKCHECK: 0=BOOTROM, 1=BL2, 2=BOOTROM_PRE, 3=BOOTROM_EXT, 4=MIXED, 5=OTHER; default 4. --link_key forces BOOTROM_EXT'

def _parse_cli_link_type(s):
    m = {'0': LINKCHECK.BOOTROM, '1': LINKCHECK.BL2, '2': LINKCHECK.BOOTROM_PRE, '3': LINKCHECK.BOOTROM_EXT, '4': LINKCHECK.MIXED, '5': LINKCHECK.OTHER}
    return m.get(s, LINKCHECK.MIXED)
BATCH_DOWNLOAD_INFILE_REQUIRED_ERROR = 'Argument error, need input bin file such as [-i firmware.bin]'
DOWNLOAD_WRITE_TARGET_REQUIRED_ERROR = 'Argument error, need at least one write target such as -i, --safe_json, --expand_data, --mac, --dev_name, --otp or --efuse'

def _has_cli_value(value):
    return value is not None and str(value).strip() != ''

def _parse_required_binfile_info(infile, startaddr, error_message):
    if not _has_cli_value(infile):
        raise Exception(error_message)
    (bin_type, binlist, bin_path) = parse_binfile_info(infile.strip(), startaddr)
    if not binlist:
        raise Exception(error_message)
    return (bin_type, binlist, bin_path)

def _parse_required_binfile_input(infile, infile_json, startaddr, error_message):
    if _has_cli_value(infile_json):
        (bin_type, binlist, bin_path) = parse_binfile_info_json(infile_json, startaddr)
        if not binlist:
            raise Exception(error_message)
        return (bin_type, binlist, bin_path)
    return _parse_required_binfile_info(infile, startaddr, error_message)

@click.group()
@click.version_option(version=get_tool_version())
@click.option('--initiator', type=click.Choice(['0', '1']), default='0', help='0 cli 1 flutter ui')
@click.option('--log_level', type=click.Choice(['-1', '0', '1', '2', '3', '999']), default=None, help='Set log level: -1=ignore this 0=nothing, 1=error message, 2=warning message, 3=info in test process + file, 999=full debug message + file')
@click.option('--log_path', type=click.Path(), default=None, help='Input log path.')
@click.option('--flash_config_path_out', type=click.Path(), default=None, help='Input flash config path.')
@click.option('--sensitive_information', is_flag=True, default=False, help='print sensitive information')
@click.option('--bk_loader_config_path_out', type=click.Path(), default=None, help='Input bk loader config path.')
@click.option('--bin_parser_path', type=str, help='cutomer bin parser path')
def cli(initiator, log_level, log_path, flash_config_path_out, sensitive_information, bk_loader_config_path_out, bin_parser_path):
    """Beken flash tools - bk_flash"""
    bk_global.BkInitiator.set_initiator(INITIATOR.CLI if initiator == '0' else INITIATOR.FLUTTER_UI)
    bk_global.BkGlobalLogConfig.set_log_level(log_level)
    bk_global.BkGlobalLogConfig.set_log_folder_path(log_path)
    bk_global.BkGlobalLogConfig.enable_print_sensitive_information(sensitive_information)
    bk_global.BkFlashConfigOut.set_flash_config_path_out(flash_config_path_out)
    bk_out_config.BkOutConfig.set_bk_loader_config_path_out(bk_loader_config_path_out)
    bk_out_config.CustomerVersionConfig()
    bk_out_config.BinParserConfig(bin_parser_path)
    MonitorStdin().start()

@cli.command()
@click.option('-p', '--portnum', default='/dev/ttyUSB0', required=True, help="UART device, such as default '/dev/ttyUSB0'")
@click.option('-b', '--baudrate', default=2000000, type=int, help='Burn UART baudrate, defaults to 2000000')
@click.option('-r', '--reboot', is_flag=True, default=False, help='Reboot after download process')
@click.option('--link_type', type=click.Choice(CLI_LINK_TYPE_CHOICE), default='4', help=CLI_LINK_TYPE_HELP)
@click.option('--reset_type', type=click.Choice(['0', '1', '2', '3']), default='3', help="reset type,0=dtr/rts,1=command 'reboot',2=command '95 27',3=multi reset dtr/rts then cmd")
@click.option('--reset_baudrate', default=115200, type=int, help='app reset UART baudrate, defaults to 115200')
@click.option('-g', '--getbus_times', default=100, type=int, help='get bus times, default is 100 times')
@click.option('--retrycnt', default=5, type=int, help='Retry times')
@click.option('--chipid', type=str, help='default none will read from chipset,0x3000 for generic BT project, 0x3436 is a special one')
@click.option('-c', '--chip_all', is_flag=True, default=False, help='erase/read all chip')
@click.option('-e', '--pre_erase', type=click.Choice(['0', '1']), default='1', help='erase flash before write')
@click.option('-d', '--debug', type=click.Choice(['0', '1', '2', '3', '999']), default='3', help='Set debug level: 0=nothing, 1=error message, 2=warning message, 3=info in test process + file, 999=full debug message + file')
@click.option('--link_key', type=str, help='Set link key, such as : --link_key 000102030405060708090a0b0c0d0e0f')
@click.option('-i', '--infile', type=click.Path(), help='Input one for more existing binary files.')
@click.option('--infile_json', type=str, default=None, help='Input binary files as JSON, e.g. [{"path":"D:/fw/app.bin","start":"0x0","len":"0x1000"}].')
@click.option('--del_after', is_flag=True, default=False, help='delete bin file after read buffer')
@click.option('-s', '--startaddr', default='0x0', help='Burn flash start address, defaults to 0x0')
@click.option('--safe_json', type=click.Path(), help='Input safe json file path')
@click.option('--aes_key', type=str, help='Input aes key stream')
@click.option('--efuse', type=str, help='Write efuse as 1, address is efuse byte index, or write efuse u8 value, include: [address-val] or [1@address-bit], such as: --efuse 0x1-0x10,1@0x2-0x1')
@click.option('--otp', type=str, help='Write OTP,value must be hex format, include: [value@address-length], such as: --otp 73c7bf397f2ad6bf@0x4b100460-8,73c7bf397f2ad6bf@0x4b100460-8')
@click.option('--otp_pm', type=str, help='Set OTP permission,include: [pm@address-length], such as: --otp_pm ro@0x4b100460-32,ro@0x4b100460-32')
@click.option('--otp_reverse', is_flag=True, default=False, help='Write OTP such as AES key, set reverse content per 4 bytes')
@click.option('--otp_big_endian', is_flag=True, default=False, help='Write OTP such as AES key if the OTP data which is writting is big-endian')
@click.option('--dev_name', type=str, help='Set device name,include : [data@startAddress-length],such as : --dev_name beken@0x2e000-5')
@click.option('-m', '--mac', type=str, help='Set mac information,include : [data@startAddress-length],such as : --mac aabbccddeeff@0x1e000-6')
@click.option('--big_endian', is_flag=True, default=False, help='Write device ID(MAC),set big-endian')
@click.option('--flash_otp', type=str, help='Set flash OTP information,include : [data@startAddress-length],such as : --flash_otp aabbccddeeff@0x0001ff-6')
@click.option('--check_words', type=str, help='check key words after reboot from bootrom, [words@baudrate],such as --check_words OTA:SUCCESS@115200')
@click.option('--custom_data', type=str, help='Set custom data,include : [data@startAddress-length],such as : --custom_data aabbccddeeff@0x1e000-6')
@click.option('--expand_data', type=str, help='Set expand data')
@click.option('--cbus', is_flag=True, default=False, help='use cbus to download')
@click.option('--random_bin_path', type=str, default=None, help='Path to random.bin (max 192 bytes). 是否执行校验由 bk_loader_config 顶层 enable_random_bin_verify 决定。')
def download(portnum, baudrate, reboot, link_type, reset_type, reset_baudrate, getbus_times, retrycnt, chipid, chip_all, debug, infile, infile_json, startaddr, safe_json, aes_key, efuse, otp, otp_pm, dev_name, mac, big_endian, otp_reverse, otp_big_endian, flash_otp, del_after, pre_erase, check_words, custom_data, link_key, expand_data, cbus, random_bin_path):
    try:
        bin_type = None
        pathlist = []
        startaddr = int(startaddr, 16)
        if reset_type == '0':
            reset_type = RESET_TYPE.DTR_RTS
        elif reset_type == '1':
            reset_type = RESET_TYPE.CMD_ASCII
        elif reset_type == '2':
            reset_type = RESET_TYPE.CMD_HEX
        else:
            reset_type = RESET_TYPE.MULTI
        link_check = _parse_cli_link_type(link_type)
        if link_key:
            link_key = bytes.fromhex(link_key)
            link_check = LINKCHECK.BOOTROM_EXT
            print('link_type:ext')
        if chipid:
            chipid = int(chipid, 16)
        else:
            chipid = None
        downloadinfo = DownloadInfo()
        downloadinfo.work_baudrate = baudrate
        downloadinfo.bAllFlash = chip_all
        downloadinfo.aes_key = aes_key
        downloadinfo.efuse_info = efuse
        downloadinfo.otp_info = otp
        downloadinfo.otp_pm = otp_pm
        downloadinfo.bEnableBigEndian = big_endian
        downloadinfo.reverse_content = otp_reverse
        downloadinfo.otp_bigendian = otp_big_endian
        downloadinfo.pre_erase = int(pre_erase)
        downloadinfo.custom_data = custom_data
        downloadinfo.flash_otp = flash_otp
        if check_words:
            downloadinfo.check_words = check_words
        if dev_name:
            (ret, devname, addr, oplen) = parse_device_name_info(dev_name)
            if not ret:
                raise Exception('Input device name format error.')
            downloadinfo.bDownloadDeviceName = True
            downloadinfo.device_name = devname
            downloadinfo.device_name_Addr = addr
            downloadinfo.device_name_length = oplen
        if mac:
            (ret, devid, addr, oplen) = parse_device_mac_info(mac)
            if not ret:
                raise Exception('Input mac format error.')
            downloadinfo.bDownloadDeviceID = True
            downloadinfo.device_id = devid
            downloadinfo.device_id_Addr = addr
            downloadinfo.device_id_length = oplen
        if safe_json:
            downloadinfo.safeinfo = parse_safe_json_file(safe_json)
            downloadinfo.safeinfo.write_safe_config = True
        if _has_cli_value(infile) or _has_cli_value(infile_json):
            (bin_type, binlist, pathlist) = _parse_required_binfile_input(infile, infile_json, startaddr, 'Argument error, invalid input bin file')
            downloadinfo.bDownloadBin = True
            if bin_type is None:
                downloadinfo.mixedBinInfo = binlist
            else:
                downloadinfo.vecbinInfo = binlist[0].binList
        if del_after:
            if pathlist and len(pathlist) > 0:
                os.remove(pathlist[0])
            if downloadinfo.safeinfo.write_safe_config:
                os.remove(safe_json)
        if expand_data:
            downloadinfo.expand_data_list = parse_expand_data(expand_data)
        has_write_target = downloadinfo.bDownloadBin or downloadinfo.safeinfo.write_safe_config or len(downloadinfo.expand_data_list) > 0 or downloadinfo.bDownloadDeviceID or downloadinfo.bDownloadDeviceName or _has_cli_value(efuse) or _has_cli_value(otp) or _has_cli_value(otp_pm) or _has_cli_value(flash_otp)
        if not has_write_target:
            raise Exception(DOWNLOAD_WRITE_TARGET_REQUIRED_ERROR)

        def _dl_link(bin_type_default):
            """link_key 强制 BOOTROM_EXT；仅当 CLI 为 OTHER(5) 时按 bin 类型取默认，否则沿用 link_check。"""
            if link_key:
                return link_check
            if link_check == LINKCHECK.OTHER:
                return bin_type_default
            return link_check
        if cbus:
            downloader = Download(portnum, 115200, _dl_link(None), reset_type, reset_baudrate, getbus_times, reboot, retrycnt, chipid, debug, link_key, random_bin_path)
            downloader.download_flash_cbus_task(downloadinfo=downloadinfo)
        elif bin_type is None:
            if downloadinfo.bDownloadBin:
                downloader = Download(portnum, 115200, _dl_link(LINKCHECK.BOOTROM), reset_type, reset_baudrate, getbus_times, reboot, retrycnt, chipid, debug, link_key, random_bin_path)
                downloader.download_mixed_task(downloadinfo=downloadinfo)
            else:
                downloader = Download(portnum, 115200, _dl_link(None), reset_type, reset_baudrate, getbus_times, reboot, retrycnt, chipid, debug, link_key, random_bin_path)
                downloader.download_base_task(downloadinfo=downloadinfo)
        elif bin_type == BIN_TYPE.TYPE_SECURE_FIX:
            downloader = Download(portnum, 115200, _dl_link(LINKCHECK.BOOTROM), reset_type, reset_baudrate, getbus_times, reboot, retrycnt, chipid, debug, link_key, random_bin_path)
            downloader.download_secure_task(downloadinfo)
        elif bin_type == BIN_TYPE.TYPE_BL2_APP_BIN:
            downloader = Download(portnum, 115200, _dl_link(LINKCHECK.BL2), reset_type, reset_baudrate, getbus_times, reboot, retrycnt, chipid, debug, link_key, random_bin_path)
            downloader.download_base_task(downloadinfo=downloadinfo)
        elif bin_type == BIN_TYPE.TYPE_BL1_ALL_BIN or bin_type == BIN_TYPE.TYPE_OTA:
            downloader = Download(portnum, 115200, _dl_link(LINKCHECK.BOOTROM), reset_type, reset_baudrate, getbus_times, reboot, retrycnt, chipid, debug, link_key, random_bin_path)
            downloader.download_base_task(downloadinfo=downloadinfo)
        elif bin_type == BIN_TYPE.TYPE_OUTTER_FLASH:
            downloader = Download(portnum, 115200, _dl_link(LINKCHECK.BOOTROM), reset_type, reset_baudrate, getbus_times, reboot, retrycnt, chipid, debug, link_key, random_bin_path)
            downloader.download_with_outter_flash_task(downloadinfo=downloadinfo)
        elif bin_type == BIN_TYPE.TYPE_BL2_OTA:
            downloader = Download(portnum, 115200, _dl_link(LINKCHECK.BL2), reset_type, reset_baudrate, getbus_times, reboot, retrycnt, chipid, debug, link_key, random_bin_path)
            downloader.download_bootloader_ota(downloadinfo=downloadinfo)
        elif bin_type == BIN_TYPE.TYPE_NORMAL:
            downloader = Download(portnum, 115200, _dl_link(LINKCHECK.BOOTROM), reset_type, reset_baudrate, getbus_times, reboot, retrycnt, chipid, debug, link_key, random_bin_path)
            downloader.download_base_task(downloadinfo=downloadinfo)
        elif bin_type == BIN_TYPE.TYPE_SAM_UN:
            downloader = Download(portnum, 115200, _dl_link(LINKCHECK.BOOTROM), reset_type, reset_baudrate, getbus_times, reboot, retrycnt, chipid, debug, link_key, random_bin_path)
            downloader.download_base_task(downloadinfo=downloadinfo)
        elif bin_type == BIN_TYPE.TYPE_SAM_EN:
            downloader = Download(portnum, 115200, _dl_link(LINKCHECK.BL2), reset_type, reset_baudrate, getbus_times, reboot, retrycnt, chipid, debug, link_key, random_bin_path)
            downloader.download_base_task(downloadinfo=downloadinfo)
        elif bin_type == BIN_TYPE.TYPE_CUSTOM_UNSECURE:
            downloader = Download(portnum, 115200, _dl_link(LINKCHECK.BOOTROM), reset_type, reset_baudrate, getbus_times, reboot, retrycnt, chipid, debug, link_key, random_bin_path)
            downloader.download_base_task(downloadinfo=downloadinfo)
        elif bin_type == BIN_TYPE.TYPE_CUSTOM_SECURE:
            downloader = Download(portnum, 115200, _dl_link(LINKCHECK.BL2), reset_type, reset_baudrate, getbus_times, reboot, retrycnt, chipid, debug, link_key, random_bin_path)
            downloader.download_base_task(downloadinfo=downloadinfo)
        elif bin_type == BIN_TYPE.TYPE_BL1_SECUR_MODE:
            downloader = Download(portnum, 115200, _dl_link(LINKCHECK.BOOTROM), reset_type, reset_baudrate, getbus_times, reboot, retrycnt, chipid, debug, link_key, random_bin_path)
            downloader.download_limited_read_task(downloadinfo=downloadinfo)
        elif bin_type == BIN_TYPE.TYPE_BL1_SECURE_EXTENSION:
            downloader = Download(portnum, 115200, _dl_link(LINKCHECK.BOOTROM), reset_type, reset_baudrate, getbus_times, reboot, retrycnt, chipid, debug, link_key, random_bin_path)
            downloader.download_bl1_secure_extension_task(downloadinfo=downloadinfo)
        elif bin_type == BIN_TYPE.TYPE_BL1_SECURE_FIXED:
            downloader = Download(portnum, 115200, _dl_link(LINKCHECK.BOOTROM), reset_type, reset_baudrate, getbus_times, reboot, retrycnt, chipid, debug, link_key, random_bin_path)
            downloader.download_bl1_secure_fixed_task(downloadinfo=downloadinfo)
        else:
            raise Exception(f'Unsupported bin type: {bin_type}')
    except Exception as e:
        error_message = str(e)
        BKLog.e(error_message)
        ui_bridge.end_flag('', False)
        if BkInitiator.initiator_global != INITIATOR.FLUTTER_UI and error_message.startswith('Argument error'):
            raise click.ClickException(error_message)
        return None

@cli.command(name='batch_download')
@click.option('-p', '--portnum', required=True, help="Comma-separated UART devices, e.g., 'COM1,COM2,COM3' or '/dev/ttyUSB0,/dev/ttyUSB1'")
@click.option('-b', '--baudrate', default=2000000, type=int, help='Burn UART baudrate, defaults to 2000000')
@click.option('-r', '--reboot', is_flag=True, default=False, help='Reboot after download process')
@click.option('--link_type', type=click.Choice(CLI_LINK_TYPE_CHOICE), default='4', help=CLI_LINK_TYPE_HELP)
@click.option('--reset_type', type=click.Choice(['0', '1', '2', '3']), default='3', help="reset type,0=dtr/rts,1=command 'reboot',2=command '95 27',3=multi reset dtr/rts then cmd")
@click.option('--reset_baudrate', default=115200, type=int, help='app reset UART baudrate, defaults to 115200')
@click.option('-g', '--getbus_times', default=100, type=int, help='get bus times, default is 100 times')
@click.option('--retrycnt', default=5, type=int, help='Retry times')
@click.option('--chipname', type=str, help='Chip name, e.g. BK7259, BK7236N. If not set, chip type is read from device.')
@click.option('-e', '--erase', type=click.Choice(['none', 'all', 'bin']), default='bin', help='Erase mode: none=no erase, all=erase entire chip, bin=erase by bin regions (default)')
@click.option('-d', '--debug', type=click.Choice(['0', '1', '2', '3', '999']), default='3', help='Set debug level: 0=nothing, 1=error message, 2=warning message, 3=info in test process + file, 999=full debug message + file')
@click.option('--link_key', type=str, help='Set link key, such as : --link_key 000102030405060708090a0b0c0d0e0f')
@click.option('-i', '--infile', type=click.Path(), help='Input one for more existing binary files.')
@click.option('--infile_json', type=str, default=None, help='Input binary files as JSON, e.g. [{"path":"D:/fw/app.bin","start":"0x0","len":"0x1000"}].')
@click.option('--del_after', is_flag=True, default=False, help='delete bin file after read buffer')
@click.option('-s', '--startaddr', default='0x0', help='Burn flash start address, defaults to 0x0')
@click.option('--safe_json', type=click.Path(), help='Input safe json file path (recommended way to configure OTP, efuse, etc.)')
@click.option('--expand_data', type=str, help='Set expand data')
@click.option('--expand_data_batch', type=str, help='Expand data for batch: 4-part or 5-part (value@step) per item, comma-separated')
@click.option('--random_bin_path', type=str, default=None, help='Path to random.bin (max 192 bytes). 是否校验由 bk_loader_config 顶层 enable_random_bin_verify 决定。')
def batch_download(portnum, baudrate, reboot, link_type, reset_type, reset_baudrate, getbus_times, retrycnt, chipname, erase, debug, infile, infile_json, startaddr, safe_json, del_after, link_key, expand_data, expand_data_batch, random_bin_path):
    try:
        report_channel_progress = BkInitiator.initiator_global == INITIATOR.FLUTTER_UI
        if report_channel_progress:
            reset_factory_stop()
        portlist = [p.strip() for p in portnum.split(',') if p.strip()]
        if not portlist:
            raise Exception('No valid ports specified. Please provide at least one port.')
        bin_type = None
        pathlist = []
        startaddr = int(startaddr, 16)
        if reset_type == '0':
            reset_type = RESET_TYPE.DTR_RTS
        elif reset_type == '1':
            reset_type = RESET_TYPE.CMD_ASCII
        elif reset_type == '2':
            reset_type = RESET_TYPE.CMD_HEX
        else:
            reset_type = RESET_TYPE.MULTI
        link_check = _parse_cli_link_type(link_type)
        if link_key:
            link_key = bytes.fromhex(link_key)
            link_check = LINKCHECK.BOOTROM_EXT
            print('link_type:ext')
        if chipname:
            chipname = chipname.strip()
        else:
            chipname = None
        if erase == 'none':
            downloadinfo_pre_erase = 0
            downloadinfo_b_all_flash = False
        elif erase == 'all':
            downloadinfo_pre_erase = 1
            downloadinfo_b_all_flash = True
        else:
            downloadinfo_pre_erase = 1
            downloadinfo_b_all_flash = False
        downloadinfo = DownloadInfo()
        downloadinfo.work_baudrate = baudrate
        downloadinfo.bAllFlash = downloadinfo_b_all_flash
        downloadinfo.pre_erase = downloadinfo_pre_erase
        if safe_json:
            downloadinfo.safeinfo = parse_safe_json_file(safe_json)
            downloadinfo.safeinfo.write_safe_config = True
        (bin_type, binlist, pathlist) = _parse_required_binfile_input(infile, infile_json, startaddr, BATCH_DOWNLOAD_INFILE_REQUIRED_ERROR)
        downloadinfo.bDownloadBin = True
        if bin_type is None:
            downloadinfo.mixedBinInfo = binlist
        else:
            downloadinfo.vecbinInfo = binlist[0].binList
        expand_rolling_steps = None
        if expand_data_batch:
            (downloadinfo.expand_data_list, expand_rolling_steps) = parse_expand_data_batch(expand_data_batch)
        elif expand_data:
            downloadinfo.expand_data_list = parse_expand_data(expand_data)
        if del_after:
            if pathlist and len(pathlist) > 0:
                os.remove(pathlist[0])
            if safe_json and downloadinfo.safeinfo and downloadinfo.safeinfo.write_safe_config:
                os.remove(safe_json)
        batch_downloader = BatchDownload(port_list=portlist, baudrate=115200, reset_type=reset_type, reset_baudrate=reset_baudrate, getbus_times=getbus_times, reboot_after_download=reboot, retry=retrycnt, chipname=chipname, debug=debug, link_key=link_key, bin_type=bin_type, random_bin_path=random_bin_path, link_check_type_cli=link_check if link_key is None else None)
        BKLog.w(f"Starting batch download on {len(portlist)} port(s): {', '.join(portlist)}")
        results = batch_downloader.batch_download(downloadinfo, bin_type, report_channel_progress=report_channel_progress, expand_rolling_steps=expand_rolling_steps)
        batch_downloader.print_summary()
        all_success = all((success for (success, _) in results.values()))
        ui_bridge.end_flag('batch_download', all_success)
    except Exception as e:
        error_message = str(e)
        BKLog.e(error_message)
        ui_bridge.end_flag('batch_download', False, error_message=error_message)
        if BkInitiator.initiator_global != INITIATOR.FLUTTER_UI and error_message.startswith('Argument error'):
            raise click.ClickException(error_message)
        return None

@cli.command()
@click.option('-p', '--portnum', default='/dev/ttyUSB0', required=True, help="UART device, such as default '/dev/ttyUSB0'")
@click.option('-b', '--baudrate', default=2000000, type=int, help='Burn UART baudrate, defaults to 2000000')
@click.option('-r', '--reboot', is_flag=True, default=False, help='Reboot after download process')
@click.option('--link_type', type=click.Choice(CLI_LINK_TYPE_CHOICE), default='4', help=CLI_LINK_TYPE_HELP)
@click.option('--reset_type', type=click.Choice(['0', '1', '2', '3']), default='3', help="reset type,0=dtr/rts,1=command 'reboot',2=command '95 27',3=multi reset dtr/rts then cmd")
@click.option('--reset_baudrate', default=115200, type=int, help='app reset UART baudrate, defaults to 115200')
@click.option('-g', '--getbus_times', default=100, type=int, help='get bus times, default is 100 times')
@click.option('--retrycnt', default=5, type=int, help='Retry times')
@click.option('--chipid', type=str, help='default None will read from chipset,0x3000 for generic BT project, 0x3436 is a special one')
@click.option('-c', '--chip_all', is_flag=True, default=False, help='erase/read all chip')
@click.option('-d', '--debug', type=click.Choice(['0', '1', '2', '3', '999']), default='3', help='Set debug level: 0=nothing, 1=error message, 2=warning message, 3=info in test process + file, 999=full debug message + file')
@click.option('--link_key', type=str, help='Set link key, such as : --link_key 000102030405060708090a0b0c0d0e0f')
@click.option('-f', '--freedom', type=str, help='Input freedom address and length,Hex data,such as " [-f 0-10000] "')
@click.option('--flash_otp', type=str, help='Input flash OTP address and length,Hex data,such as " [-f 0-10000] "')
@click.option('--random_bin_path', type=str, default=None, help='Path to random.bin (max 192 bytes). Gated by enable_random_bin_verify in bk_loader config.')
def erase(portnum, baudrate, reboot, link_type, reset_type, reset_baudrate, getbus_times, retrycnt, chipid, chip_all, debug, freedom, link_key, flash_otp, random_bin_path):
    try:
        if reset_type == '0':
            reset_type = RESET_TYPE.DTR_RTS
        elif reset_type == '1':
            reset_type = RESET_TYPE.CMD_ASCII
        elif reset_type == '2':
            reset_type = RESET_TYPE.CMD_HEX
        else:
            reset_type = RESET_TYPE.MULTI
        link_check = _parse_cli_link_type(link_type)
        if link_key:
            link_key = bytes.fromhex(link_key)
            link_check = LINKCHECK.BOOTROM_EXT
            print('link_type:ext')
        if chipid:
            chipid = int(chipid, 16)
        else:
            chipid = None
        eraser = Erase(portnum, 115200, link_check, reset_type, reset_baudrate, getbus_times, reboot, retrycnt, chipid, debug, link_key, random_bin_path)
        eraseinfo = EraseInfo()
        eraseinfo.work_baudrate = baudrate
        eraseinfo.flash_otp = flash_otp
        if chip_all:
            eraseinfo.bAllFlash = True
        else:
            binlist = parse_erase_info(freedom)
            eraseinfo.vecbinInfo = binlist
            if binlist is None and (not eraseinfo.flash_otp):
                raise Exception('Argument error, need input address and length such as [-f 0-1000]')
        eraser.erase_task(eraseinfo=eraseinfo)
    except Exception as e:
        BKLog.e(str(e))
        ui_bridge.end_flag('', False)
        return

@cli.command()
@click.option('-p', '--portnum', default='/dev/ttyUSB0', required=True, help="UART device, such as default '/dev/ttyUSB0'")
@click.option('-b', '--baudrate', default=1000000, type=int, help='Burn UART baudrate, defaults to 1000000')
@click.option('-r', '--reboot', is_flag=True, default=False, help='Reboot after download process')
@click.option('--link_type', type=click.Choice(CLI_LINK_TYPE_CHOICE), default='4', help=CLI_LINK_TYPE_HELP)
@click.option('--reset_type', type=click.Choice(['0', '1', '2', '3']), default='3', help="reset type,0=dtr/rts,1=command 'reboot',2=command '95 27',3=multi reset dtr/rts then cmd")
@click.option('--reset_baudrate', default=115200, type=int, help='app reset UART baudrate, defaults to 115200')
@click.option('-g', '--getbus_times', default=100, type=int, help='get bus times, default is 100 times')
@click.option('--retrycnt', default=5, type=int, help='Retry times')
@click.option('--chipid', type=str, help='default 0 will read from chipset,0x3000 for generic BT project, 0x3436 is a special one')
@click.option('-c', '--chip_all', is_flag=True, default=False, help='erase/read all chip')
@click.option('-d', '--debug', type=click.Choice(['0', '1', '2', '3', '999']), default='3', help='Set debug level: 0=nothing, 1=error message, 2=warning message, 3=info in test process + file, 999=full debug message + file')
@click.option('--link_key', type=str, help='Set link key, such as : --link_key 000102030405060708090a0b0c0d0e0f')
@click.option('-o', '--out_path', type=click.Path(), help='Input dump file path for read flash.')
@click.option('-s', '--startaddr', default='0x0', help='Read flash address, defaults to 0x0')
@click.option('-f', '--freedom', type=str, help='Input freedom address and file length,Hex data,such as "[-f x-1.bin@0-10000] | [-f D:/all.trpk@0x10000-0x1000]"')
@click.option('--console', is_flag=True, default=False, help='Print the content to console after reading info')
@click.option('--read_uid', is_flag=True, default=False, help='Read chip UID')
@click.option('--read_efuse', type=str, help="Read chip efuse with address and length, such as '[0x10-4]'")
@click.option('--read_otp', type=str, help="Read chip otp with reg address and length, such as '[0x4b010000-4]'")
@click.option('--read_otp_efuse_auto', type=str, help="Read chip OTP or efuse by address and length, such as '[0x44850014-4]'")
@click.option('--reverse_content', is_flag=True, default=False, help='Read OTP such as AES key,set reverse content per 4 bytes')
@click.option('--flash_otp', type=str, help='Set read flash OTP information,include : [startAddress-length],such as : --flash_otp 0x0001ff-6')
@click.option('--read_otp_efuse_uid', type=str, help="Read chip otp/efuse/uid,otp need provide reg address and length, such as '[0x4b010000-4]'")
@click.option('--read_as_safe_json', type=click.Path(), help='Input safe json file path')
@click.option('--cbus', is_flag=True, default=False, help='use cbus to read')
@click.option('--random_bin_path', type=str, default=None, help='Path to random.bin (max 192 bytes). Gated by enable_random_bin_verify in bk_loader config.')
def read(portnum, baudrate, reboot, link_type, reset_type, reset_baudrate, getbus_times, retrycnt, chipid, chip_all, debug, out_path, startaddr, freedom, console, read_uid, read_efuse, read_otp, read_otp_efuse_auto, reverse_content, flash_otp, read_otp_efuse_uid, link_key, read_as_safe_json, cbus, random_bin_path):
    try:
        if reset_type == '0':
            reset_type = RESET_TYPE.DTR_RTS
        elif reset_type == '1':
            reset_type = RESET_TYPE.CMD_ASCII
        elif reset_type == '2':
            reset_type = RESET_TYPE.CMD_HEX
        else:
            reset_type = RESET_TYPE.MULTI
        link_check = _parse_cli_link_type(link_type)
        if link_key:
            link_key = bytes.fromhex(link_key)
            link_check = LINKCHECK.BOOTROM_EXT
            print('link_type:ext')
        if chipid:
            chipid = int(chipid, 16)
        else:
            chipid = None
        dumper = Dump(portnum, 115200, link_check, reset_type, reset_baudrate, getbus_times, reboot, retrycnt, chipid, debug, link_key, random_bin_path)
        readinfo = ReadInfo()
        readinfo.work_baudrate = baudrate
        readinfo.read_uid = read_uid
        readinfo.read_efuse = read_efuse
        readinfo.read_otp = read_otp
        readinfo.read_otp_efuse_auto = read_otp_efuse_auto
        readinfo.bConsole = console
        readinfo.reverse_content = reverse_content
        readinfo.read_path = out_path
        readinfo.read_otp_efuse_uid = read_otp_efuse_uid
        readinfo.flash_otp = flash_otp
        if chip_all:
            readinfo.bAllFlash = True
            dumpinfo = BinInfo()
            dumpinfo.bCheck = True
            dumpinfo.sFilePath = 'dump_all.bin'
            dumpinfo.iStartAddress = int(startaddr, 16)
            readinfo.vecbinInfo.append(dumpinfo)
        elif freedom:
            binlist = parse_dump_info(freedom)
            readinfo.vecbinInfo = binlist
            if binlist is None:
                raise Exception('Argument error, need input address and length such as [-f dump-1.bin@0-1000]')
        if read_as_safe_json:
            readinfo.safeinfo = parse_safe_json_file(read_as_safe_json)
            readinfo.safeinfo.read_safe_config = True
        if cbus:
            dumper.read_cbus_task(readinfo=readinfo)
        else:
            dumper.read_task(readinfo=readinfo)
    except Exception as e:
        BKLog.e(str(e))
        ui_bridge.end_flag('', False)
        return

@cli.command()
@click.option('-p', '--portnum', default='/dev/ttyUSB0', required=True, help="UART device, such as default '/dev/ttyUSB0'")
@click.option('-b', '--baudrate', default=1000000, type=int, help='Burn UART baudrate, defaults to 2000000')
@click.option('-r', '--reboot', is_flag=True, default=False, help='Reboot after download process')
@click.option('--link_type', type=click.Choice(CLI_LINK_TYPE_CHOICE), default='4', help=CLI_LINK_TYPE_HELP)
@click.option('--reset_type', type=click.Choice(['0', '1', '2']), default='0', help="reset type,0=dtr/rts,1=command 'reboot',2=command '95 27'")
@click.option('--reset_baudrate', default=115200, type=int, help='app reset UART baudrate, defaults to 115200')
@click.option('-g', '--getbus_times', default=100, type=int, help='get bus times, default is 100 times')
@click.option('--retrycnt', default=5, type=int, help='Retry times')
@click.option('--link_key', type=str, help='Set link key, such as : --link_key 000102030405060708090a0b0c0d0e0f')
@click.option('--chipid', type=str, help='default None will read from chipset,0x3000 for generic BT project, 0x3436 is a special one')
@click.option('-d', '--debug', type=click.Choice(['0', '1', '2', '3', '999']), default='3', help='Set debug level: 0=nothing, 1=error message, 2=warning message, 3=info in test process + file, 999=full debug message + file')
@click.option('--aes_key', type=str, help='Set aes128 ecb key stream')
def authorize(portnum, baudrate, reboot, link_type, reset_type, reset_baudrate, getbus_times, retrycnt, chipid, debug, aes_key, link_key):
    try:
        if reset_type == '0':
            reset_type = RESET_TYPE.DTR_RTS
        elif reset_type == '1':
            reset_type = RESET_TYPE.CMD_ASCII
        else:
            reset_type = RESET_TYPE.CMD_HEX
        link_check = _parse_cli_link_type(link_type)
        if link_key:
            link_key = bytes.fromhex(link_key)
            link_check = LINKCHECK.BOOTROM_EXT
            print('link_type:ext')
        if chipid:
            chipid = int(chipid, 16)
        else:
            chipid = None
        auth = Authorize(portnum, 115200, link_check, reset_type, reset_baudrate, getbus_times, reboot, retrycnt, chipid, debug)
        authinfo = AuthorizeInfo()
        authinfo.work_baudrate = baudrate
        if aes_key:
            authinfo.aes_key = aes_key
        auth.authorize_task(authinfo=authinfo)
    except Exception as e:
        BKLog.e(str(e))
        return

@cli.command()
@click.option('-p', '--portnum', default='/dev/ttyUSB0', required=True, help="UART device, such as default '/dev/ttyUSB0'")
@click.option('-b', '--baudrate', default=1000000, type=int, help='Burn UART baudrate, defaults to 2000000')
@click.option('-r', '--reboot', is_flag=True, default=False, help='Reboot after download process')
@click.option('--link_type', type=click.Choice(CLI_LINK_TYPE_CHOICE), default='4', help=CLI_LINK_TYPE_HELP)
@click.option('--reset_type', type=click.Choice(['0', '1', '2']), default='0', help="reset type,0=dtr/rts,1=command 'reboot',2=command '95 27'")
@click.option('--reset_baudrate', default=115200, type=int, help='app reset UART baudrate, defaults to 115200')
@click.option('-g', '--getbus_times', default=100, type=int, help='get bus times, default is 100 times')
@click.option('--retrycnt', default=5, type=int, help='Retry times')
@click.option('--link_key', type=str, help='Set link key, such as : --link_key 000102030405060708090a0b0c0d0e0f')
@click.option('--chipid', type=str, help='default None will read from chipset,0x3000 for generic BT project, 0x3436 is a special one')
@click.option('-d', '--debug', type=click.Choice(['0', '1', '2', '3', '999']), default='3', help='Set debug level: 0=nothing, 1=error message, 2=warning message, 3=info in test process + file, 999=full debug message + file')
@click.option('--enter_debug', is_flag=True, default=False, help='Enter secure debug')
@click.option('--key_path', type=str, help='Set key file path')
def secure(portnum, baudrate, reboot, link_type, reset_type, reset_baudrate, getbus_times, retrycnt, chipid, debug, link_key, enter_debug, key_path):
    try:
        if reset_type == '0':
            reset_type = RESET_TYPE.DTR_RTS
        elif reset_type == '1':
            reset_type = RESET_TYPE.CMD_ASCII
        else:
            reset_type = RESET_TYPE.CMD_HEX
        link_check = _parse_cli_link_type(link_type)
        if link_key:
            link_key = bytes.fromhex(link_key)
            link_check = LINKCHECK.BOOTROM_EXT
            print('link_type:ext')
        if chipid:
            chipid = int(chipid, 16)
        else:
            chipid = None
        sec = SecDebug(portnum, 115200, link_check, reset_type, reset_baudrate, getbus_times, reboot, retrycnt, chipid, debug)
        secinfo = SecureDebugInfo()
        secinfo.work_baudrate = baudrate
        secinfo.key_path = key_path
        if enter_debug:
            sec.secure_debug_task(secdbginfo=secinfo)
        else:
            raise Exception('No valid task')
    except Exception as e:
        BKLog.e(str(e))
        ui_bridge.end_flag('', False)
        return

@cli.command(name='inject_key')
@click.option('-p', '--portnum', default='/dev/ttyUSB0', required=True, help="UART device, such as default '/dev/ttyUSB0'")
@click.option('-d', '--debug', type=click.Choice(['0', '1', '2', '3', '999']), default='3', help='Set debug level: 0=nothing, 1=error message, 2=warning message, 3=info in test process + file, 999=full debug message + file')
@click.option('--aes_key_path', type=click.Path(), required=False, default=None, help='Input AES key JSON file path (optional, at least one of aes/random required)')
@click.option('--random_key_path', type=click.Path(), required=False, default=None, help='Input random key JSON file path (optional, at least one of aes/random required)')
def inject_key(portnum, debug, aes_key_path, random_key_path):
    try:
        if not aes_key_path and (not random_key_path):
            raise Exception('At least one of --aes_key_path or --random_key_path must be provided')
        if aes_key_path and (not os.path.exists(aes_key_path)):
            raise Exception(f'AES key file not found: {aes_key_path}')
        if random_key_path and (not os.path.exists(random_key_path)):
            raise Exception(f'Random key file not found: {random_key_path}')
        inject_key_service = InjectKey(port=portnum, debug=debug)
        result = inject_key_service.inject_key_task(aes_key_path=aes_key_path, random_key_path=random_key_path)
        if result:
            BKLog.w('Inject key completed successfully.')
        else:
            BKLog.e('Inject key failed.')
    except Exception as e:
        BKLog.e(str(e))
        ui_bridge.end_flag('', False)
        return

@cli.group('tools')
def tools_group():
    """Manage tools"""
    BKLog.w('tools start')

@tools_group.command('getbus')
@click.option('-p', '--portnum', default='/dev/ttyUSB0', required=True, help="UART device, such as default '/dev/ttyUSB0'")
@click.option('-g', '--getbus_times', default=20, type=int, help='get bus times, default is 20 times')
def getbus(portnum, getbus_times):
    BKLog(logger_level=logging.INFO, log_folder_path='./')
    serial = SerialHelper()
    serial.connect(portnum, 115200, 0)
    base_ctrl = BaseController(serial_instance=serial)
    (res, linkcheck_type) = base_ctrl.get_bus(reset_type=RESET_TYPE.DTR_RTS, max_try_count=getbus_times)
    if res:
        BKLog.i('getbus done.\r\n')
    else:
        BKLog.i('getbus fail.\r\n')

@tools_group.command('addcrc')
@click.option('-i', '--infile', type=click.Path(), help='Input one existing binary file.')
def addcrc(infile: str):
    BKLog(logger_level=logging.INFO, log_folder_path='./')
    BKLog.i(f'Add crc for file {infile}')
    with open(infile, 'rb') as f:
        src_data = f.read()
        f.close()
    total_len = len(src_data)
    if total_len % 32:
        total_len += 32 - total_len % 32
        src_data += '0xff' * (32 - total_len % 32)
    loop_cnt = int(total_len / 32)
    crcdata = bytearray()
    for idx in range(loop_cnt):
        data = bytearray(src_data[idx * 32:idx * 32 + 32])
        crcdata += crc32bytes(data=data)
    (root, ext) = os.path.splitext(infile)
    if not ext:
        ext = '.bin'
    outfile = f'{root}_crc{ext}'
    with open(outfile, 'wb') as of:
        of.write(crcdata)
        of.close()

@tools_group.command('rmcrc')
@click.option('-i', '--infile', type=click.Path(), help='Input one existing binary file.')
def rmcrc(infile: str):
    BKLog(logger_level=logging.INFO, log_folder_path='./')
    BKLog.i(f'Remove crc for file {infile}')
    with open(infile, 'rb') as f:
        src_data = f.read()
        f.close()
    total_len = len(src_data)
    if total_len % 34:
        total_len += 34 - total_len % 34
        src_data += '0xff' * (34 - total_len % 34)
    if crc32bytes(src_data[0:32]) == bytearray(src_data[0:34]):
        idx = 0
        nocrc_data = bytearray()
        while idx < total_len - 34:
            nocrc_data += bytearray(src_data[idx:idx + 32])
            idx += 34
    (root, ext) = os.path.splitext(infile)
    if not ext:
        ext = '.bin'
    outfile = f'{root}_rmcrc{ext}'
    with open(outfile, 'wb') as of:
        of.write(nocrc_data)
        of.close()

@tools_group.command('encrypt')
@click.option('-p', '--portnum', default='/dev/ttyUSB0', help='UART device, default /dev/ttyUSB0')
def encrypt(portnum):
    BKLog(logger_level=logging.INFO, log_folder_path='./')
    BKLog.i(f'Encrypting data on port {portnum}')

@tools_group.command('package')
@click.option('-p', '--portnum', default='/dev/ttyUSB0', help='UART device, default /dev/ttyUSB0')
def package(portnum):
    BKLog(logger_level=logging.INFO, log_folder_path='./')
    BKLog.i(f'Packaging data on port {portnum}')

@tools_group.command('list_ports')
def list_ports():
    ui_bridge.port_info()

@tools_group.command('bin_info')
@click.option('-i', '--infile', type=click.Path(), help='Input one existing binary files.')
@click.option('--infile_json', type=str, default=None, help='Input binary files as JSON, e.g. [{"path":"D:/fw/app.bin","start":"0x0","len":"0x1000"}].')
def bin_info(infile, infile_json):
    ui_bridge.bin_info(infile, infile_json)

@tools_group.command('cal_crc32')
@click.option('-i', '--infile', type=click.Path(), help='Input one existing binary files.')
def cal_crc32(infile):
    BKLog(logger_level=logging.INFO, log_folder_path='./')
    with open(infile, 'rb') as f:
        buf = f.read()
        f.close()
    if buf:
        buf_len = len(buf)
        padding_len = buf_len % 256
        if padding_len:
            buf += b'\xff' * (256 - padding_len)
            buf_len += 256 - padding_len
        crc32 = crc32_ver2(4294967295, buf)
        BKLog.i(f'CRC32 is: 0x{crc32:x}')
    else:
        BKLog.w('Error, bin file is empty')
if __name__ == '__main__':
    cli()
