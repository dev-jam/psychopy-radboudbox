# Copyright (C) 2016-2026 Bob Rosbag <mail@bobrosbag.nl>
# SPDX-License-Identifier: GPL-3.0-or-later

"""The demo latency tester (demo/), compiled and run with the simulated
box, a fake sound (the box hears it LATENCY after the flip at which it is
played) and scripted keys. Needs a display: run under xvfb-run.
"""

import csv
import os
import shutil
import statistics
import subprocess
import sys
from pathlib import Path

import pytest
from psychopy import experiment, plugins, prefs

from psychopy_radboudbox.components import RadboudboxSoundSensorBackend

HERE = Path(__file__).parent
DEMO = HERE.parent / 'demo'
PSYEXP = 'radboudbox_latency_audio_tester.psyexp'
LATENCY = 0.008  # (s) from the flip of the beep to the S of the box
PTB_DELAY = 0.002  # (s) from the flip to the start Psychtoolbox reports

plugins.scanPlugins()
assert plugins.loadPlugin('psychopy-radboudbox')

RUNNER = '''
import sys, threading, time
sys.path.insert(0, {tests!r})
import serial
from conftest import FakeBox, FakeSerial
FakeSerial.boxes = {{'/dev/fakebox0': FakeBox()}}
serial.Serial = FakeSerial
box = FakeSerial.boxes['/dev/fakebox0']

from psychopy import core, gui, sound
from psychopy.hardware import keyboard
SOUND_CALLS = []  # the hamming argument of each setSound()


class FakeDialog:
    """The info dialog: OK with the defaults; a list is a choice, as in the
    real dialog (HAMMING picks the hamming one)."""
    OK = True

    def __init__(self, dictionary=None, **kwargs):
        self.dictionary = dictionary
        for key, value in dictionary.items():
            if isinstance(value, list):
                dictionary[key] = value[0]
        if {hamming!r} is not None:
            dictionary['hamming'] = {hamming!r}


gui.DlgFromDict = FakeDialog

# Answers: any key, feedback 1 (yes), N 2 (30 beeps per condition)
ANSWERS = {{None: 'space', ('1', '2'): '1', ('1', '2', '3', '4'): '2'}}
first_call = {{}}


def get_keys(self, keyList=None, ignoreKeys=None, waitRelease=True,
             clear=True):
    if keyList == ['escape']:
        return []
    key = ANSWERS[None if keyList is None else tuple(keyList)]
    start = first_call.setdefault(id(self), core.getTime())
    if core.getTime() - start < 0.2 or first_call.get((id(self), 'done')):
        return []
    first_call[(id(self), 'done')] = True
    press = keyboard.KeyPress(code=key, tDown=core.getTime(), name=key)
    press.rt = 0.2
    press.duration = None
    return [press]


keyboard.Keyboard.getKeys = get_keys


class FakeSpeaker:
    sampleRateHz = 48000


class FakeTrack:
    """The PsychPortAudio status of the track: Psychtoolbox starts the beep
    PTB_DELAY after the requested time (the flip)."""
    status = {{}}


class FakeSound:
    """The part of sound.Sound that the compiled experiment uses."""
    detections = 0

    def __init__(self, value='A', secs=0.1, **kwargs):
        self.status = None
        self.speaker = FakeSpeaker()
        self.track = FakeTrack()
        self.hamming_calls = []
        self.secs = 0.1
        self._end = None

    def setSound(self, value, secs=None, hamming=True, log=True):
        self.value = value
        self.hamming_calls.append(hamming)
        SOUND_CALLS.append(hamming)

    def setVolume(self, volume, log=True):
        pass

    def seek(self, t):
        pass

    def play(self, when=None, log=True):
        # On core.getTime(): the experiment sets the default clock (the
        # clock of getFutureFlipTime(clock=None)) to its own clock
        onset = core.getTime() + when.getFutureFlipTime(clock='now')
        requested = when.getFutureFlipTime(clock='ptb')
        self.track = FakeTrack()
        self.track.status = {{'RequestedStartTime': requested,
                             'StartTime': requested + {ptb_delay!r},
                             'PredictedLatency': 0.01, 'XRuns': 0}}
        self._end = onset + self.secs
        def detect():
            time.sleep(max(0, onset + {latency!r} - core.getTime()))
            # The box sends S once after each Detect Sound (the Sound
            # Sensor component sends it in the frame before the flip)
            if bytes(box.written).count(b'DS') > FakeSound.detections:
                FakeSound.detections += 1
                box.press('S')
        threading.Thread(target=detect, daemon=True).start()

    @property
    def isFinished(self):
        return self._end is not None and core.getTime() >= self._end

    def stop(self, log=True):
        pass

    def pause(self, log=True):
        pass


sound.Sound = FakeSound
import runpy
try:
    runpy.run_path({script!r}, run_name='__main__')
except SystemExit:
    pass
print('WRITTEN', bytes(box.written))
print('HAMMING', SOUND_CALLS.count(False))
'''


def run_demo(tmp_path, monkeypatch, device=True, hamming=None):
    """Compiles the demo and runs it with the fakes; returns the process
    result and the work folder. hamming: the choice in the info dialog
    (None: its default).
    """
    work = tmp_path / 'demo'
    shutil.copytree(DEMO, work)
    devices = dict(prefs.devices)
    if device:
        backend = RadboudboxSoundSensorBackend({'deviceName': None})
        backend.name = 'soundkey'
        backend.params['radboudboxPort'].val = '/dev/fakebox0'
        # The demo calibrates itself, after a key press
        backend.params['radboudboxCalibrate'].val = False
        devices['soundkey'] = backend
    monkeypatch.setattr(prefs, '_devices', devices, raising=False)
    exp = experiment.Experiment()
    exp.loadFromXML(str(work / PSYEXP))
    script = work / 'radboudbox_latency_audio_tester.py'
    script.write_text(exp.writeScript(str(work / PSYEXP)))
    runner = work / 'runner.py'
    runner.write_text(RUNNER.format(tests=str(HERE), script=str(script),
                                    latency=LATENCY, ptb_delay=PTB_DELAY,
                                    hamming=hamming))
    result = subprocess.run([sys.executable, str(runner)], cwd=work,
                            capture_output=True, text=True, timeout=300)
    return result, work


def read_rows(work):
    data = list((work / 'data').glob('*.csv'))
    assert len(data) == 1, data
    with open(data[0], newline='') as f:
        return [row for row in csv.DictReader(f) if row['audio_latency']]


@pytest.mark.skipif(not os.environ.get('DISPLAY'),
                    reason='needs a display (xvfb-run)')
def test_demo_latency_tester(tmp_path, monkeypatch):
    result, work = run_demo(tmp_path, monkeypatch)
    assert result.returncode == 0, result.stdout + result.stderr
    # The end screen shows the summary, not the text "$summary_text"
    # (Builder reads a text as code only when it starts with $)
    script = (work / 'radboudbox_latency_audio_tester.py').read_text()
    assert 'doneText.setText(summary_text)' in script
    written = result.stdout.split('WRITTEN ')[-1].split('\n')[0].strip()
    # Calibrate Sound once, then Detect Sound before each of the 180 beeps
    assert written == repr(b'CS' + b'DS' * 180), written
    # Hamming yes (the default): the beep is never loaded without the ramp
    assert 'HAMMING 0' in result.stdout
    rows = read_rows(work)
    assert len(rows) == 180
    latencies = [float(row['audio_latency']) for row in rows]
    # The simulated latency: never earlier (the onset is the flip of the
    # beep, on the clock of the times of the box), the median within 1 ms.
    # Later ones: the fake box thread and the reader thread both wait for
    # the CPU here (container: up to about 4 ms each)
    assert min(latencies) >= LATENCY * 1000
    assert abs(statistics.median(latencies) - LATENCY * 1000) < 1
    assert max(latencies) < LATENCY * 1000 + 20
    # Diagnostics: Psychtoolbox's start 2 ms after the flip, the rest of the
    # latency from there
    for row in rows:
        assert float(row['ptb_start_delay']) == pytest.approx(
            PTB_DELAY * 1000, abs=0.01)
        assert float(row['latency_from_ptb_start']) == pytest.approx(
            float(row['audio_latency']) - PTB_DELAY * 1000, abs=0.02)
        assert float(row['ptb_predicted_latency']) == 10
        assert float(row['ptb_xruns']) == 0
    last = rows[-1]
    assert last['sound_file'] == '2000Hz_-_32bit_-_2chan_-_192000Hz.wav'
    # Numbers as numbers: PsychoPy 2027.1 (dev) writes a column with empty
    # cells in other rows as floats (30.0), 2026.2 as written (30)
    assert float(last['n_trials']) == 30 and float(last['n_timeouts']) == 0
    assert float(last['latency_std']) < 5
    assert float(last['beeps_done']) == 180
    assert last['time_left'] == '0:00:00'
    assert float(last['speaker_sample_rate']) == 48000
    # extraInfo (participant, ..., the box, hamming): PsychoPy 2027.1 (dev,
    # at 6fdd52c) writes none of its columns to the data file
    if 'participant' in last:
        assert last['radboudbox_id_string'] == \
            'BITSI_extend mode, Ready! w:2018'
        assert last['hamming'] == 'yes'
    print(f'latency median {statistics.median(latencies):.2f} ms, '
          f'min {min(latencies):.2f}, max {max(latencies):.2f}')


@pytest.mark.skipif(not os.environ.get('DISPLAY'),
                    reason='needs a display (xvfb-run)')
def test_demo_without_hamming(tmp_path, monkeypatch):
    """hamming no in the info dialog: each beep is loaded again without the
    ramp, at the start of its trial.
    """
    result, work = run_demo(tmp_path, monkeypatch, hamming='no')
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'HAMMING 180' in result.stdout, result.stdout[-500:]
    rows = read_rows(work)
    assert len(rows) == 180
    if 'participant' in rows[-1]:
        assert rows[-1]['hamming'] == 'no'


@pytest.mark.skipif(not os.environ.get('DISPLAY'),
                    reason='needs a display (xvfb-run)')
def test_demo_without_soundkey_device(tmp_path, monkeypatch):
    """No device 'soundkey' in Device Manager (another computer): the demo
    says what to set up, instead of an AttributeError.
    """
    result, work = run_demo(tmp_path, monkeypatch, device=False)
    assert result.returncode != 0
    assert "needs a device 'soundkey' in Device Manager" in result.stderr, \
        result.stderr[-2000:]
    assert 'Found: no device' in result.stderr
