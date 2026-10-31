# Decompiled with PyLingual (https://pylingual.io)
# Internal filename: 'bkutils/chip_controller/chip_set/__init__.py'
# Bytecode version: 3.9.0beta5 (3425)
# Source timestamp: 1970-01-01 00:00:00 UTC (0)

from ...bk_log import BKLog
from .base_chip import BaseChip
from .bk7236 import BK7236
from .bk7231N import BK7231N
from .bk7259 import BK7259
from .bk7252N import BK7252N
from .bk7238 import BK7238
from .bk3633 import BK3633
from .bk3436 import BK3436
from .bk3437 import BK3437
from .bk7256 import BK7256
from .bk7236Q import BK7236Q
from .bk7236N import BK7236N
from .bk7239N import BK7239N
from .bk5886 import BK5886
from .bk7311 import BK7311
from .bk3653 import BK3653
from .bk3515N import BK3515N
def get_chip_set_with_chip_id(chip_id, sec_id=65537) -> BaseChip:
    ChipSetClass = None
    if chip_id == BK7236N.CHIP_ID:
        ChipSetClass = BK7236N()
        BKLog.sensitive_information('BK7236NN')
    else:
        if chip_id == BK7236Q.CHIP_ID:
            ChipSetClass = BK7236Q()
            BKLog.sensitive_information('BK7236Q')
        else:
            if chip_id == BK7236.CHIP_ID or chip_id >> 16 == BK7236.CHIP_ID:
                for id in BK7236N.SECOND_ID:
                    if sec_id == id:
                        ChipSetClass = BK7236N()
                        BKLog.sensitive_information('BK7236N')
                        break
                if ChipSetClass is None:
                    for id in BK7239N.SECOND_ID:
                        if sec_id == id:
                            ChipSetClass = BK7239N()
                            BKLog.sensitive_information('BK7239N')
                            break
                if ChipSetClass is None:
                    for id in BK7236Q.SECOND_ID:
                        if sec_id == id:
                            ChipSetClass = BK7236Q()
                            BKLog.sensitive_information('BK7236Q')
                            break
                if ChipSetClass is None:
                    ChipSetClass = BK7236()
                    BKLog.sensitive_information('BK7236')
            else:
                if chip_id == BK7259.CHIP_ID or chip_id >> 16 == BK7259.CHIP_ID:
                    ChipSetClass = BK7259()
                else:
                    if chip_id == BK7231N.CHIP_ID:
                        ChipSetClass = BK7231N()
                    else:
                        if chip_id == BK7252N.CHIP_ID:
                            ChipSetClass = BK7252N()
                        else:
                            if chip_id == BK7238.CHIP_ID:
                                ChipSetClass = BK7238()
                            else:
                                if chip_id == BK3633.CHIP_ID:
                                    ChipSetClass = BK3633()
                                else:
                                    if chip_id == BK3436.CHIP_ID:
                                        ChipSetClass = BK3436()
                                    else:
                                        if chip_id == BK3437.CHIP_ID:
                                            ChipSetClass = BK3437()
                                        else:
                                            if chip_id == BK7256.CHIP_ID or chip_id >> 16 == BK7256.CHIP_ID:
                                                ChipSetClass = BK7256()
                                            else:
                                                if chip_id == BK5886.CHIP_ID:
                                                    ChipSetClass = BK5886()
                                                else:
                                                    if chip_id == BK3653.CHIP_ID:
                                                        ChipSetClass = BK3653()
                                                    else:
                                                        if chip_id == BK7311.CHIP_ID or chip_id >> 16 == BK7311.CHIP_ID:
                                                            ChipSetClass = BK7311()
                                                        else:
                                                            if chip_id == BK3515N.CHIP_ID:
                                                                ChipSetClass = BK3515N()
                                                            else:
                                                                ChipSetClass = BK7236N()
                                                                BKLog.sensitive_information('Current Chip is not support, use BK7236N as default')
    return ChipSetClass
def get_chip_set_with_chip_name(chip_name: str=None) -> BaseChip:
    if chip_name is None:
        return
    else:
        chip_name = chip_name.upper()
        if chip_name in ['BK7236', 'BK7258']:
            return BK7236()
        else:
            if chip_name in ['BK7236N']:
                return BK7236N()
            else:
                if chip_name in ['BK7239N']:
                    return BK7239N()
                else:
                    if chip_name == 'BK7236Q':
                        return BK7236Q()
                    else:
                        if chip_name == 'BK7259':
                            return BK7259()
                        else:
                            if chip_name == 'BK7231N':
                                return BK7231N()
                            else:
                                if chip_name == 'BK7252N':
                                    return BK7252N()
                                else:
                                    if chip_name == 'BK7238':
                                        return BK7238()
                                    else:
                                        if chip_name == 'BK3633':
                                            return BK3633()
                                        else:
                                            if chip_name == 'BK3436':
                                                return BK3436()
                                            else:
                                                if chip_name == 'BK3437':
                                                    return BK3437()
                                                else:
                                                    if chip_name == 'BK7256':
                                                        return BK7256()
                                                    else:
                                                        if chip_name == 'BK5886':
                                                            return BK5886()
                                                        else:
                                                            if chip_name == 'BK7311':
                                                                return BK7311()
                                                            else:
                                                                if chip_name == 'BK3515N':
                                                                    return BK3515N()