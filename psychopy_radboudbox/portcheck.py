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

Finding the port of the Radboud Buttonbox and checking its port settings:
the latency timer (BITSI 2015), the COM port number and the FIFO buffers
(Windows) and ModemManager (BITSI 2018, Linux). Ported from the init item
of opensesame-plugin-radboudbox 7.0.1, without OpenSesame.
"""

__author__ = "Bob Rosbag"
__license__ = "GPL-3.0-or-later"

import os
import re
import sys

from psychopy import logging


class RadboudboxError(Exception):
    """An error the user must understand: a wrong setting, a missing box,
    or wrong port settings.
    """


# USB vendor ids of the boards in the buttonboxes: FTDI (USB UART of the
# Arduino Duemilanove, BITSI 2015), Arduino and Teensy (BITSI 2018)
BUTTONBOX_VENDOR_IDS = {0x0403, 0x2341, 0x2A03, 0x16C0}

FTDI_VENDOR_ID = 0x0403
# The FTDI chip sends small amounts of data after its latency timer (ms)
LATENCY_TIMER_MAX = 1
SYSFS_USB_SERIAL = '/sys/bus/usb-serial/devices'

# The FTDI driver keeps the Advanced port settings of a COM port (BITSI
# 2015) in the Device Parameters of its FTDIBUS key. ConfigData holds the
# USB transfer sizes: byte 2 transmit, byte 3 receive, as (size / 64) - 1
REGISTRY_FTDIBUS = r'SYSTEM\CurrentControlSet\Enum\FTDIBUS'
FTDI_SETTINGS = {'RxTransferSize': 64, 'TxTransferSize': 64,
                 'LatencyTimer': LATENCY_TIMER_MAX, 'MinReadTimeout': 0,
                 'MinWriteTimeout': 0}
FTDI_SETTING_NAMES = {'RxTransferSize': 'Receive (Bytes)',
                      'TxTransferSize': 'Transmit (Bytes)',
                      'LatencyTimer': 'Latency Timer (msec)',
                      'MinReadTimeout': 'Minimum Read Timeout (msec)',
                      'MinWriteTimeout': 'Minimum Write Timeout (msec)'}
# A setting that isn't in the registry: the driver's default
FTDI_SETTING_DEFAULTS = {'RxTransferSize': 4096, 'TxTransferSize': 4096,
                         'LatencyTimer': 16, 'MinReadTimeout': 0,
                         'MinWriteTimeout': 0}

# Windows keeps the Advanced port settings of a USB serial port (usbser.sys,
# BITSI 2018) in its Device Parameters. Required: Use FIFO buffers off,
# receive and transmit buffer Low (1)
REGISTRY_USB = r'SYSTEM\CurrentControlSet\Enum\USB'
FIFO_SETTINGS = {'ForceFifoEnable': 0, 'RxFIFO': 1, 'TxFIFO': 1}
FIFO_SETTING_NAMES = {'ForceFifoEnable': 'Use FIFO buffers',
                      'RxFIFO': 'Receive Buffer',
                      'TxFIFO': 'Transmit Buffer'}
# A setting that was never changed in the Device Manager isn't in the
# registry: its default (Use FIFO buffers on, buffers High)
FIFO_SETTING_DEFAULTS = {'ForceFifoEnable': 1, 'RxFIFO': 14, 'TxFIFO': 16}

# Our lab setting for the buttonbox port on Windows: COM1-COM9
COM_NUMBER_MAX = 9
COM_NUMBER_FIX = ('Device Manager, Ports, {port}, Properties, Port '
                  'Settings, Advanced, COM Port Number: a free number below '
                  '10')

PORT_SETTINGS_CURRENT = (
    'The port settings of the Radboud Buttonbox on {port} are wrong:\n\n'
    'Current settings are:\n\n'
    '{current}\n\n')
PORT_SETTINGS_MESSAGE = PORT_SETTINGS_CURRENT + (
    'Please go to:\n\n'
    '    Device Manager > Ports (COM & LPT) > {device} > Port Settings > '
    'Advanced\n\n'
    '{fix}')
PORT_SETTINGS_FIX_2018 = (
    'Set the following when incorrect, the order is important!\n\n'
    '1. First set "COM Port Number" to a COM port below 10.\n'
    '2. Then set both "Receive Buffer" and "Transmit Buffer" to "Low (1)", '
    'by moving the sliders all the way to the left.\n'
    '3. Finally, uncheck "Use FIFO buffers".\n\n'
    'Now you should see:\n\n'
    '    Port: COM3 (or another COM port below 10)\n'
    '    Use FIFO buffers: off\n'
    '    Receive Buffer: Low (1)\n'
    '    Transmit Buffer: Low (1)')
PORT_SETTINGS_FIX_2015 = (
    'Set the following when incorrect:\n\n'
    '    Port: COM3 (or another COM port below 10)\n'
    '    Receive (Bytes): 64\n'
    '    Transmit (Bytes): 64\n'
    '    Latency Timer (msec): 1\n'
    '    Minimum Read Timeout (msec): 0\n'
    '    Minimum Write Timeout (msec): 0\n\n'
    'Leave the other settings as they are.')

# Linux: the latency timer of the BITSI 2015 is in sysfs, written by the
# ftdi_sio driver; the chip starts at 16 ms when it is connected
PORT_SETTINGS_MESSAGE_LINUX = PORT_SETTINGS_CURRENT + (
    'Please run:\n\n'
    '    echo 1 | sudo tee {sysfs}\n\n'
    'This lasts until the box is disconnected. To set it permanently, add '
    'a udev rule, then disconnect and reconnect the box:\n\n'
    '    echo \'ACTION=="add", SUBSYSTEM=="usb-serial", DRIVER=="ftdi_sio", '
    'ATTR{{latency_timer}}="1"\' | sudo tee '
    '/etc/udev/rules.d/99-ftdi-latency-timer.rules\n'
    '    sudo udevadm control --reload-rules\n\n'
    'Now you should see:\n\n'
    '    cat {sysfs}\n'
    '    1')

# Linux: ModemManager probes a new cdc_acm port whose interface says it
# takes modem (AT) commands (protocol 1-6), as the Teensy (BITSI 2018) does.
# It ignores a device with ID_MM_DEVICE_IGNORE=1, set by udev rules; udev
# keeps the properties of each device in /run/udev/data/c<major>:<minor>
PROC = '/proc'
SYSFS_TTY = '/sys/class/tty'
UDEV_DATA = '/run/udev/data'
MODEM_MANAGER_WARNING = (
    'ModemManager is running and may use the Radboud Buttonbox on {port}: '
    'when the box is connected, ModemManager can open its port and send '
    'modem commands to it. To make ModemManager ignore the box, run:\n\n'
    '    echo \'ATTRS{{idVendor}}=="{vid:04x}", '
    'ENV{{ID_MM_DEVICE_IGNORE}}="1", '
    'ENV{{ID_MM_PORT_IGNORE}}="1"\' | sudo tee '
    '/etc/udev/rules.d/99-radboudbox-modemmanager.rules\n'
    '    sudo udevadm control --reload-rules\n\n'
    'then disconnect and reconnect the box. For a Teensy, the udev rules '
    'of PJRC (https://www.pjrc.com/teensy/00-teensy.rules) do the same. Or '
    'remove ModemManager when you don\'t use a modem.')

WRONG_PORT_SETTINGS_WARNING = (
    '\n\nWrong port settings is set to warning: the experiment continues.')

# Names of the port information that PortCheck collects (the
# radboudbox_<name> log variables of the OpenSesame plugin). None is
# unknown; 'NA' for settings that the box or the system doesn't have
PORT_INFO_NAMES = (
    'type', 'port', 'driver', 'id_string', 'port_settings',
    'latency_timer', 'receive_bytes', 'transmit_bytes', 'min_read_timeout',
    'min_write_timeout',
    'use_fifo_buffers', 'receive_buffer', 'transmit_buffer', 'modemmanager')
FTDI_INFO_NAMES = {'LatencyTimer': 'latency_timer',
                   'RxTransferSize': 'receive_bytes',
                   'TxTransferSize': 'transmit_bytes',
                   'MinReadTimeout': 'min_read_timeout',
                   'MinWriteTimeout': 'min_write_timeout'}
FIFO_INFO_NAMES = {'ForceFifoEnable': 'use_fifo_buffers',
                   'RxFIFO': 'receive_buffer',
                   'TxFIFO': 'transmit_buffer'}


def com_number(port):
    """Returns the number of a Windows COM port (COM12 or \\\\.\\COM12),
    or None for another name.
    """
    match = re.fullmatch(r'(?:\\\\\.\\)?COM(\d+)', port, re.IGNORECASE)
    return None if match is None else int(match.group(1))


def device_manager_name(info, default):
    """The name of a port in the Device Manager, e.g. USB Serial Device
    (COM4): pyserial's description is the device's friendly name.
    """
    if info.description and info.device in info.description:
        return info.description
    return f'{default} ({info.device})'


def port_settings_lines(settings):
    """Lines of (name, value, correct) for the error; correct is None when
    the setting could not be read.
    """
    return '\n'.join(
        f'    {name}: {value}' + (
            '' if correct is None
            else f' ({"correct" if correct else "incorrect"})')
        for name, value, correct in settings)


def modem_manager_running():
    """Whether a ModemManager process runs."""
    try:
        pids = [pid for pid in os.listdir(PROC) if pid.isdigit()]
    except OSError:
        return False
    for pid in pids:
        try:
            with open(os.path.join(PROC, pid, 'comm')) as f:
                if f.read().strip() == 'ModemManager':
                    return True
        except OSError:
            continue
    return False


def probed_by_modem_manager(port):
    """Whether ModemManager would probe the port: the protocol of its USB
    interface says modem (AT) commands (1-6). False when that can't be read.
    """
    tty = os.path.join(SYSFS_TTY, os.path.basename(os.path.realpath(port)))
    interface = os.path.dirname(os.path.dirname(os.path.realpath(tty)))
    try:
        with open(os.path.join(interface, 'bInterfaceProtocol')) as f:
            return 1 <= int(f.read(), 16) <= 6
    except (OSError, ValueError):
        return False


def ignored_by_modem_manager(port):
    """Whether udev set ID_MM_DEVICE_IGNORE=1 on the port's tty or on the
    USB device above it.
    """
    path = os.path.realpath(os.path.join(
        SYSFS_TTY, os.path.basename(os.path.realpath(port))))
    while path not in ('/', '/sys', '/sys/devices', ''):
        try:
            with open(os.path.join(path, 'dev')) as f:
                device_id = f'c{f.read().strip()}'
            with open(os.path.join(UDEV_DATA, device_id)) as f:
                if 'E:ID_MM_DEVICE_IGNORE=1' in f.read().splitlines():
                    return True
        except OSError:
            pass
        path = os.path.dirname(path)
    return False


def usb_port_info():
    """Returns a function that gives pyserial's information on a port (also
    through a symbolic link), or None.
    """
    from serial.tools import list_ports
    usb_info = {}
    for info in list_ports.comports():
        usb_info[info.device] = info
        usb_info[os.path.realpath(info.device)] = info
    return lambda port: usb_info.get(port,
                                     usb_info.get(os.path.realpath(port)))


def list_buttonbox_ports():
    """The ports of the connected buttonboxes (by USB vendor id), with
    pyserial's information. Never raises: Builder calls it to list the
    available devices.
    """
    try:
        from serial.tools import list_ports
        return [info for info in list_ports.comports()
                if info.vid in BUTTONBOX_VENDOR_IDS]
    except Exception as e:
        logging.warning(f'Could not list the serial ports: {e}')
        return []


def box_type(vid):
    """BITSI 2015 or BITSI 2018 by the USB vendor id, or None."""
    if vid == FTDI_VENDOR_ID:
        return 'BITSI 2015'
    if vid in BUTTONBOX_VENDOR_IDS:
        return 'BITSI 2018'
    return None


def read_latency_timer(info):
    """Returns the latency timer (ms) of an FTDI port on Linux and where it
    is set, or None for the timer when it can't be read.
    """
    if sys.platform.startswith('linux'):
        path = os.path.join(SYSFS_USB_SERIAL, os.path.basename(info.device),
                            'latency_timer')
        try:
            with open(path) as f:
                return int(f.read()), path
        except (OSError, ValueError):
            return None, path
    return None, sys.platform


def is_usb_device(info):
    """Returns is_device() for find_port_key() under Enum\\USB."""
    def is_device(device, instance):
        return info.pid is not None and info.serial_number is not None \
            and device.upper() == f'VID_{info.vid:04X}&PID_{info.pid:04X}' \
            and instance.upper() == info.serial_number.upper()
    return is_device


def is_ftdibus_device(info):
    """Returns is_device() for find_port_key() under Enum\\FTDIBUS: the
    serial number is in the device name.
    """
    def is_device(device, instance):
        return info.pid is not None and info.serial_number is not None \
            and device.upper() == (f'VID_{info.vid:04X}+PID_{info.pid:04X}+'
                                   f'{info.serial_number}').upper()
    return is_device


def find_port_key(path, prefix, info, is_device):
    """Returns the registry key of a port: the instance under path (HKLM,
    <device>/<instance>, device names that start with prefix) whose
    Device Parameters have the port as PortName. Windows keeps the keys of
    devices that were connected before, and several can have the same
    PortName: then is_device(device, instance) chooses the connected one.
    Returns None when the port isn't found or can't be told apart.
    """
    import winreg
    try:
        bus = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path)
        devices = [winreg.EnumKey(bus, i)
                   for i in range(winreg.QueryInfoKey(bus)[0])]
    except OSError:
        return None
    found = []
    for name in devices:
        if not name.upper().startswith(prefix):
            continue
        try:
            device = winreg.OpenKey(bus, name)
            instances = [winreg.EnumKey(device, j)
                         for j in range(winreg.QueryInfoKey(device)[0])]
        except OSError:
            continue
        for instance in instances:
            try:
                parameters = winreg.OpenKey(
                    device, instance + r'\Device Parameters')
                port_name = winreg.QueryValueEx(parameters, 'PortName')[0]
            except OSError:
                continue
            if port_name.upper() == info.device.upper():
                found.append((name, instance, device))
    if len(found) > 1:
        found = [key for key in found if is_device(key[0], key[1])]
    if len(found) != 1:
        return None
    try:
        return winreg.OpenKey(found[0][2], found[0][1])
    except OSError:
        return None


def find_port_parameters(path, prefix, info, is_device):
    """Returns the Device Parameters key of a port, or None."""
    import winreg
    key = find_port_key(path, prefix, info, is_device)
    if key is None:
        return None
    try:
        return winreg.OpenKey(key, 'Device Parameters')
    except OSError:
        return None


def read_ftdi_settings_windows(info):
    """Returns the settings of an FTDI COM port from the registry (the
    default for a value that isn't there, None for transfer sizes that
    can't be read), or None when the port isn't found.
    """
    import winreg
    parameters = find_port_parameters(REGISTRY_FTDIBUS, f'VID_{info.vid:04X}+',
                                      info, is_ftdibus_device(info))
    if parameters is None:
        return None
    settings = dict(FTDI_SETTING_DEFAULTS)
    for setting in ('LatencyTimer', 'MinReadTimeout', 'MinWriteTimeout'):
        try:
            settings[setting] = winreg.QueryValueEx(parameters, setting)[0]
        except OSError:
            pass
    try:
        config = winreg.QueryValueEx(parameters, 'ConfigData')[0]
    except OSError:
        config = None
    if config is not None:
        if isinstance(config, bytes) and len(config) >= 4:
            settings['TxTransferSize'] = (config[2] + 1) * 64
            settings['RxTransferSize'] = (config[3] + 1) * 64
        else:
            settings['TxTransferSize'] = settings['RxTransferSize'] = None
    return settings


def read_fifo_settings_windows(info):
    """Returns the FIFO settings of a USB serial port from the registry
    (the default for a value that isn't set), or None when the port isn't
    found.
    """
    import winreg
    parameters = find_port_parameters(REGISTRY_USB, f'VID_{info.vid:04X}&',
                                      info, is_usb_device(info))
    if parameters is None:
        return None
    settings = {}
    for setting in FIFO_SETTINGS:
        try:
            settings[setting] = winreg.QueryValueEx(parameters, setting)[0]
        except OSError:
            settings[setting] = FIFO_SETTING_DEFAULTS[setting]
    return settings


def read_driver(info):
    """Returns the name of the port's driver (e.g. ftdi_sio or cdc_acm on
    Linux, FTSER2K or usbser on Windows), or None.
    """
    if sys.platform.startswith('linux'):
        driver = os.path.join(SYSFS_TTY,
                              os.path.basename(os.path.realpath(info.device)),
                              'device', 'driver')
        if not os.path.exists(driver):
            return None
        return os.path.basename(os.path.realpath(driver))
    if sys.platform != 'win32':
        return None
    import winreg
    if info.vid == FTDI_VENDOR_ID:
        key = find_port_key(REGISTRY_FTDIBUS, f'VID_{info.vid:04X}+', info,
                            is_ftdibus_device(info))
    else:
        key = find_port_key(REGISTRY_USB, f'VID_{info.vid:04X}&', info,
                            is_usb_device(info))
    if key is None:
        return None
    try:
        return str(winreg.QueryValueEx(key, 'Service')[0])
    except OSError:
        return None


def find_port(ports, device_id):
    """Chooses a port from rusocsci's list of USB serial devices (the
    device connected last first). rusocsci takes any device, e.g. the
    serial port of an audio interface, so the USB vendor id is checked.
    device_id None takes the first buttonbox, or else the first port
    without USB data (it can't be checked); a device id takes that
    position.
    """
    # On Windows, rusocsci returns the port names as bytes
    ports = [p.decode() if isinstance(p, bytes) else p for p in ports]
    info = usb_port_info()

    def is_other_device(port):
        return info(port) is not None and info(port).vid is not None \
            and info(port).vid not in BUTTONBOX_VENDOR_IDS

    def describe(ports):
        return ', '.join(
            f'{p} ({info(p).description}, {info(p).hwid})'
            if info(p) is not None else p for p in ports) or 'none'

    boxes = [p for p in ports if not is_other_device(p)]
    others = [p for p in ports if is_other_device(p)]
    if not ports:
        raise RadboudboxError('Could not find the Radboud Buttonbox: no USB '
                              'serial device found')
    if device_id is None:
        if boxes:
            return boxes[0]
        raise RadboudboxError(
            f'Could not find the Radboud Buttonbox. Other USB serial '
            f'devices: {describe(others)}')
    if not -len(ports) <= device_id < len(ports):
        raise RadboudboxError(
            f'Could not find the Radboud Buttonbox: no USB serial device '
            f'with device id {device_id} (0 is the device connected last). '
            f'USB serial devices: {describe(ports)}')
    port = ports[device_id]
    if is_other_device(port):
        raise RadboudboxError(
            f'Could not find the Radboud Buttonbox: device id {device_id} '
            f'is another USB device: {describe([port])}. Buttonboxes: '
            f'{describe(boxes)}')
    return port


class PortCheck:
    """Checks the settings of the buttonbox port. wrong_port_settings is
    'error' (raise RadboudboxError) or 'warning' (log it and go on).
    The results are in self.info (see PORT_INFO_NAMES).
    """

    def __init__(self, wrong_port_settings='error'):
        self.wrong_port_settings = wrong_port_settings
        self.info = dict.fromkeys(PORT_INFO_NAMES, 'NA')

    def _set(self, name, value):
        self.info[name] = value

    def check(self, port):
        """The latency timer (FTDI), and on Windows our lab settings (COM
        number, and for the BITSI 2018 the FIFO buffers). On Linux, a
        warning when ModemManager may use the BITSI 2018.
        """
        info = usb_port_info()(port)
        self._set('port', port if info is None else info.device)
        self._set('driver', None if info is None else read_driver(info))
        if info is not None and info.vid == FTDI_VENDOR_ID:
            self._set('type', 'BITSI 2015')
            self._check_latency_timer(port, info)
        elif info is not None and info.vid in BUTTONBOX_VENDOR_IDS:
            self._set('type', 'BITSI 2018')
            if sys.platform == 'win32':
                self._check_fifo_settings(port, info)
            elif sys.platform.startswith('linux'):
                # No port settings on Linux (cdc_acm)
                self._set('port_settings', 'correct')
                self._check_modem_manager(port, info)
            else:
                self._set('port_settings', None)
        else:
            self._set('type', None)
            self._check_com_number(port)

    def _status(self, settings):
        """Sets whether the settings (name, value, correct) are correct, and
        returns True when one of them is incorrect.
        """
        corrects = [correct for _, _, correct in settings]
        if False in corrects:
            status = 'incorrect'
        elif None in corrects:
            status = None
        else:
            status = 'correct'
        self._set('port_settings', status)
        return status == 'incorrect'

    def _wrong(self, message):
        if self.wrong_port_settings == 'warning':
            logging.warning(message + WRONG_PORT_SETTINGS_WARNING)
            return
        raise RadboudboxError(message)

    def _check_modem_manager(self, port, info):
        if not modem_manager_running():
            self._set('modemmanager', 'not running')
            return
        if not probed_by_modem_manager(port) \
                or ignored_by_modem_manager(port):
            self._set('modemmanager', 'does not use the box')
            return
        self._set('modemmanager', 'may use the box')
        logging.warning(MODEM_MANAGER_WARNING.format(port=info.device,
                                                     vid=info.vid))

    def _port_row(self, info):
        number = com_number(info.device)
        return 'Port', info.device, number is None or \
            number <= COM_NUMBER_MAX

    def _check_latency_timer(self, port, info):
        """The FTDI chip of the BITSI 2015 box sends small amounts of data
        after its latency timer: 16 ms by default, so button presses can
        arrive up to 16 ms late. It should be 1 ms.
        """
        if sys.platform == 'win32':
            self._check_ftdi_settings(port, info)
            return
        latency, where = read_latency_timer(info)
        self._set('latency_timer', latency)
        if latency is None:
            self._set('port_settings', None)
            logging.warning(
                f'Could not read the latency timer of the FTDI port {port} '
                f'({where}): it should be {LATENCY_TIMER_MAX} ms, otherwise '
                f'button presses can arrive up to 16 ms late')
            return
        settings = [('Latency Timer (msec)', latency,
                     latency <= LATENCY_TIMER_MAX)]
        if self._status(settings):
            self._wrong(PORT_SETTINGS_MESSAGE_LINUX.format(
                port=info.device, sysfs=where,
                current=port_settings_lines(settings)))

    def _check_ftdi_settings(self, port, info):
        ftdi = read_ftdi_settings_windows(info)
        device = device_manager_name(info, 'USB Serial Port')
        if ftdi is None:
            logging.warning(
                f'Could not read the settings of the FTDI port {port} from '
                f'the registry: its key was not found or could not be read, '
                f'or several keys have this port name and the connected box '
                f'could not be told apart. The latency timer should be '
                f'{LATENCY_TIMER_MAX} ms, otherwise button presses can arrive '
                f'up to 16 ms late (Device Manager > Ports (COM & LPT) > '
                f'{device} > Port Settings > Advanced)')
        settings = [self._port_row(info)]
        for setting, required in FTDI_SETTINGS.items():
            value = None if ftdi is None else ftdi[setting]
            self._set(FTDI_INFO_NAMES[setting], value)
            if value is None:
                settings.append((FTDI_SETTING_NAMES[setting],
                                 'could not be read', None))
                continue
            if setting == 'LatencyTimer':
                correct = isinstance(value, int) and 1 <= value <= required
            else:
                correct = value == required
            settings.append((FTDI_SETTING_NAMES[setting], value, correct))
        if self._status(settings):
            self._wrong(PORT_SETTINGS_MESSAGE.format(
                port=info.device, current=port_settings_lines(settings),
                device=device, fix=PORT_SETTINGS_FIX_2015))

    def _check_fifo_settings(self, port, info):
        fifo = read_fifo_settings_windows(info)
        device = device_manager_name(info, 'USB Serial Device')
        if fifo is None:
            logging.warning(
                f'Could not read the FIFO settings of the Radboud Buttonbox '
                f'port {port}: its registry key was not found or could not '
                f'be read, or several keys have this port name and the '
                f'connected box could not be told apart. They should be: '
                f'Use FIFO buffers off, Receive Buffer and Transmit Buffer '
                f'Low (1) (Device Manager > Ports (COM & LPT) > {device} > '
                f'Port Settings > Advanced)')
        settings = [self._port_row(info)]
        for setting in FIFO_SETTINGS:
            if fifo is None:
                self._set(FIFO_INFO_NAMES[setting], None)
                settings.append((FIFO_SETTING_NAMES[setting],
                                 'could not be read', None))
                continue
            value = fifo[setting]
            if setting == 'ForceFifoEnable':
                shown = {0: 'off', 1: 'on'}.get(value, value)
            else:
                shown = 'Low (1)' if value == 1 else value
            self._set(FIFO_INFO_NAMES[setting],
                      shown if setting == 'ForceFifoEnable' else value)
            settings.append((FIFO_SETTING_NAMES[setting], shown,
                             value == FIFO_SETTINGS[setting]))
        if self._status(settings):
            self._wrong(PORT_SETTINGS_MESSAGE.format(
                port=info.device, current=port_settings_lines(settings),
                device=device, fix=PORT_SETTINGS_FIX_2018))

    def _check_com_number(self, port):
        """A COM number below 10 on Windows, also when it isn't known which
        box it is.
        """
        self._set('port_settings', None)
        if sys.platform != 'win32':
            return
        number = com_number(port)
        if number is None or number <= COM_NUMBER_MAX:
            return
        self._set('port_settings', 'incorrect')
        name = f'COM{number}'
        self._wrong(
            f'The Radboud Buttonbox is on port {name}: the COM number must '
            f'be below 10. {COM_NUMBER_FIX.format(port=name)}')
