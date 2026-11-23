# Copyright (C) 2016-2026 Bob Rosbag <mail@bobrosbag.nl>
# SPDX-License-Identifier: GPL-3.0-or-later

"""The icons, found the way the Builder app finds them (psychopy_app
2026.2.1, themes/icons.py): a component's icon is
<folder of iconFile>/<theme>/<stem>*.png; with none, the Builder window
does not open (IndexError).
"""

from pathlib import Path

import pytest
from PIL import Image

from psychopy_radboudbox.components import (RadboudboxButtonBoxBackend,
                                            RadboudboxControlComponent,
                                            RadboudboxSoundSensorBackend,
                                            RadboudboxTriggerComponent)

THEMES = ('light', 'dark', 'classic')


@pytest.mark.parametrize('component', [RadboudboxTriggerComponent,
                                       RadboudboxControlComponent])
@pytest.mark.parametrize('theme', THEMES)
def test_component_icon_per_theme(component, theme):
    icon = Path(component.iconFile)
    matches = {match.stem.replace(icon.stem, ''): match
               for match in (icon.parent / theme).glob(f'{icon.stem}*.png')}
    assert set(matches) == {'', '@2x'}
    assert Image.open(matches['']).size == (48, 48)
    assert Image.open(matches['@2x']).size == (96, 96)


@pytest.mark.parametrize('backend', [RadboudboxButtonBoxBackend,
                                     RadboudboxSoundSensorBackend])
def test_backend_icon_exists(backend):
    assert backend.getIconFile().is_file()


@pytest.mark.parametrize('backend', [RadboudboxButtonBoxBackend,
                                     RadboudboxSoundSensorBackend])
def test_backend_params_shown_in_device_manager(backend):
    """Device Manager (psychopy_app 2026.2.1, deviceManager/panel.py) shows
    the params of category Basic (or None) on the device's page and folds
    the others away behind a button, as PsychoPy's own backends don't.
    """
    device = backend({'deviceName': None})
    categories = {param.categ for param in device.params.values()}
    assert categories <= {'Basic', None}, categories
