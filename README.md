PsychoPy Plugin: Radboud Buttonbox
==========

*A PsychoPy plugin for the Radboud Buttonbox (BITSI): button responses, sound and voice key, and stimulus synchronization triggers to data acquisition systems.*

Copyright (C) 2016-2026 Bob Rosbag

This plugin makes use of the RuSocSci python package developed by Wilbert van Ham. Radboud Buttonbox is developed by Pascal de Water. It is the PsychoPy version of [opensesame-plugin-radboudbox](https://github.com/dev-jam/opensesame-plugin-radboudbox).


## About

The Technical Support Group (Radboud University, Social Sciences) developed a USB Arduino based Buttonbox which can be used for time accurate (1ms) button press, voice key, sound key registration and sending parallel port like triggers.
Upper case A, B, C, D, E (, F, G, H) are used for key presses, and lower case a, b, c, d, e (, f, g, h) are used for key releases. Uppercase S is used for sound key detection and uppercase V for voice key.

For more information:

<https://tsgdoc.socsci.ru.nl/index.php/ButtonBox>


## What the plugin adds

The plugin works the way PsychoPy handles response hardware since 2026.1: a *device* is set up once in Builder's **Device Manager**, and components in a Routine use it by its label. The plugin adds:

- **Device backends** for PsychoPy's own components:
  - *Radboud Buttonbox (BITSI)* for the **Button Box** component: buttons A-H are buttons 0-7; *Register button press on* Press is A-H, Release is a-h.
  - *Radboud Buttonbox (BITSI) sound/voice key* for the **Sound Sensor** component (extended mode).
- Two components (category I/O):
  - **Radboud Buttonbox Trigger** sends a trigger value when it starts and a stop value (default 0) when it stops, e.g. a 50 ms pulse. It replaces radboudbox_send_trigger with its pulse mode.
  - **Radboud Buttonbox Control** sends a control command when it starts (Calibrate Sound/Voice, Detect Sound/Voice, Marker Out, Pulse Out, Pulse Time, Analog Out 1/2, Tone, Analog In 1-4, LEDs Off/Input/Output; see the table in the README of the OpenSesame plugin for the firmware that has them). Analog In logs the answer as `[name].analogIn`. Calibrate waits 1 s (be silent): put it in a Routine of its own.
- Hardware classes for Coder (`psychopy_radboudbox.radboudbox`): `RadboudboxButtonGroup`, `RadboudboxSoundSensorGroup` and `RadboudboxDevice`.

The Trigger and Control components use a device of either backend; one box can have both a buttons device and a sound/voice key device (they share the port; set the same *Bitsi extended mode* for both).

Install:

    pip install psychopy-radboudbox

or in PsychoPy: Tools > Plugins/packages manager. The plugin needs Python 3.10 or later and the [RuSocSci](https://pypi.org/project/RuSocSci/) package, which is installed with it.

**PsychoPy version.** The Builder part needs PsychoPy 2026.1 or later: Device Manager's device backends got their current form (`psychopy.experiment.devices`) in 2026.1; in 2025.2 they named the device label differently. Tested with PsychoPy 2026.2.5 (Linux, with a simulated box); not yet with a real box, nor on Windows or macOS.


## Foreground and background items are not needed in PsychoPy

The OpenSesame plugin has a foreground item (radboudbox_collect_buttons_fg) and background items (bg_start, bg_wait, bg_stop). The PsychoPy plugin has neither, and doesn't need them:

- **OpenSesame** runs the items of a sequence one after another: an item that waits for a button holds up the next item, e.g. the stimulus. To collect buttons while a stimulus is shown, the plugin needed a thread that a start item starts and a wait or stop item ends.
- **PsychoPy** Builder runs all components of a Routine at the same time: each frame, every component checks its start and stop time and does its part (draw a stimulus, read responses). A Button Box component reads the box while a Text or Image component in the same Routine is shown. *Force end of Routine* gives the foreground behaviour (wait for the response); a start and a stop time give the background behaviour (collect for a time window, also while other stimuli change).

| OpenSesame item | PsychoPy |
|---|---|
| radboudbox_init | a device in Device Manager (port, Bitsi extended mode, Wrong port settings) |
| radboudbox_collect_buttons_fg | Button Box component, *Force end of Routine* on, duration empty |
| radboudbox_collect_buttons_bg_start/_wait/_stop | Button Box component with a start and stop time in the Routine of the stimuli; its duration is the timeout |
| radboudbox_send_trigger (pulse mode) | Radboud Buttonbox Trigger (start value, stop value 0, duration = pulse time) |
| radboudbox_send_control | Radboud Buttonbox Control |
| Detect Sound/Voice + collect S/V | Sound Sensor component (it starts detection itself) |

What stays in the background is the **reading**: the box sends no times, so a response is only as exact as the moment it is read. A Builder component asks for responses once per frame (16.7 ms at 60 Hz); timestamped then, a response would be up to a frame late. So `RadboudboxDevice` runs one reader thread per box for the whole experiment: it reads each character the moment it arrives and timestamps it then (`psychopy.core.getTime()`); the components get these timestamps, converted to their clock. The thread also keeps the answer of Analog In apart from the buttons, so Analog In works while buttons are collected.

Responses that span several Routines (start in one, end in a later one) are kept by the device: a Button Box component with *Discard previous* off also gets the responses that came before it started and that no component took, with their own times (before its start: negative). In Coder, `getResponses()` can be called at any moment.


## Builder

1. Device Manager (in Builder: Tools > Device Manager, or *Device manager* in the toolbar): add a device, choose *Radboud Buttonbox (BITSI)*, give it a label, e.g. `radboudbox`. *Port* empty takes the first buttonbox found. Devices are stored in the PsychoPy settings of each computer: set them up again on the lab computer, with the same label.
2. Add a **Button Box** component to the trial Routine and choose the device. *Allowed buttons*: e.g. `0, 1` for A and B (empty: all). *Correct answer*: a button number, e.g. `$corrAns` with 0 or 1 in the conditions file.
3. For a trigger at the stimulus onset: a **Radboud Buttonbox Trigger** component with the same start time as the stimulus and *Sync timing with screen refresh* on (the default): the value is sent at the flip that shows the stimulus.

**Known PsychoPy issues** (2026.2.5, also in the release and dev branches on GitHub; not of this plugin):

- The Button Box component saves `[name].rt` from an attribute it never fills: the reaction times in the data file stay empty. Add a Code component after it, *End Routine*: `thisExp.addData('buttonBox.rt', buttonBox.rt)` (with the name of the component).
- The Button Box component uses the first button device in Device Manager, whatever device is chosen. With only a Radboud Buttonbox device this doesn't matter; don't add a Keyboard Button Box device next to it.
- The Sound Sensor component with *Store* first response keeps the last one.

**Testing without a box:** PsychoPy's own *Keyboard Button Box* backend of the Button Box component uses keys as buttons (the dummy mode of the OpenSesame plugin). The Trigger and Control components need a box.


## Coder

```python
from psychopy import core
from psychopy.hardware import DeviceManager

buttons = DeviceManager.addDevice(
    deviceClass='psychopy_radboudbox.radboudbox.RadboudboxButtonGroup',
    deviceName='radboudbox', port='', extendedMode=True)
clock = core.Clock()
buttons.resetTimer(clock)
buttons.clearResponses()
buttons.sendMarker(1)            # trigger value 1
core.wait(0.05)
buttons.sendMarker(0)
core.wait(2)
for response in buttons.getResponses(state=True):   # presses only
    print('ABCDEFGH'[response.channel], response.t)
print(buttons.sendCommand('Analog In 1'))
```

The Trigger and Control components use `RadboudboxSender(device='radboudbox')`: its own status per component, and `sendMarker()` and `sendCommand()` of the device. `RadboudboxSoundSensorGroup(sensor='voice')` is the voice key: `clearResponses()` starts detection, the box then sends one response at the next sound. `RadboudboxDevice.portInfo` has the box and its port settings (the log variables of the OpenSesame plugin, without `radboudbox_`).


## Buttonboxes

| | BITSI 2015 | BITSI 2018 |
|---|---|---|
| Board | Arduino Duemilanove, FTDI USB (0403:6001) | Teensy 3.6 (USB vendor 16C0) |
| Port on Linux | /dev/ttyUSB*, /dev/serial/by-id/usb-FTDI_* | /dev/ttyACM* |
| Simple mode | hold A+H while connecting | hold A+E while connecting |
| Extended mode | hold B+H while connecting | hold B+E while connecting |

**Mode.** The box stores its mode (simple or extended) itself. *Bitsi extended mode* of the device must match it: a box in the other mode sends wrong triggers. The device checks this with the ID string the box sends when it starts, and raises an error when the modes differ. When the ID string doesn't arrive in time, the mode can't be checked; there is a warning in the log.

**Port settings.** As the OpenSesame plugin, the device checks the port settings that make the timing wrong, and stops the experiment with an error that says how to fix them (*Wrong port settings*: error; warning only logs it, for tests): the latency timer of the BITSI 2015 (1 ms; on Linux also the udev rule), on Windows the COM port number (COM1-COM9) and for the BITSI 2018 the FIFO buffers. On Linux, a warning when ModemManager may use the BITSI 2018. See the README of the OpenSesame plugin for the details.

**Triggers.** Radboud Buttonbox Trigger works on all boxes, in both modes and with all firmware.


## License

This plugin is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version (GPL-3.0-or-later).

The full license text is in the file `COPYING`, and is also available at <https://www.gnu.org/licenses/gpl-3.0.html>.
