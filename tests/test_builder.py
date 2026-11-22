# Copyright (C) 2016-2026 Bob Rosbag <mail@bobrosbag.nl>
# SPDX-License-Identifier: GPL-3.0-or-later

"""Builder: an experiment with the plugin's device in a Button Box
component, a Trigger and a Control component; saved, loaded, compiled,
and run with the simulated box (needs a display: run under xvfb-run).
"""

import csv
import os
import subprocess
import sys
from pathlib import Path

import pytest
from psychopy import experiment, plugins, prefs
from psychopy.experiment.components.buttonBox import ButtonBoxComponent
from psychopy.experiment.components.code import CodeComponent
from psychopy.experiment.components.soundsensor import SoundSensorComponent
from psychopy.experiment.components.text import TextComponent

from psychopy_radboudbox.components import (RadboudboxButtonBoxBackend,
                                            RadboudboxControlComponent,
                                            RadboudboxSoundSensorBackend,
                                            RadboudboxTriggerComponent)

HERE = Path(__file__).parent

# As the app does: the components of a loaded experiment come from the
# entry points of the plugin
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

def press():
    # The experiment opens the box (1.1 s in rusocsci) and opens a window
    while box.port is None:
        time.sleep(0.01)
    time.sleep(2.5)
    box.press('V')
    time.sleep(0.1)
    box.press('B')
    time.sleep(0.2)
    box.press('b')
threading.Thread(target=press, daemon=True).start()
import runpy
try:
    runpy.run_path({script!r}, run_name='__main__')
except SystemExit:
    pass
print('WRITTEN', bytes(box.written))
'''


@pytest.fixture
def device_config(tmp_path, monkeypatch):
    backend = RadboudboxButtonBoxBackend({'deviceName': None})
    backend.name = 'radboudbox'
    backend.params['radboudboxPort'].val = '/dev/fakebox0'
    devices = dict(prefs.devices)
    monkeypatch.setattr(prefs, '_devices', devices, raising=False)
    devices['radboudbox'] = backend
    voice = RadboudboxSoundSensorBackend({'deviceName': None})
    voice.name = 'voicekey'
    voice.params['radboudboxPort'].val = '/dev/fakebox0'
    voice.params['radboudboxSensor'].val = 'voice'
    voice.params['radboudboxCalibrate'].val = False
    devices['voicekey'] = voice
    return backend


def make_experiment():
    exp = experiment.Experiment()
    exp.settings.params['Show info dlg'].val = False
    exp.settings.params['Full-screen window'].val = False
    exp.settings.params['Window size (pixels)'].val = [200, 200]
    exp.settings.params['Save csv file'].val = True
    routine = experiment.routines.Routine('trial', exp)
    exp.addRoutine('trial', routine)
    exp.flow.addRoutine(routine, 0)
    routine.addComponent(TextComponent(exp, 'trial', name='stim', text='X',
                                       stopVal=5))
    routine.addComponent(ButtonBoxComponent(
        exp, 'trial', name='buttonBox', deviceLabel='radboudbox', stopVal='',
        forceEndRoutine=True, store='first', allowedButtons='1',
        storeCorrect=True, correctAns='1'))
    routine.addComponent(RadboudboxTriggerComponent(
        exp, 'trial', name='trigger', deviceLabel='radboudbox', startData=7))
    routine.addComponent(RadboudboxControlComponent(
        exp, 'trial', name='analog', deviceLabel='radboudbox',
        command='Analog In 3'))
    routine.addComponent(SoundSensorComponent(
        exp, 'trial', name='voice', deviceLabel='voicekey', stopVal='',
        forceEndRoutine=False, store='all'))
    # The workaround of the README for buttonBox.rt
    routine.addComponent(CodeComponent(
        exp, 'trial', name='saveRt',
        endRoutine="thisExp.addData('buttonBox.rt', buttonBox.rt)"))
    return exp


def test_save_load_compile(tmp_path, device_config):
    exp = make_experiment()
    psyexp = tmp_path / 'radboudbox_test.psyexp'
    exp.saveToXML(str(psyexp))
    loaded = experiment.Experiment()
    loaded.loadFromXML(str(psyexp))
    # The first is the Routine settings
    trial = {c.name: c for c in loaded.routines['trial']}
    assert list(trial) == ['trial', 'stim', 'buttonBox', 'trigger', 'analog',
                           'voice', 'saveRt']
    assert str(trial['trigger'].params['startData'].val) == '7'
    assert trial['analog'].params['command'].val == 'Analog In 3'
    assert trial['buttonBox'].params['deviceLabel'].val == 'radboudbox'
    script = loaded.writeScript(str(psyexp))
    compile(script, 'radboudbox_test.py', 'exec')
    assert ("deviceClass='psychopy_radboudbox.radboudbox."
            "RadboudboxButtonGroup'") in script
    assert "port='/dev/fakebox0'" in script
    assert "sensor='voice'" in script
    assert 'win.callOnFlip(trigger.sendMarker, int(7))' in script
    assert "analog.sendCommand('Analog In 3')" in script


@pytest.mark.skipif(not os.environ.get('DISPLAY'),
                    reason='needs a display (xvfb-run)')
def test_run_experiment(tmp_path, device_config):
    exp = make_experiment()
    psyexp = tmp_path / 'radboudbox_test.psyexp'
    exp.saveToXML(str(psyexp))
    script = tmp_path / 'radboudbox_test.py'
    script.write_text(exp.writeScript(str(psyexp)))
    runner = tmp_path / 'runner.py'
    runner.write_text(RUNNER.format(tests=str(HERE), script=str(script)))
    result = subprocess.run([sys.executable, str(runner)], cwd=tmp_path,
                            capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stdout + result.stderr
    # Analog In 3 and Detect Voice at once (the voice key starts detection);
    # trigger 7 at the flip of the onset, 0 after 50 ms
    assert "WRITTEN b'A3DVM\\x07M\\x00'" in result.stdout, result.stdout
    data = list((tmp_path / 'data').glob('*.csv'))
    assert len(data) == 1
    with open(data[0], newline='') as f:
        row = list(csv.DictReader(f))[0]
    assert row['buttonBox.buttons'] == '1'
    assert row['buttonBox.corr'] == '1'
    assert row['analog.analogIn'] == '512'
    assert row['trigger.startData'] == '7'
    assert row['trigger.stopData'] == '0'
    # PsychoPy saves buttonBox.rt from an attribute it never fills ([]);
    # the Code component saves it. B was pressed about 2.5 s after the box
    # was opened, so later than the start of the Routine
    rt = float(row['buttonBox.rt'])
    # The voice key, 0.1 s before B
    voice_times = eval(row['voice.times'])
    assert len(voice_times) == 1
    assert 0.05 < rt - voice_times[0] < 0.2
    assert 0 < rt < float(row['trial.stopped'])
