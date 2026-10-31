from .base_boot_rom_flash_protocol import BaseBootRomFlashProtocol

class FlashSecurityReadProtocol(BaseBootRomFlashProtocol):

    def cmd(self, addr, size):
        payload = [72, addr >> 16 & 255, addr >> 8 & 255, addr & 255, 0]
        for _ in range(size):
            payload.append(0)
        return self.command_generate(14, payload)

    def expect_length(self, size):
        return self.rx_expect_length(5 + size)

    def response_check(self, response_content):
        return super().response_check(response_content)

    def get_read_val(self, response_content, size):
        return response_content[16:16 + size]
