"""Protocol used to switch a running application into key-injection mode."""


class InjectKeyStartProtocol:
    START_CMD = b"insert_key_start\r\n"

    def cmd(self):
        return self.START_CMD

    @property
    def expect_length(self):
        return 0

    def response_check(self, response_content):
        return True, None
