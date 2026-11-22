# Code component of the demo (tools/build_demo.py puts it in the .psyexp)
# The requested onset of the beep: the flip at which the Sound component
# plays it, on the clock of this Routine (the clock of soundSensor.times)
if beep_onset is None and beep.status == STARTED:
    beep_onset = tThisFlip
# Next trial when the beep has played and the box answered (or at the
# timeout of the Sound Sensor)
if beep.status == FINISHED and soundSensor.times != []:
    continueRoutine = False
