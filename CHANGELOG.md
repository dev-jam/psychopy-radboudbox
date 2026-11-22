# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/en/1.0.0/)
and this project adheres to [Semantic Versioning](http://semver.org/spec/v2.0.0.html).

## [Unreleased]

- added: first version, the PsychoPy version of opensesame-plugin-radboudbox 7.0.1, through RuSocSci
- added: device backends that make the Radboud Buttonbox a device of PsychoPy's own Button Box component (buttons A-H are buttons 0-7, press and release) and Sound Sensor component (sound or voice key, extended mode)
- added: Radboud Buttonbox Trigger (a start and a stop value, synced to the screen refresh) and Radboud Buttonbox Control (the commands of radboudbox_send_control) components
- added: hardware classes for Coder; one reader thread per box timestamps each character when it arrives, since a component reads only once per frame
- added: the port settings checks of the OpenSesame plugin (latency timer, COM port number, FIFO buffers, ModemManager)
- changed: while a box is open, Python's switch interval is 0.5 ms instead of 5 ms (for the whole process; restored when the last box is closed), so the reader thread timestamps within 1 ms also while the frame loop runs Python code
- fixed: a Radboud Buttonbox Control component without a stop time never finished, so its Routine never ended; it now finishes once it has sent its command
- added: demo: audio latency tester, the PsychoPy version of the OpenSesame audio latency tester (default sampler) of the lab-validation-toolbox

[Unreleased]: https://github.com/dev-jam/psychopy-radboudbox/commits/main
