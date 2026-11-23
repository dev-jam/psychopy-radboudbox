# Code component of the demo (tools/build_demo.py puts it in the .psyexp)
beep_onset = None
ptb_status = None
# Note the moment the Sound component calls beep.play(): the latency is
# measured from there, on the clock of this Routine (the clock of
# soundSensor.times), and on Psychtoolbox's clock
if not getattr(beep, '_timed_play', False):
    _beep_play = beep.play

    def _timed_play(*args, **kwargs):
        play_calls['play_call'] = (routineTimer.getTime(), ptb_now(),
                                    kwargs.get('when') is not None)
        return _beep_play(*args, **kwargs)
    beep.play = _timed_play
    beep._timed_play = True
play_calls['play_call'] = None
# Without the hamming ramp (Experiment info: hamming no) the beep starts at
# full volume: the Sound component loaded it with the ramp just before this
if not hamming_on:
    beep.setSound(sound_file, hamming=False)
