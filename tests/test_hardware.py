# Copyright (C) 2016-2026 Bob Rosbag <mail@bobrosbag.nl>
# SPDX-License-Identifier: GPL-3.0-or-later

"""The hardware classes with a simulated box (conftest.py)."""

import time

import pytest
from psychopy import core
from psychopy.hardware.manager import DeviceManager

from psychopy_radboudbox.radboudbox import (RadboudboxButtonGroup,
                                            RadboudboxDevice,
                                            RadboudboxError,
                                            RadboudboxSoundSensorGroup)

from conftest import ID_2014, ID_SIMPLE

PORT = '/dev/fakebox0'


def wait_for(condition, timeout=1.0):
    end = time.monotonic() + timeout
    while not condition():
        if time.monotonic() > end:
            return False
        time.sleep(0.005)
    return True


def test_open_extended_keeps_id_string(fake_box):
    fake_box(PORT)
    device = RadboudboxDevice(port=PORT)
    assert device.idString == 'BITSI_extend mode, Ready! w:2018'
    assert device.portInfo['id_string'] == device.idString
    assert device.portInfo['port'] == PORT
    assert device._thread.is_alive()
    device.close()
    assert not device._thread.is_alive()


def test_mode_mismatch_is_an_error(fake_box):
    fake_box(PORT, id_string=ID_SIMPLE)
    with pytest.raises(RadboudboxError, match='simple mode'):
        RadboudboxDevice(port=PORT, extendedMode=True)


def test_missing_id_string_warns_and_opens(fake_box):
    fake_box(PORT, id_string=None)
    device = RadboudboxDevice(port=PORT)
    assert device.idString == 'USB serial timeout'
    device.close()


def test_missing_port_is_an_error(fake_box):
    with pytest.raises(RadboudboxError, match='Could not open port'):
        RadboudboxDevice(port='/dev/nothing')


@pytest.mark.parametrize('kwargs, message', [
    ({'extendedMode': 'yes'}, 'extendedMode'),
    ({'wrongPortSettings': 'ignore'}, 'wrongPortSettings'),
    ({'port': 3}, 'port should be'),
    ({'deviceId': '0'}, 'deviceId'),
    ({'port': PORT, 'deviceId': 0}, 'not both'),
])
def test_invalid_settings(fake_box, kwargs, message):
    with pytest.raises(RadboudboxError, match=message):
        RadboudboxDevice(**kwargs)


def test_buttons_timestamped_on_arrival(fake_box):
    box = fake_box(PORT)
    buttons = RadboudboxButtonGroup(port=PORT)
    clock = core.Clock()
    buttons.resetTimer(clock)
    box.press('A')
    t_press = clock.getTime()
    box.press('b')
    # Read much later than the press, as a Builder component one frame on
    time.sleep(0.1)
    responses = buttons.getResponses()
    assert [(r.channel, r.value) for r in responses] == [(0, True),
                                                         (1, False)]
    assert abs(responses[0].t - t_press) < 0.02
    # Not the time of getResponses()
    assert clock.getTime() - responses[0].t > 0.08


def test_response_before_reset_timer_is_negative(fake_box):
    # A component that starts later, without discarding earlier responses
    box = fake_box(PORT)
    buttons = RadboudboxButtonGroup(port=PORT)
    box.press('A')
    time.sleep(0.1)
    clock = core.Clock()
    buttons.resetTimer(clock)
    responses = buttons.getResponses()
    assert len(responses) == 1
    assert -0.12 < responses[0].t < -0.08


def test_get_responses_filters_state_and_channel(fake_box):
    box = fake_box(PORT)
    buttons = RadboudboxButtonGroup(port=PORT)
    box.press('AaBbC')
    assert wait_for(lambda: buttons.parent._characters)
    time.sleep(0.02)
    presses = buttons.getResponses(state=True, channel=[0, 2])
    assert [r.channel for r in presses] == [0, 2]
    rest = buttons.getResponses()
    assert [(r.channel, r.value) for r in rest] == [(0, False), (1, True),
                                                    (1, False)]


def test_channels_limits_buttons(fake_box):
    box = fake_box(PORT)
    buttons = RadboudboxButtonGroup(port=PORT, channels=2)
    box.press('ABC')
    time.sleep(0.05)
    assert [r.channel for r in buttons.getResponses()] == [0, 1]


def test_clear_responses_drops_earlier(fake_box):
    box = fake_box(PORT)
    buttons = RadboudboxButtonGroup(port=PORT)
    box.press('A')
    time.sleep(0.05)
    buttons.clearResponses()
    box.press('B')
    time.sleep(0.05)
    assert [r.channel for r in buttons.getResponses()] == [1]


def test_send_marker_extended_and_simple(fake_box):
    box = fake_box(PORT)
    device = RadboudboxDevice(port=PORT)
    device.sendMarker(5)
    assert bytes(box.written) == b'M\x05'
    device.close()
    box = fake_box('/dev/fakebox1', id_string=ID_SIMPLE)
    device = RadboudboxDevice(port='/dev/fakebox1', extendedMode=False)
    device.sendMarker(255)
    assert bytes(box.written) == b'\xff'
    device.close()


@pytest.mark.parametrize('value', [256, -1, True, '1', 1.0, None])
def test_send_marker_rejects(fake_box, value):
    fake_box(PORT)
    device = RadboudboxDevice(port=PORT)
    with pytest.raises(RadboudboxError, match='0 to 255'):
        device.sendMarker(value)
    device.close()


def test_commands(fake_box):
    box = fake_box(PORT)
    device = RadboudboxDevice(port=PORT)
    device.sendCommand('Tone')
    device.sendCommand('Pulse Time', 100)
    device.sendCommand('LEDs Input')
    assert bytes(box.written) == b'TXdLI'
    with pytest.raises(RadboudboxError, match='takes no value'):
        device.sendCommand('Tone', 3)
    with pytest.raises(RadboudboxError, match='0 to 255'):
        device.sendCommand('Marker Out', 300)
    with pytest.raises(RadboudboxError, match='Unknown command'):
        device.sendCommand('Beep')
    device.close()


def test_commands_need_extended_mode(fake_box):
    fake_box(PORT, id_string=ID_SIMPLE)
    device = RadboudboxDevice(port=PORT, extendedMode=False)
    with pytest.raises(RadboudboxError, match='extended mode'):
        device.sendCommand('Tone')
    device.close()


def test_pulse_needs_newer_firmware(fake_box):
    fake_box(PORT, id_string=ID_2014)
    device = RadboudboxDevice(port=PORT)
    with pytest.raises(RadboudboxError, match='2014 firmware'):
        device.sendCommand('Pulse Out', 3)
    device.close()


def test_analog_in_while_buttons_arrive(fake_box):
    box = fake_box(PORT)
    buttons = RadboudboxButtonGroup(port=PORT)
    box.press('A')
    assert buttons.sendCommand('Analog In 2') == 512
    assert bytes(box.written) == b'A2'
    box.press('a')
    time.sleep(0.05)
    # The digits are not buttons
    assert [(r.channel, r.value) for r in buttons.getResponses()] == [
        (0, True), (0, False)]


def test_analog_in_2014_firmware_without_line_end(fake_box):
    fake_box(PORT, analog_answer=b'37')
    device = RadboudboxDevice(port=PORT)
    assert device.sendCommand('Analog In 1') == 37
    device.close()


def test_analog_in_without_answer(fake_box):
    fake_box(PORT, analog_answer=None)
    device = RadboudboxDevice(port=PORT)
    with pytest.raises(RadboudboxError, match='did not answer'):
        device.sendCommand('Analog In 1')
    device.close()


def test_sound_sensor_detects_after_clear(fake_box):
    box = fake_box(PORT)
    start = time.monotonic()
    voice = RadboudboxSoundSensorGroup(port=PORT, sensor='voice')
    # Calibrated: 1 s of silence
    assert time.monotonic() - start >= 1.0
    assert bytes(box.written) == b'CV'
    voice.clearResponses()
    assert bytes(box.written) == b'CVDV'
    box.press('SV')
    time.sleep(0.05)
    responses = voice.getResponses(state=True)
    assert [(r.channel, r.value) for r in responses] == [(0, True)]


def test_sound_sensor_needs_extended_mode(fake_box):
    fake_box(PORT, id_string=ID_SIMPLE)
    with pytest.raises(RadboudboxError, match='extended mode'):
        RadboudboxSoundSensorGroup(port=PORT, extendedMode=False)


def test_groups_share_the_box(fake_box):
    box = fake_box(PORT)
    buttons = DeviceManager.addDevice(
        deviceClass='psychopy_radboudbox.radboudbox.RadboudboxButtonGroup',
        deviceName='buttons', port=PORT)
    sound = DeviceManager.addDevice(
        deviceClass='psychopy_radboudbox.radboudbox.RadboudboxSoundSensorGroup',
        deviceName='sound', port='', calibrate=False)
    assert sound.parent is buttons.parent
    box.press('AS')
    time.sleep(0.05)
    # Each group gets its own characters, whichever reads first
    assert [r.value for r in sound.getResponses()] == [True]
    assert [r.channel for r in buttons.getResponses()] == [0]


def test_groups_with_other_extended_mode(fake_box):
    fake_box(PORT)
    RadboudboxButtonGroup(port=PORT)
    with pytest.raises(RadboudboxError, match='same extended mode'):
        RadboudboxButtonGroup(port=PORT, extendedMode=False)


def test_reader_error_is_raised_in_main_thread(fake_box):
    fake_box(PORT)
    buttons = RadboudboxButtonGroup(port=PORT)

    def broken_read(size=1):
        raise OSError('device disconnected')
    buttons.parent._box._device.read = broken_read
    assert wait_for(lambda: not buttons.parent._thread.is_alive())
    with pytest.raises(RadboudboxError, match='device disconnected'):
        buttons.getResponses()


def test_available_devices_never_fail(monkeypatch):
    from serial.tools import list_ports

    def broken():
        raise OSError('no access')
    monkeypatch.setattr(list_ports, 'comports', broken)
    assert RadboudboxButtonGroup.getAvailableDevices() == []
