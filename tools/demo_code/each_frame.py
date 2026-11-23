# Code component of the demo (tools/build_demo.py puts it in the .psyexp)
# The requested onset of the beep: the flip at which the Sound component
# plays it, on the clock of this Routine (the clock of soundSensor.times)
if beep_onset is None and beep.status == STARTED:
    beep_onset = tThisFlip
# Psychtoolbox's own timing of this beep (diagnostics): its status once the
# box has answered, so the beep has certainly started
if ptb_status is None and soundSensor.times != []:
    ptb_status = beep_ptb_status(beep)
# Next trial when the beep has played and the box answered (or at the
# timeout of the Sound Sensor)
if beep.status == FINISHED and soundSensor.times != []:
    continueRoutine = False
