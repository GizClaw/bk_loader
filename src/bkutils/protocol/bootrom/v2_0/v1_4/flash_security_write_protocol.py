from .base_boot_rom_flash_protocol import BaseBootRomFlashProtocol

class FlashSecurityWriteProtocol(BaseBootRomFlashProtocol):

    def cmd(self, addr, data):
        payload = [66, addr >> 16 & 255, addr >> 8 & 255, addr & 255]
        payload.extend(data)
        return self.command_generate(14, payload)

    def expect_length(self, oplen):
        return self.rx_expect_length(4 + oplen)

    def response_check(self, response_content):
        return super().response_check(response_content)
