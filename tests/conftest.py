# Copyright (C) 2016-2026 Bob Rosbag <mail@bobrosbag.nl>
# SPDX-License-Identifier: GPL-3.0-or-later

"""A simulated Radboud Buttonbox: a fake pyserial port that rusocsci
opens. It sends the ID string after the DTR reset, records what is
written, answers Analog In, and sends characters when a test asks.
"""

import threading
import time

import pytest
import serial

ID_EXTENDED = 'BITSI_extend mode, Ready! w:2018'
ID_SIMPLE = 'BITSI mode, Ready!'
ID_2014 = 'BITSI_extend mode, Ready!'


class FakeBox:
    """The box behind one port name."""

    def __init__(self, id_string=ID_EXTENDED, analog_answer=b'512\r\n'):
        self.id_string = id_string
        self.analog_answer = analog_answer
        self.written = bytearray()
        self.port = None

    def press(self, characters):
        """The box sends characters (e.g. 'A', 'a', 'S')."""
        self.port.feed(characters.encode())

    def on_write(self, data):
        self.written += data
        # Analog In: 'A' and a channel digit
        if self.written[-2:-1] == b'A' and self.written[-1:] in b'1234' \
                and self.analog_answer is not None:
            self.port.feed(self.analog_answer)


class FakeSerial:
    """The part of serial.Serial that rusocsci and the plugin use."""

    boxes = {}

    def __init__(self, port, baudrate=9600, parity='N', timeout=None, **kw):
        if port not in self.boxes:
            raise serial.serialutil.SerialException(
                f'could not open port {port}: No such file or directory')
        self.box = self.boxes[port]
        self.box.port = self
        self.name = port
        self._timeout = timeout
        self._buffer = bytearray()
        self._condition = threading.Condition()
        self.is_open = True

    @property
    def timeout(self):
        return self._timeout

    @timeout.setter
    def timeout(self, value):
        self._timeout = value

    def feed(self, data):
        with self._condition:
            self._buffer += data
            self._condition.notify_all()

    def setDTR(self, value):
        # The box resets and sends its ID string
        if value and self.box.id_string is not None:
            self.feed(self.box.id_string.encode() + b'\r\n')

    def flushInput(self):
        with self._condition:
            self._buffer.clear()

    reset_input_buffer = flushInput

    @property
    def in_waiting(self):
        with self._condition:
            return len(self._buffer)

    def inWaiting(self):
        return self.in_waiting

    def read(self, size=1):
        end = None if self._timeout is None else \
            time.monotonic() + self._timeout
        with self._condition:
            while not self._buffer and self.is_open:
                rest = None if end is None else end - time.monotonic()
                if rest is not None and rest <= 0:
                    break
                self._condition.wait(rest)
            data = bytes(self._buffer[:size])
            del self._buffer[:size]
            return data

    def write(self, data):
        self.box.on_write(bytes(data))
        return len(data)

    def close(self):
        with self._condition:
            self.is_open = False
            self._condition.notify_all()


@pytest.fixture
def fake_box(monkeypatch):
    """Returns a function that connects a FakeBox to a port name."""
    FakeSerial.boxes = {}
    monkeypatch.setattr(serial, 'Serial', FakeSerial)

    def connect(port='/dev/fakebox0', **kwargs):
        box = FakeBox(**kwargs)
        FakeSerial.boxes[port] = box
        return box
    yield connect
    from psychopy.hardware.manager import DeviceManager
    DeviceManager.closeAll()
