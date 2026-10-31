from .base_boot_rom_protocol import BaseBootRomProtocol
from ....common.common import crc32_ver2

class ChipEnterCbusModeDbgProtocol(BaseBootRomProtocol):

    def cmd(self, flash_addr: list):
        data = []
        data = flash_addr
        crc = crc32_ver2(4294967295, data)
        data.append(crc & 255)
        data.append(crc >> 8 & 255)
        data.append(crc >> 16 & 255)
        data.append(crc >> 24 & 255)
        return self.command_generate(20, data)

    @property
    def expect_length(self):
        return self.rx_expect_length(1)

    def response_check(self, response_content):
        return super().response_check(response_content) and self.get_response_cmd(response_content) == bytes([20]) and (self.get_response_payload(response_content) == bytes([0]))
