# Code component of the demo (tools/build_demo.py puts it in the .psyexp)
# The latency from the play() call (as the OpenSesame tester measures from
# the sampler), and where that time went: to the flip, to Psychtoolbox's
# start, and from there to the box
timing = beep_timing(play_calls['play_call'], beep_onset,
                     soundSensor.times if soundSensor.times != [] else None,
                     ptb_status)
audio_latency = timing['audio_latency']
if audio_latency is not None:
    tester.latencies.append(audio_latency)
else:
    # No S within the timeout: not a latency
    tester.n_timeouts += 1
tester.n_trials += 1
statistics = latency_statistics()
for _name, _value in timing.items():
    if _name != 'audio_latency':
        thisExp.addData(_name, _value)
update_session_timer(core.getTime())

thisExp.addData('audio_latency', audio_latency)
thisExp.addData('beep_onset', beep_onset)
thisExp.addData('n_trials', tester.n_trials)
thisExp.addData('n_timeouts', tester.n_timeouts)
for _name, _value in statistics.items():
    thisExp.addData(_name, _value)
# The rate of the audio stream: the file is resampled to it
thisExp.addData('speaker_sample_rate',
                getattr(getattr(beep, 'speaker', None), 'sampleRateHz', None))
thisExp.addData('beeps_done', tester.beeps_done)
thisExp.addData('time_passed', tester.time_passed)
thisExp.addData('time_left', tester.time_left)

status = (f'Beep {tester.beeps_done} of {tester.beeps_total} - time '
          f'passed: {tester.time_passed}, time left: {tester.time_left}')
if verbose:
    print(f'Audio latency: {audio_latency} ms')
    print(status)
if feedback_on:
    feedback_text = (
        f'Condition:\n\nBit depth: {bit_depth}bit\nChannels: {nchannels}\n'
        f'Sample rate: {sample_rate} Hz\n\n'
        f'Current audio latency (from play): {audio_latency} ms\n'
        f'Play to flip: {timing["play_to_flip"]} ms, Psychtoolbox start '
        f'after play: {timing["ptb_start_after_play"]} ms\n\n'
        f'Audio latency:\n'
        f'Mean: {statistics["latency_mean"]} ± {statistics["latency_std"]} ms\n'
        f'Min: {statistics["latency_min"]} ms\n'
        f'Max: {statistics["latency_max"]} ms\n'
        f'Range: {statistics["latency_range"]} ms\n'
        f'RMS S2S: {statistics["latency_rms"]} ms\n\n'
        f'n = {tester.n_trials} (timeouts: {tester.n_timeouts})\n\n'
        f'Time passed: {tester.time_passed}\n'
        f'Time left: {tester.time_left} (beep {tester.beeps_done} of '
        f'{tester.beeps_total})')
else:
    feedback_text = status
summary_text = (f'Done!\n\nLast condition: mean {statistics["latency_mean"]} ± '
                f'{statistics["latency_std"]} ms, n = {tester.n_trials}, '
                f'timeouts: {tester.n_timeouts}\n\nPress a key to quit')
