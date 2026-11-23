# Code component of the demo (tools/build_demo.py puts it in the .psyexp)
beep_onset = None
ptb_status = None
# Without the hamming ramp (Experiment info: hamming no) the beep starts at
# full volume: the Sound component loaded it with the ramp just before this
if not hamming_on:
    beep.setSound(sound_file, hamming=False)
