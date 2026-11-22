# Copyright (C) 2016-2026 Bob Rosbag <mail@bobrosbag.nl>
# SPDX-License-Identifier: GPL-3.0-or-later

"""PsychoPy plugin for the Radboud Buttonbox (BITSI)"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version('psychopy-radboudbox')
except PackageNotFoundError:
    # Running from a source folder that is not installed
    __version__ = 'unknown'
