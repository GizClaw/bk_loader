"""Initiator identity shared by configuration and logging without an import cycle."""

from enum import Enum


class INITIATOR(Enum):
    CLI = 0
    FLUTTER_UI = 1
