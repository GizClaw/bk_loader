from .base_boot_rom_protocol import BaseBootRomProtocol

class ChipEnterSecureDebugProtocol(BaseBootRomProtocol):

    def cmd(self, pubkey: list):
        payload = [len(pubkey)]
        payload.extend(pubkey)
        return self.command_generate(80, payload)

    @property
    def expect_length(self):
        return self.rx_expect_length(32)

    def response_check(self, response_content):
        return super().response_check(response_content) and self.get_response_cmd(response_content) == bytes([80]) and (self.get_response_payload(response_content) == bytes([0]))

    def get_rdm_data(self, response_content):
        return self.get_response_payload(response_content)[8:]
