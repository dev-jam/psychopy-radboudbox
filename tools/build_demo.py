"""
Build the demo experiment demo/radboudbox_latency_audio_tester.psyexp with
PsychoPy's Builder API: the PsychoPy version of the audio latency tester
(default sampler) of the lab-validation-toolbox. The code of its Code
components is in tools/demo_code/. Needs PsychoPy and this plugin
installed.

Run from the repository root: python tools/build_demo.py

SPDX-License-Identifier: GPL-3.0-or-later
"""

from pathlib import Path

from psychopy import experiment, plugins
from psychopy.experiment.components.code import CodeComponent
from psychopy.experiment.components.keyboard import KeyboardComponent
from psychopy.experiment.components.sound import SoundComponent
from psychopy.experiment.components.soundsensor import SoundSensorComponent
from psychopy.experiment.components.text import TextComponent
from psychopy.experiment.loops import TrialHandler

plugins.scanPlugins()
assert plugins.loadPlugin('psychopy-radboudbox')
from psychopy_radboudbox.components import RadboudboxControlComponent  # noqa

ROOT = Path(__file__).resolve().parent.parent
DEMO = ROOT / 'demo'
CODE = ROOT / 'tools' / 'demo_code'
DEVICE = 'soundkey'

exp = experiment.Experiment()
exp.name = 'radboudbox_latency_audio_tester'
settings = exp.settings.params
settings['expName'].val = 'radboudbox_latency_audio_tester'
settings['Full-screen window'].val = False
settings['Window size (pixels)'].val = [1280, 720]
settings['color'].val = 'black'
settings['Units'].val = 'height'
settings['Save csv file'].val = False
settings['Save wide csv file'].val = True
settings['Save excel file'].val = False
settings['Save psydat file'].val = False
settings['Save log file'].val = True
# participant and session only
settings['Experiment info'].val = "{'participant': '0', 'session': '001'}"


def text(exp, routine, name, value, stop='', height=0.035, update='constant'):
    component = TextComponent(exp, routine, name=name, text=value,
                              stopVal=stop, letterHeight=height,
                              font='Noto Sans Mono', color='white')
    component.params['text'].updates = update
    return component


def question(name, value, keys=''):
    """A Routine with a text, ended by a key (allowed keys: keys)."""
    routine = experiment.routines.Routine(name, exp)
    exp.addRoutine(name, routine)
    routine.addComponent(text(exp, name, f'{name}Text', value))
    routine.addComponent(KeyboardComponent(
        exp, name, name=f'{name}Key', allowedKeys=keys, store='last key',
        forceEndRoutine=True, stopVal=''))
    return routine


flow = []

# --- Begin experiment: statistics, session timer, system information ---
welcome = question('welcome', 'Welcome at the audio latency tester\n\n'
                   'Press a key to continue')
welcome.addComponent(CodeComponent(exp, 'welcome', name='setup', beginExp=(
    (CODE / 'begin_experiment.py').read_text())))
flow.append(welcome)

feedback_question = question(
    'feedback_question',
    'Do you want visual feedback on each trial?\n\n1: Yes\n2: No', "'1','2'")
feedback_question.addComponent(CodeComponent(
    exp, 'feedback_question', name='setFeedback',
    endRoutine="feedback_on = feedback_questionKey.keys == '1'"))
flow.append(feedback_question)

mode_question = question(
    'mode_question', 'Choose your N:\n\n1: 1\n2: 30\n3: 100\n4: 300',
    "'1','2','3','4'")
mode_question.addComponent(CodeComponent(
    exp, 'mode_question', name='setN',
    endRoutine="n = {'1': 1, '2': 30, '3': 100, '4': 300}"
               "[mode_questionKey.keys]"))
flow.append(mode_question)

flow.append(question('start_calibration',
                     'Press a key to start calibration\n\n(then be silent '
                     'for 1 s)'))

# Calibrate Sound: the text first, then 1 s of silence (the command waits)
calibration = experiment.routines.Routine('calibration', exp)
exp.addRoutine('calibration', calibration)
calibration.addComponent(text(exp, 'calibration', 'calibrationText',
                              'Starting calibration', stop=1.2))
calibration.addComponent(RadboudboxControlComponent(
    exp, 'calibration', name='calibrateSound', deviceLabel=DEVICE,
    command='Calibrate Sound', startVal=0.1, stopVal=''))
flow.append(calibration)

flow.append(question('start_experiment',
                     'Calibration done!\n\nPress a key to start test'))

# --- Conditions: the files of the OpenSesame tester ---
start_condition = experiment.routines.Routine('start_condition', exp)
exp.addRoutine('start_condition', start_condition)
start_condition.addComponent(CodeComponent(
    exp, 'start_condition', name='resetCondition',
    beginRoutine='begin_condition(n * len(conditions_loop.trialList))'))

trial = experiment.routines.Routine('trial', exp)
exp.addRoutine('trial', trial)
trial.addComponent(text(exp, 'trial', 'feedbackText', '$feedback_text',
                        height=0.03, update='set every repeat'))
trial.addComponent(SoundComponent(
    exp, 'trial', name='beep', sound='$sound_file', startVal=0, stopVal='',
    volume=1, syncScreenRefresh=True))
# Detection starts when it starts (Detect Sound); no response within 1 s:
# a timeout (the timeout of the OpenSesame tester)
trial.addComponent(SoundSensorComponent(
    exp, 'trial', name='soundSensor', deviceLabel=DEVICE, startVal=0,
    stopVal=1.0, forceEndRoutine=False, store='first', registerOn=True))
trial.addComponent(CodeComponent(
    exp, 'trial', name='latency',
    beginRoutine='beep_onset = None',
    eachFrame=(CODE / 'each_frame.py').read_text(),
    endRoutine=(CODE / 'end_routine.py').read_text()))

done = question('done', 'Done!\n\n$summary_text')
done.getComponentFromName('doneText').params['text'].updates = \
    'set every repeat'

trials = TrialHandler(exp, name='trials', loopType='sequential', nReps='n',
                      conditions=[], conditionsFile='', endPoints=[0, 1],
                      isTrials=True)
conditions = TrialHandler(
    exp, name='conditions_loop', loopType='sequential', nReps=1,
    conditions=[],
    conditionsFile='conditions.csv', endPoints=[0, 1], isTrials=False)

for routine in flow:
    exp.flow.addRoutine(routine, len(exp.flow))
first = len(exp.flow)
exp.flow.addRoutine(start_condition, first)
exp.flow.addRoutine(trial, first + 1)
exp.flow.addLoop(trials, startPos=first + 1, endPos=first + 2)
exp.flow.addLoop(conditions, startPos=first, endPos=first + 4)
exp.flow.addRoutine(done, len(exp.flow))

exp.saveToXML(str(DEMO / 'radboudbox_latency_audio_tester.psyexp'))
print(f"saved {DEMO / 'radboudbox_latency_audio_tester.psyexp'}")
