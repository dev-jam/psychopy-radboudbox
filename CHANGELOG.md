# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0]

### Added
- first version, the PsychoPy version of opensesame-plugin-radboudbox 7.0.1
- device backends for the Button Box and Sound Sensor components of PsychoPy
- Radboud Buttonbox Trigger and Radboud Buttonbox Control components
- hardware classes for Coder: a reader thread per box timestamps each character when it arrives
- the port settings checks of the OpenSesame plugin (latency timer, COM port number, FIFO buffers, ModemManager)
- while a box is open, Python's switch interval is 0.5 ms instead of 5 ms, so the reader thread timestamps within 1 ms also while the frame loop runs Python code
- radboud buttonbox control without a stop time is finished once it has sent its command (otherwise its routine never ended)
- demo: audio latency tester, the PsychoPy version of the OpenSesame audio latency tester (default sampler) of the lab-validation-toolbox
