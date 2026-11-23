# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/en/1.0.0/)
and this project adheres to [Semantic Versioning](http://semver.org/spec/v2.0.0.html).

## [Unreleased]

- fixed: demo: without a device 'soundkey' in Device Manager the demo stopped with an AttributeError; it now says which device to set up

## [0.1.1] - 2026-11-23

- fixed: the Builder window did not open with the plugin installed (IndexError in psychopy_app's ComponentIcon): the component icons are now in a folder per Builder theme (light, dark, classic), 48 and 96 px, made by `tools/make_icons.py`

## [0.1.0] - 2026-11-22

- first version: device backends for PsychoPy's own Button Box component (buttons A-H are buttons 0-7, press and release) and Sound Sensor component (sound or voice key), and the components Radboud Buttonbox Trigger and Radboud Buttonbox Control, ported from opensesame-plugin-radboudbox 7.0.1 (through RuSocSci)
- hardware classes for Code components and Coder scripts; one reader thread per box timestamps each character when it arrives (the box sends no times, and a component reads only once per frame)
- the port settings checks of the OpenSesame plugin (latency timer, COM port number, FIFO buffers, ModemManager)
- while a box is open, Python's switch interval is 0.5 ms instead of 5 ms (for the whole process; restored when the last box is closed), so the reader thread timestamps within 1 ms also while the frame loop runs Python code
- Radboud Buttonbox Control without a stop time finishes once it has sent its command (its Routine never ended)
- demo experiment `demo/radboudbox_latency_audio_tester.psyexp` (the audio latency tester with the default sampler of the lab-validation-toolbox)
- changelog: links to the versions
- `tools/build_demo.py` builds the demo experiment

[Unreleased]: https://github.com/dev-jam/psychopy-radboudbox/compare/0.1.1...HEAD
[0.1.1]: https://github.com/dev-jam/psychopy-radboudbox/compare/0.1.0...0.1.1
[0.1.0]: https://github.com/dev-jam/psychopy-radboudbox/releases/tag/0.1.0
