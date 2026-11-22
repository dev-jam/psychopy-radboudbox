"""
This file is part of psychopy-radboudbox.

Copyright (C) 2016-2026 Bob Rosbag <mail@bobrosbag.nl>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.

SPDX-License-Identifier: GPL-3.0-or-later

The Radboud Buttonbox (BITSI) as PsychoPy devices, through rusocsci.

RadboudboxDevice owns the box: rusocsci opens the port and sends to it, a
reader thread reads every character the box sends and timestamps it when
it arrives (the box doesn't send times). RadboudboxButtonGroup (buttons
A-H) and RadboudboxSoundSensorGroup (sound or voice key) take their
characters from it; they are what Builder's Button Box and Sound Sensor
components use. Both create the RadboudboxDevice of their port through
DeviceManager, or use the one that is already there.
"""

__author__ = "Bob Rosbag"
__license__ = "GPL-3.0-or-later"

import collections
import os
import queue
import sys
import threading
import time

from psychopy import constants, core, logging
from psychopy.hardware.base import BaseDevice
from psychopy.hardware.button import BaseButtonGroup, ButtonResponse
from psychopy.hardware.manager import DeviceManager
from psychopy.hardware.soundsensor import (BaseSoundSensorGroup,
                                           SoundSensorResponse)

from . import portcheck
from .portcheck import RadboudboxError

# Buttons: upper case is a press, lower case its release
BUTTONS = 'ABCDEFGH'
# The box sends S or V once after a Detect Sound or Detect Voice command
SENSOR_CODES = {'sound': 'S', 'voice': 'V'}
# The box answers Analog In with digits (2018 firmware: and a line end)
ANALOG_CHARACTERS = '0123456789\r\n'
ANALOG_IN_TIMEOUT = 0.2  # (s) for the answer
ANALOG_IN_QUIET = 0.02  # (s) without a new digit: the answer is complete

# The reader thread waits this long (s) per read, so close() ends it within
# this time. A character that arrives ends the read at once.
READ_TIMEOUT = 0.05

# Extended mode commands (see the README for the firmware that has them)
COMMANDS = {'Calibrate Sound': 'CS',
            'Calibrate Voice': 'CV',
            'Detect Sound': 'DS',
            'Detect Voice': 'DV',
            'Marker Out': 'M',
            'Pulse Out': 'P',
            'Pulse Time': 'X',
            'Analog Out 1': 'Y',
            'Analog Out 2': 'Z',
            'Tone': 'T',
            'Analog In 1': 'A1',
            'Analog In 2': 'A2',
            'Analog In 3': 'A3',
            'Analog In 4': 'A4',
            'LEDs Off': 'LX',
            'LEDs Input': 'LI',
            'LEDs Output': 'LO'}
# Tone is one character: a value after it would be read as a new command
VALUE_COMMANDS = ('Marker Out', 'Pulse Out', 'Pulse Time', 'Analog Out 1',
                  'Analog Out 2')
CALIBRATE_COMMANDS = ('Calibrate Sound', 'Calibrate Voice')
ANALOG_IN_COMMANDS = ('Analog In 1', 'Analog In 2', 'Analog In 3',
                      'Analog In 4')
# Not in the oldest firmware (2014), whose ID string ends with "Ready!"
NEWER_FIRMWARE_COMMANDS = ('Pulse Out', 'Pulse Time')
CALIBRATE_TIME = 1.0  # (s) of silence after a calibrate command

# The mode is set on the box: hold two buttons while connecting it
MODE_BUTTONS = ('BITSI 2015 (Duemilanove): A+H simple, B+H extended; '
                'BITSI 2018 (Teensy): A+E simple, B+E extended')

WRONG_PORT_SETTINGS = ('error', 'warning')


def _check_bool(name, value):
    if not isinstance(value, bool):
        raise RadboudboxError(f'{name} should be True or False, not '
                              f'{value!r}')
    return value


def _check_byte(name, value):
    # bool is an int too: True would send 1
    if not isinstance(value, int) or isinstance(value, bool) \
            or not 0 <= value <= 255:
        raise RadboudboxError(f'{name} should be a whole number from 0 to '
                              f'255, not {value!r}')
    return value


def _same_port(a, b):
    """Whether two port names are the same port (a symbolic link such as
    /dev/serial/by-id/... is the same as its target; COM3 is com3).
    """
    if sys.platform == 'win32':
        return a.upper() == b.upper()
    return os.path.realpath(a) == os.path.realpath(b)


class RadboudboxDevice(BaseDevice):
    """The Radboud Buttonbox on one port. Usually made by
    RadboudboxButtonGroup or RadboudboxSoundSensorGroup; in Coder it can be
    made directly, e.g. to send triggers only.

    Parameters
    ----------
    port : str
        Port of the box, e.g. 'COM3' or '/dev/ttyACM0'. Empty: the first
        buttonbox found (or the box at deviceId).
    extendedMode : bool
        Must match the mode of the box (checked with the ID string it sends
        when it starts). Needed for commands and the sound and voice key.
    wrongPortSettings : str
        'error' (default) raises when a port setting makes the timing wrong;
        'warning' logs it and goes on (for tests only).
    deviceId : int or None
        With an empty port: the position in rusocsci's list of USB serial
        devices (0 is the device connected last). None: the first buttonbox.
    """

    def __init__(self, port='', extendedMode=True, wrongPortSettings='error',
                 deviceId=None):
        self.extendedMode = _check_bool('extendedMode', extendedMode)
        if wrongPortSettings not in WRONG_PORT_SETTINGS:
            raise RadboudboxError(f"wrongPortSettings should be 'error' or "
                                  f"'warning', not {wrongPortSettings!r}")
        if port is None:
            port = ''
        if not isinstance(port, str):
            raise RadboudboxError(f'port should be a port name such as COM3 '
                                  f'or /dev/ttyACM0, or empty, not {port!r}')
        if deviceId is not None and (not isinstance(deviceId, int)
                                     or isinstance(deviceId, bool)):
            raise RadboudboxError(f'deviceId should be a whole number (0 is '
                                  f'the device connected last) or None, not '
                                  f'{deviceId!r}')
        if port and deviceId is not None:
            raise RadboudboxError('Give a port or a deviceId, not both')
        # The nodes (button and sound sensor groups) that take characters
        self.nodes = []
        self._lock = threading.Lock()
        self._characters = collections.deque()
        self._analog = queue.Queue()
        self._error = None
        self._stop_event = threading.Event()
        self._thread = None
        self._box = None
        self._box = self._open(port.strip(), deviceId, wrongPortSettings)
        self.port = self.portInfo['port']
        # One timeout for all reads: the reader thread never changes it
        self._box._device.timeout = READ_TIMEOUT
        self._thread = threading.Thread(target=self._read_loop,
                                        name='radboudbox reader',
                                        daemon=True)
        self._thread.start()

    # --- opening ---

    def _open(self, port, device_id, wrong_port_settings):
        try:
            from rusocsci import buttonbox, extended, utils
        except ImportError as e:
            raise RadboudboxError('The RuSocSci package could not be '
                                  'imported. Please install it: pip install '
                                  'rusocsci') from e
        if not port:
            port = portcheck.find_port(utils.serialList(), device_id)
        # rusocsci reads the ID string of the box, but doesn't keep it
        id_strings = []
        open_port = utils.open

        def open_and_keep_id(port):
            device, id_string = open_port(port)
            id_strings.append(id_string)
            return device, id_string
        utils.open = open_and_keep_id
        try:
            if self.extendedMode:
                box = extended.Extended(port=port)
            else:
                box = buttonbox.Buttonbox(port=port)
        except Exception as e:
            raise RadboudboxError(f'Could not access the Radboud Buttonbox '
                                  f'on port {port}: {e}') from e
        finally:
            utils.open = open_port
        # rusocsci logs the reason and doesn't raise an exception
        if box._device is None:
            raise RadboudboxError(f'Could not open port {port} of the Radboud '
                                  f'Buttonbox, see the log for the reason')
        self.idString = id_strings[0] if id_strings else None
        check = portcheck.PortCheck(wrong_port_settings)
        try:
            self._check_mode(self.idString)
            check.check(port)
        except RadboudboxError:
            box.close()
            raise
        check.info['id_string'] = self.idString
        # e.g. type, port, driver, port_settings, latency_timer (README)
        self.portInfo = check.info
        logging.info(f'Radboud Buttonbox on {self.portInfo["port"]}: '
                     f'{self.idString}')
        return box

    def _check_mode(self, id_string):
        """Checks that the box is in the mode of extendedMode, with the ID
        string that the box sends when it starts. A box in the wrong mode
        sends wrong triggers without an error.
        """
        mode = 'extended' if self.extendedMode else 'simple'
        if id_string is None or 'Ready!' not in id_string:
            logging.warning(
                f'The Radboud Buttonbox did not send its ID string '
                f'({id_string!r}), so it could not be checked that the box '
                f'is in {mode} mode')
            return
        if 'BITSI_extend mode' in id_string:
            box_mode = 'extended'
        elif 'BITSI mode' in id_string or 'BITSI event mode' in id_string:
            box_mode = 'simple'
        else:
            raise RadboudboxError(
                f"The Radboud Buttonbox is in a mode this plugin doesn't "
                f"support ('{id_string}'). Switch it to {mode} mode: hold two "
                f"buttons while connecting it ({MODE_BUTTONS})")
        if box_mode != mode:
            raise RadboudboxError(
                f"The Radboud Buttonbox is in {box_mode} mode, but extended "
                f"mode is {self.extendedMode} ({mode} mode). Change the "
                f"device setting, or switch the box: hold two buttons while "
                f"connecting it ({MODE_BUTTONS})")

    # --- reading ---

    def _read_loop(self):
        """Reads the characters of the box and timestamps them on arrival
        (core.getTime()); runs until close(). An error is raised in the
        main thread by dispatchMessages().
        """
        device = self._box._device
        try:
            while not self._stop_event.is_set():
                data = device.read(1)
                if not data:
                    continue
                t = core.getTime()
                waiting = device.in_waiting
                if waiting:
                    # Arrived together: the same time
                    data += device.read(waiting)
                with self._lock:
                    for character in data.decode('ascii', errors='replace'):
                        if character in ANALOG_CHARACTERS:
                            self._analog.put(character)
                        else:
                            self._characters.append((character, t))
        except Exception as e:
            if not self._stop_event.is_set():
                self._error = e

    def _raise_error(self):
        error = self._error
        if error is not None:
            self._error = None
            raise RadboudboxError(f'Reading from the Radboud Buttonbox on '
                                  f'{self.port} failed: {error}') from error
        if not self._thread.is_alive() and not self._stop_event.is_set():
            raise RadboudboxError(f'The reader thread of the Radboud '
                                  f'Buttonbox on {self.port} has stopped')

    def dispatchMessages(self):
        """Passes the characters that arrived to the nodes that take them.
        Characters no node takes (e.g. buttons without a button group) are
        dropped.
        """
        self._raise_error()
        with self._lock:
            characters = list(self._characters)
            self._characters.clear()
        for character, t in characters:
            taken = False
            for node in self.nodes:
                if node.takes(character):
                    node.receiveMessage(node.parseMessage((character, t)))
                    taken = True
            if not taken:
                logging.debug(f'Radboud Buttonbox: {character!r} at {t} '
                              f'dropped, no device takes it')

    def clearEvents(self):
        """Drops the characters that arrived but were not dispatched."""
        self._raise_error()
        with self._lock:
            self._characters.clear()

    def getTime(self):
        """The clock of the timestamps (core.getTime())."""
        return core.getTime()

    # --- sending ---

    def _write(self, characters):
        """Sends a command (extended mode): a list of characters (sent as
        ASCII) and values (0-255).
        """
        self._raise_error()
        for character in characters:
            self._box.send(ord(character) if isinstance(character, str)
                           else character)

    def sendMarker(self, value):
        """Sets the trigger output to value (0-255); it keeps the value
        until the next marker. Works in both modes and all firmware.
        """
        value = _check_byte('Trigger value', value)
        self._raise_error()
        # rusocsci sends 'M' and the value in extended mode, the value in
        # simple mode
        self._box.sendMarker(val=value)

    def sendCommand(self, command, value=None):
        """Sends an extended mode command (see COMMANDS), with a value for
        the commands in VALUE_COMMANDS. Calibrate waits 1 s: be silent.
        Analog In returns the value the box answers. Other commands return
        None.
        """
        if not self.extendedMode:
            raise RadboudboxError('Commands only work in Bitsi extended mode')
        if command not in COMMANDS:
            raise RadboudboxError(f"Unknown command {command!r}, choose one "
                                  f"of: {', '.join(COMMANDS)}")
        if command in NEWER_FIRMWARE_COMMANDS and self.idString is not None \
                and self.idString.rstrip().endswith('Ready!'):
            raise RadboudboxError(
                f"'{command}' needs newer buttonbox firmware (2015-11-18 or "
                f"2018); this box has the 2014 firmware ('{self.idString}')")
        characters = list(COMMANDS[command])
        if command in VALUE_COMMANDS:
            characters.append(_check_byte(f'The value of {command}', value))
        elif value is not None:
            raise RadboudboxError(f"'{command}' takes no value, not "
                                  f"{value!r}")
        if command in ANALOG_IN_COMMANDS:
            # Digits of an earlier answer
            self._drop_analog()
        self._write(characters)
        logging.exp(f'Radboud Buttonbox: sent {command}'
                    + ('' if value is None else f' {value}'))
        if command in CALIBRATE_COMMANDS:
            time.sleep(CALIBRATE_TIME)
        if command in ANALOG_IN_COMMANDS:
            return self._read_analog_in(command)
        return None

    def _drop_analog(self):
        while True:
            try:
                self._analog.get_nowait()
            except queue.Empty:
                return

    def _read_analog_in(self, command):
        """The digits of the answer; the 2014 firmware sends no line end,
        so a short silence after a digit ends it too.
        """
        digits = ''
        end = time.monotonic() + ANALOG_IN_TIMEOUT
        while True:
            wait = ANALOG_IN_QUIET if digits else end - time.monotonic()
            if wait <= 0:
                break
            try:
                character = self._analog.get(timeout=wait)
            except queue.Empty:
                break
            if character in '\r\n':
                if digits:
                    break
                continue
            digits += character
        self._raise_error()
        if not digits:
            raise RadboudboxError(f"The Radboud Buttonbox did not answer "
                                  f"'{command}' within "
                                  f"{int(ANALOG_IN_TIMEOUT * 1000)} ms")
        return int(digits)

    # --- DeviceManager ---

    def isSameDevice(self, other):
        if isinstance(other, RadboudboxDevice):
            return _same_port(self.port, other.port)
        if isinstance(other, (RadboudboxButtonGroup,
                              RadboudboxSoundSensorGroup)):
            return other.parent is self
        if isinstance(other, dict) and other.get('port'):
            return _same_port(self.port, other['port'])
        return False

    @staticmethod
    def getAvailableDevices():
        devices = []
        for info in portcheck.list_buttonbox_ports():
            devices.append({
                'deviceName': f'Radboud Buttonbox '
                              f'{portcheck.box_type(info.vid)} ({info.device})',
                'port': info.device,
            })
        return devices

    def close(self):
        """Ends the reader thread and closes the port."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=1)
            if self._thread.is_alive():
                logging.warning('The reader thread of the Radboud Buttonbox '
                                'did not end')
        if self._box is not None:
            try:
                self._box.close()
            except Exception as e:
                # Also at the end after an error: raising would hide it
                logging.warning(f'Failed to close the Radboud Buttonbox: {e}')
            self._box = None

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass


def resolve_device(port, extendedMode, wrongPortSettings):
    """The RadboudboxDevice of the port in DeviceManager, or a new one
    added to it. An empty port takes the box that is there, when there is
    one.
    """
    port = (port or '').strip()
    devices = list(DeviceManager.getInitialisedDevices(
        RadboudboxDevice).values())
    if port:
        devices = [d for d in devices if d.isSameDevice({'port': port})]
    elif len(devices) > 1:
        raise RadboudboxError(
            f'There are {len(devices)} Radboud Buttonboxes: set the port of '
            f'each device (' + ', '.join(d.port for d in devices) + ')')
    if devices:
        device = devices[0]
        if device.extendedMode != extendedMode:
            raise RadboudboxError(
                f'The Radboud Buttonbox on {device.port} is already set up '
                f'with extended mode {device.extendedMode}: use the same '
                f'extended mode for all devices of this box')
        return device
    return DeviceManager.addDevice(
        deviceClass='psychopy_radboudbox.radboudbox.RadboudboxDevice',
        deviceName=f'radboudbox@{port or "autodetect"}',
        port=port, extendedMode=extendedMode,
        wrongPortSettings=wrongPortSettings)


class _RadboudboxNode:
    """What the button and sound sensor groups share: the parent box, its
    clock and its commands.
    """

    def _attach(self, port, extendedMode, wrongPortSettings):
        _check_bool('extendedMode', extendedMode)
        self.parent = resolve_device(port, extendedMode, wrongPortSettings)
        # Added to the clock of the box: the clock of resetTimer()
        self._timeAdjust = 0.0
        self.parent.nodes.append(self)

    def resetTimer(self, clock=logging.defaultClock):
        """Gives the times of the responses on this clock."""
        self._timeAdjust = clock.getTime() - self.parent.getTime()

    def dispatchMessages(self):
        self.parent.dispatchMessages()

    def sendMarker(self, value):
        """See RadboudboxDevice.sendMarker()."""
        return self.parent.sendMarker(value)

    def sendCommand(self, command, value=None):
        """See RadboudboxDevice.sendCommand()."""
        return self.parent.sendCommand(command, value)

    def isSameDevice(self, other):
        if isinstance(other, _RadboudboxNode):
            return other is self
        if isinstance(other, dict):
            return self._same_profile(other)
        return False

    def close(self):
        if self in self.parent.nodes:
            self.parent.nodes.remove(self)


class RadboudboxButtonGroup(_RadboudboxNode, BaseButtonGroup):
    """The buttons of the Radboud Buttonbox: channel 0-7 is button A-H;
    a press has value True, a release False. The time of a response is
    the moment it arrived from the box, on the clock of resetTimer().

    Parameters
    ----------
    port, extendedMode, wrongPortSettings
        See RadboudboxDevice.
    channels : int
        Number of buttons (1-8).
    """

    def __init__(self, port='', extendedMode=True, wrongPortSettings='error',
                 channels=len(BUTTONS)):
        if not isinstance(channels, int) or isinstance(channels, bool) \
                or not 1 <= channels <= len(BUTTONS):
            raise RadboudboxError(f'channels should be the number of buttons, '
                                  f'1 to {len(BUTTONS)}, not {channels!r}')
        BaseButtonGroup.__init__(self, channels=channels)
        self._attach(port, extendedMode, wrongPortSettings)

    def takes(self, character):
        return character.upper() in BUTTONS[:self.channels]

    def parseMessage(self, message):
        character, t = message
        return ButtonResponse(t=t + self._timeAdjust,
                              value=character.isupper(),
                              channel=BUTTONS.index(character.upper()))

    def _same_profile(self, profile):
        return 'port' in profile and self.parent.isSameDevice(profile) \
            and profile.get('kind', 'buttons') == 'buttons'

    @staticmethod
    def getAvailableDevices():
        return [dict(profile, deviceName=profile['deviceName'] + ' buttons')
                for profile in RadboudboxDevice.getAvailableDevices()]


class RadboudboxSoundSensorGroup(_RadboudboxNode, BaseSoundSensorGroup):
    """The sound or voice key of the Radboud Buttonbox (extended mode),
    one channel. The box sends a response once after each Detect command;
    clearResponses() sends it, so detection starts when a Sound Sensor
    component starts. A response has value True; the box sends no end of
    the sound. The box has no threshold: it calibrates the silence.

    Parameters
    ----------
    port, extendedMode, wrongPortSettings
        See RadboudboxDevice.
    sensor : str
        'sound' (sound key) or 'voice' (voice key).
    calibrate : bool
        Calibrate the silence when the device is set up (1 s, be silent).
    """

    def __init__(self, port='', extendedMode=True, wrongPortSettings='error',
                 sensor='sound', calibrate=True):
        if sensor not in SENSOR_CODES:
            raise RadboudboxError(f"sensor should be 'sound' or 'voice', not "
                                  f"{sensor!r}")
        _check_bool('calibrate', calibrate)
        if not extendedMode:
            raise RadboudboxError('The sound and voice key only work in Bitsi '
                                  'extended mode')
        self.sensor = sensor
        self.code = SENSOR_CODES[sensor]
        BaseSoundSensorGroup.__init__(self, channels=1, threshold=None)
        self._attach(port, extendedMode, wrongPortSettings)
        if calibrate:
            self.calibrate()

    def takes(self, character):
        return character == self.code

    def parseMessage(self, message):
        character, t = message
        return SoundSensorResponse(t=t + self._timeAdjust, value=True,
                                   channel=0, device=self)

    def calibrate(self):
        """Calibrates the silence (1 s: be silent)."""
        self.parent.sendCommand(f'Calibrate {self.sensor.capitalize()}')

    def detect(self):
        """Starts detection: the box sends one response at the next
        sound.
        """
        self.parent.sendCommand(f'Detect {self.sensor.capitalize()}')

    def clearResponses(self):
        """Drops the earlier responses and starts detection."""
        BaseSoundSensorGroup.clearResponses(self)
        self.detect()
        return True

    def _setThreshold(self, threshold, channel=None):
        if threshold is not None:
            logging.warning('The Radboud Buttonbox has no threshold for its '
                            'sound and voice key; it calibrates the silence')
        return False

    def _same_profile(self, profile):
        return 'port' in profile and self.parent.isSameDevice(profile) \
            and profile.get('sensor', 'sound') == self.sensor

    @staticmethod
    def getAvailableDevices():
        devices = []
        for profile in RadboudboxDevice.getAvailableDevices():
            for sensor in SENSOR_CODES:
                devices.append(dict(
                    profile, sensor=sensor,
                    deviceName=f'{profile["deviceName"]} {sensor} key'))
        return devices


class RadboudboxSender:
    """What a Radboud Buttonbox Trigger or Control component uses: one per
    component, with its own status (as psychopy.hardware.button.ButtonBox
    for the Button Box component), for a device of Device Manager.

    Parameters
    ----------
    device : str or RadboudboxDevice or a group
        The label of the device in Device Manager, or the device.
    """

    def __init__(self, device):
        if isinstance(device, str):
            label = device
            device = DeviceManager.getDevice(label)
            if device is None:
                raise RadboudboxError(
                    f'There is no device {label!r}: choose a Radboud '
                    f'Buttonbox device of Device Manager')
        if not isinstance(device, (RadboudboxDevice, _RadboudboxNode)):
            raise RadboudboxError(f'{device!r} is not a Radboud Buttonbox '
                                  f'device')
        self.device = device
        self.status = constants.NOT_STARTED

    def sendMarker(self, value):
        """See RadboudboxDevice.sendMarker()."""
        return self.device.sendMarker(value)

    def sendCommand(self, command, value=None):
        """See RadboudboxDevice.sendCommand()."""
        return self.device.sendCommand(command, value)
