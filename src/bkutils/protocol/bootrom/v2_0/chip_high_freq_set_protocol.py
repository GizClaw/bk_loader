from .base_boot_rom_protocol import BaseBootRomProtocol

class ChipHighFreqSetProtocol(BaseBootRomProtocol):

    def cmd(self, mode: int, cpu_freq: int, flash_freq: int, target: int, delay=10):
        payload = [mode & 255, cpu_freq & 255, flash_freq & 255]
        payload.extend([target & 255, target >> 8 & 255, target >> 16 & 255, target >> 24 & 255])
        payload.append(delay & 255)
        return self.command_generate(22, payload)

    @property
    def expect_length(self):
        return self.rx_expect_length(9)

    def response_check(self, response_content):
        return super().response_check(response_content) and self.get_response_cmd(response_content) == bytes([22]) and (self.get_response_payload(response_content)[0] == 0)
