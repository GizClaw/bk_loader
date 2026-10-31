from .base_boot_rom_flash_protocol import BaseBootRomFlashProtocol

class FlashSecurityEraseProtocol(BaseBootRomFlashProtocol):

    def cmd(self, addr):
        return self.command_generate(14, [68, addr >> 16 & 255, addr >> 8 & 255, addr & 255])

    @property
    def expect_length(self):
        return self.rx_expect_length(4)

    def response_check(self, response_content):
        return super().response_check(response_content)
