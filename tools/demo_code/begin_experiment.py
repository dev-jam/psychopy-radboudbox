# Code component of the demo (tools/build_demo.py puts it in the .psyexp)
# Audio latency tester with the Radboud Buttonbox, the PsychoPy version of
# OpenSesame_-_latency_audio_tester_-_default_sampler_-_v12.4.osexp: the
# sound key of the box detects each beep (2000 Hz, 100 ms) and sends S.
#
# Audio latency = the time S arrived (Sound Sensor component, timestamped
# by the plugin on arrival) - the requested onset of the beep (the flip at
# which the Sound component plays it, play(when=win)). Both on the clock of
# the trial Routine.
import platform
import types

import numpy as np

verbose = False

# System information, in every row of the data file
os_version = {'Linux': lambda: platform.freedesktop_os_release().get(
                  'PRETTY_NAME', 'Linux'),
              'Darwin': lambda: f'macOS {platform.mac_ver()[0]}'}.get(
    platform.system(), lambda: f'{platform.system()} {platform.release()}')
try:
    os_version = os_version()
except OSError:
    os_version = platform.system()
thisExp.extraInfo['os_version'] = os_version
thisExp.extraInfo['kernel'] = platform.release()
thisExp.extraInfo['os_build'] = platform.version()
# The sound key of the box: a device of Device Manager, set up on each
# computer (it is not stored in the experiment)
soundkey = deviceManager.getDevice('soundkey')
if type(soundkey).__name__ != 'RadboudboxSoundSensorGroup':
    raise RuntimeError(
        "This demo needs a device 'soundkey' in Device Manager (Builder: "
        "Tools > Device Manager): add a device 'Radboud Buttonbox (BITSI) "
        "sound/voice key' with the label soundkey, Key: sound, Calibrate "
        "at the start: off (the demo calibrates after a key press). Found: "
        f"{type(soundkey).__name__ if soundkey is not None else 'no device'}")
# The box and its port settings (see the README of the plugin)
for _name, _value in soundkey.parent.portInfo.items():
    thisExp.extraInfo[f'radboudbox_{_name}'] = _value

feedback_on = False
feedback_text = ''
summary_text = ''
# The state of the tester: Builder runs this code inside a function, so
# the functions below change this object, not global variables
tester = types.SimpleNamespace(
    latencies=[], n_trials=0, n_timeouts=0, beeps_done=0, beeps_total=0,
    session_start=None, cycle_previous=None, cycle_total=0.0, cycle_count=0,
    time_passed='0:00:00', time_left='unknown')


def format_duration(seconds):
    seconds = int(round(seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f'{hours}:{minutes:02d}:{seconds:02d}'


def begin_condition(beeps_total):
    """Before the first trial of a condition."""
    tester.latencies = []
    tester.n_trials = 0
    tester.n_timeouts = 0
    if tester.session_start is None:
        # Start the session timer just before the first condition starts
        tester.beeps_total = beeps_total
        tester.session_start = core.getTime()


def update_session_timer(now):
    """Once per trial. All trials take about as long in PsychoPy: one audio
    stream for all conditions (the files are resampled to its rate), so
    the time left is the mean trial cycle times the beeps left.
    """
    tester.beeps_done += 1
    if tester.cycle_previous is not None:
        tester.cycle_total += now - tester.cycle_previous
        tester.cycle_count += 1
    tester.cycle_previous = now
    tester.time_passed = format_duration(now - tester.session_start)
    if tester.beeps_done >= tester.beeps_total:
        tester.time_left = format_duration(0)
    elif tester.cycle_count:
        tester.time_left = format_duration(
            (tester.beeps_total - tester.beeps_done) * tester.cycle_total
            / tester.cycle_count)


def latency_statistics():
    """Mean, stdev, RMS of successive differences (S2S), min, max, range
    (ms), as in the OpenSesame tester; empty for fewer than 2 latencies.
    """
    if len(tester.latencies) <= 1:
        return dict.fromkeys(('latency_mean', 'latency_std', 'latency_rms',
                              'latency_min', 'latency_max',
                              'latency_range'), '')
    latencies = np.array(tester.latencies)
    return {
        'latency_mean': round(float(np.mean(latencies)), 2),
        'latency_std': round(float(np.std(latencies, ddof=1)), 2),
        'latency_rms': round(float(np.sqrt(np.mean(np.diff(latencies) ** 2))),
                             2),
        'latency_min': round(float(np.min(latencies)), 2),
        'latency_max': round(float(np.max(latencies)), 2),
        'latency_range': round(float(np.ptp(latencies)), 2),
    }
