# SPDX-FileCopyrightText: 2026 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

"""GDB utilities for debugging ESP-IDF drivers."""

__version__ = '0.2.0'

try:
    from .lcd import FramebufferDisplayCommand
except ModuleNotFoundError as err:
    if err.name != 'gdb':
        raise
else:
    FramebufferDisplayCommand()
