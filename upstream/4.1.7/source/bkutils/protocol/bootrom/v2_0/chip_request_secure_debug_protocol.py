from .base_boot_rom_protocol import BaseBootRomProtocol

class ChipRequestSecureDebugProtocol(BaseBootRomProtocol):

    def cmd(self, debug_mode, sign_data: list):
        payload = [debug_mode]
        payload.append(len(sign_data))
        payload.extend(sign_data)
        return self.command_generate(81, payload)

    @property
    def expect_length(self):
        raise Exception('not support.')

    def response_check(self, response_content):
        raise Exception('not support.')
