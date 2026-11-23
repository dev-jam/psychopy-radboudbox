"""
This file is part of psychopy-radboudbox.

Copyright (C) 2016-2026 Bob Rosbag <mail@bobrosbag.nl>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.

SPDX-License-Identifier: GPL-3.0-or-later

Builder support: device backends that make the Radboud Buttonbox a device
of PsychoPy's own Button Box and Sound Sensor components, and two
components of this plugin, Radboud Buttonbox Trigger and Radboud
Buttonbox Control, that use such a device.
"""

__author__ = "Bob Rosbag"
__license__ = "GPL-3.0-or-later"

from copy import copy
from pathlib import Path

from psychopy.experiment.components import (BaseDeviceComponent, Param,
                                             getInitVals)
from psychopy.experiment.components.buttonBox import ButtonBoxComponent
from psychopy.experiment.components.soundsensor import SoundSensorComponent
from psychopy.experiment.devices import DeviceBackend
from psychopy.localization import _translate

from ..radboudbox import COMMANDS, VALUE_COMMANDS

HERE = Path(__file__).parent
# Builder reads <HERE>/<theme>/<stem>.png and <stem>@2x.png (themes light,
# dark and classic; tools/make_icons.py makes them): iconFile only gives the
# folder and the stem


def _device_params(profile):
    """The settings of the box, the same for buttons and sound sensor."""
    params = {}
    params['radboudboxPort'] = Param(
        profile.get('port') or '', valType='str', inputType='single',
        categ='Device', label=_translate('Port'),
        hint=_translate('Port of the box, e.g. COM3 or /dev/ttyACM0; empty: '
                        'the first buttonbox found'))
    params['radboudboxExtendedMode'] = Param(
        True, valType='bool', inputType='bool', categ='Device',
        label=_translate('Bitsi extended mode'),
        hint=_translate('Must match the mode of the box; needed for the '
                        'sound and voice key and for control commands'))
    params['radboudboxWrongPortSettings'] = Param(
        'error', valType='str', inputType='choice', categ='Device',
        allowedVals=['error', 'warning'],
        label=_translate('Wrong port settings'),
        hint=_translate('error: stop the experiment when a port setting '
                        'makes the timing wrong; warning: log it and go on '
                        '(for tests only)'))
    return params, list(params)


DEVICE_CODE = (
    "    port=%(radboudboxPort)s,\n"
    "    extendedMode=%(radboudboxExtendedMode)s,\n"
    "    wrongPortSettings=%(radboudboxWrongPortSettings)s,\n"
)


class RadboudboxButtonBoxBackend(DeviceBackend):
    """The buttons of the Radboud Buttonbox for the Button Box component:
    button A-H is button 0-7.
    """
    backendLabel = _translate('Radboud Buttonbox (BITSI)')
    deviceClass = 'psychopy_radboudbox.radboudbox.RadboudboxButtonGroup'
    icon = 'light/radboudboxTrigger.png'
    plugin = 'psychopy-radboudbox'

    def getParams(self):
        return _device_params(self.profile or {})

    def writeDeviceCode(self, buff):
        inits = getInitVals(self.params)
        code = (
            "# initialize %(name)s (Radboud Buttonbox buttons)\n"
            "deviceManager.addDevice(\n"
            f"    deviceClass='{self.deviceClass}',\n"
            "    deviceName=%(name)s,\n"
            + DEVICE_CODE +
            ")\n"
        )
        buff.writeIndentedLines(code % inits)


class RadboudboxSoundSensorBackend(DeviceBackend):
    """The sound or voice key of the Radboud Buttonbox for the Sound Sensor
    component (extended mode).
    """
    backendLabel = _translate('Radboud Buttonbox (BITSI) sound/voice key')
    deviceClass = 'psychopy_radboudbox.radboudbox.RadboudboxSoundSensorGroup'
    icon = 'light/radboudboxControl.png'
    plugin = 'psychopy-radboudbox'

    def getParams(self):
        profile = self.profile or {}
        params, order = _device_params(profile)
        params['radboudboxSensor'] = Param(
            profile.get('sensor') or 'sound', valType='str',
            inputType='choice', categ='Device',
            allowedVals=['sound', 'voice'], label=_translate('Key'),
            hint=_translate('The sound key or the voice key of the box'))
        params['radboudboxCalibrate'] = Param(
            True, valType='bool', inputType='bool', categ='Device',
            label=_translate('Calibrate at the start'),
            hint=_translate('Calibrate the silence when the experiment '
                            'starts (1 s: be silent)'))
        return params, order + ['radboudboxSensor', 'radboudboxCalibrate']

    def writeDeviceCode(self, buff):
        inits = getInitVals(self.params)
        code = (
            "# initialize %(name)s (Radboud Buttonbox sound/voice key)\n"
            "deviceManager.addDevice(\n"
            f"    deviceClass='{self.deviceClass}',\n"
            "    deviceName=%(name)s,\n"
            + DEVICE_CODE +
            "    sensor=%(radboudboxSensor)s,\n"
            "    calibrate=%(radboudboxCalibrate)s,\n"
            ")\n"
        )
        buff.writeIndentedLines(code % inits)


ButtonBoxComponent.registerBackend(RadboudboxButtonBoxBackend)
SoundSensorComponent.registerBackend(RadboudboxSoundSensorBackend)


def _require_sender(component):
    # Imports are written before the code of the components
    component.exp.requireImport(
        importName='RadboudboxSender',
        importFrom='psychopy_radboudbox.radboudbox')


def _write_get_device(component, buff):
    """The component's own sender for its device of Device Manager."""
    code = (
        "# Radboud Buttonbox of %(name)s, set up in Device Manager\n"
        "%(name)s = RadboudboxSender(device=%(deviceLabel)s)\n"
    )
    buff.writeIndentedLines(code % getInitVals(component.params))


class RadboudboxTriggerComponent(BaseDeviceComponent):
    """Sends a trigger value through the Radboud Buttonbox when the
    component starts, and an optional value (e.g. 0) when it stops.
    """
    categories = ['I/O', 'EEG']
    targets = ['PsychoPy']
    iconFile = HERE / 'radboudboxTrigger.png'
    tooltip = _translate('Radboud Buttonbox Trigger: send a trigger value '
                         'through the Radboud Buttonbox')
    plugin = 'psychopy-radboudbox'

    def __init__(self, exp, parentName, name='radboudboxTrigger',
                 startType='time (s)', startVal=0.0,
                 stopType='duration (s)', stopVal=0.05,
                 startEstim='', durationEstim='',
                 deviceLabel='', startData=1, stopData=0,
                 syncScreenRefresh=True, disabled=False):
        BaseDeviceComponent.__init__(
            self, exp, parentName, name=name,
            startType=startType, startVal=startVal,
            stopType=stopType, stopVal=stopVal,
            startEstim=startEstim, durationEstim=durationEstim,
            deviceLabel=deviceLabel, syncScreenRefresh=syncScreenRefresh,
            disabled=disabled)
        self.type = 'RadboudboxTrigger'
        _require_sender(self)
        self.order += ['startData', 'stopData']
        self.params['startData'] = Param(
            startData, valType='code', inputType='single', categ='Basic',
            label=_translate('Start value'),
            hint=_translate('Trigger value (0-255) sent when the component '
                            'starts, e.g. $trigger'))
        self.params['stopData'] = Param(
            stopData, valType='code', inputType='single', categ='Basic',
            label=_translate('Stop value'),
            hint=_translate('Trigger value (0-255) sent when the component '
                            'stops (also at the end of the Routine); empty: '
                            'none, the output keeps the start value'))

    def writeInitCode(self, buff):
        _write_get_device(self, buff)

    def _write_send(self, buff, data):
        params = copy(self.params)
        params['data'] = data
        if self.params['syncScreenRefresh'].val:
            code = "win.callOnFlip(%(name)s.sendMarker, int(%(data)s))\n"
        else:
            code = "%(name)s.sendMarker(int(%(data)s))\n"
        buff.writeIndentedLines(code % params)

    def _has_stop_data(self):
        return str(self.params['stopData'].val).strip() not in ('', 'None')

    def writeFrameCode(self, buff):
        buff.writeIndentedLines("\n# *%(name)s* updates\n" % self.params)
        indented = self.writeStartTestCode(buff)
        if indented:
            self._write_send(buff, self.params['startData'])
            buff.writeIndentedLines(
                "thisExp.addData('%(name)s.startData', %(startData)s)\n"
                % self.params)
            buff.setIndentLevel(-indented, relative=True)
        indented = self.writeStopTestCode(buff)
        if indented:
            if self._has_stop_data():
                self._write_send(buff, self.params['stopData'])
                buff.writeIndentedLines(
                    "thisExp.addData('%(name)s.stopData', %(stopData)s)\n"
                    % self.params)
            buff.setIndentLevel(-indented, relative=True)

    def writeRoutineEndCode(self, buff):
        if self._has_stop_data():
            # Ended before its stop time (e.g. by a response): the stop
            # value, at once (there is no flip after the Routine)
            code = (
                "# the Routine ended before %(name)s stopped: send its stop "
                "value\n"
                "if %(name)s.status == STARTED:\n"
                "    %(name)s.sendMarker(int(%(stopData)s))\n"
                "    thisExp.addData('%(name)s.stopData', %(stopData)s)\n"
            )
            buff.writeIndentedLines(code % self.params)
        BaseDeviceComponent.writeRoutineEndCode(self, buff)


class RadboudboxControlComponent(BaseDeviceComponent):
    """Sends a control command to the Radboud Buttonbox (extended mode)
    when the component starts; without a stop time it is then finished. Analog In logs the answer of the box as
    <name>.analogIn; Calibrate waits 1 s (be silent; put it in a Routine
    of its own).
    """
    categories = ['I/O']
    targets = ['PsychoPy']
    iconFile = HERE / 'radboudboxControl.png'
    tooltip = _translate('Radboud Buttonbox Control: send a control command '
                         'to the Radboud Buttonbox')
    plugin = 'psychopy-radboudbox'

    def __init__(self, exp, parentName, name='radboudboxControl',
                 startType='time (s)', startVal=0.0,
                 stopType='duration (s)', stopVal='',
                 startEstim='', durationEstim='',
                 deviceLabel='', command='Tone', commandValue='',
                 syncScreenRefresh=False, disabled=False):
        BaseDeviceComponent.__init__(
            self, exp, parentName, name=name,
            startType=startType, startVal=startVal,
            stopType=stopType, stopVal=stopVal,
            startEstim=startEstim, durationEstim=durationEstim,
            deviceLabel=deviceLabel, syncScreenRefresh=syncScreenRefresh,
            disabled=disabled)
        self.type = 'RadboudboxControl'
        _require_sender(self)
        self.order += ['command', 'commandValue']
        self.params['command'] = Param(
            command, valType='str', inputType='choice', categ='Basic',
            allowedVals=list(COMMANDS), label=_translate('Command'),
            hint=_translate('The command to send when the component starts'))
        self.params['commandValue'] = Param(
            commandValue, valType='code', inputType='single', categ='Basic',
            label=_translate('Command value'),
            hint=_translate('0-255 (Pulse Time: ms), for Marker Out, Pulse '
                            'Out, Pulse Time and Analog Out'))
        self.depends.append({
            'dependsOn': 'command',
            'condition': f'in {list(VALUE_COMMANDS)!r}',
            'param': 'commandValue',
            'true': 'show',
            'false': 'hide',
        })

    def writeInitCode(self, buff):
        _write_get_device(self, buff)

    def writeFrameCode(self, buff):
        params = copy(self.params)
        command = self.params['command'].val
        if command in VALUE_COMMANDS:
            params['args'] = ('%(command)s, int(%(commandValue)s)'
                              % self.params)
        else:
            params['args'] = '%(command)s' % self.params
        buff.writeIndentedLines("\n# *%(name)s* updates\n" % self.params)
        indented = self.writeStartTestCode(buff)
        if indented:
            if command.startswith('Analog In'):
                code = (
                    "%(name)s.analogIn = %(name)s.sendCommand(%(args)s)\n"
                    "thisExp.addData('%(name)s.analogIn', %(name)s.analogIn)\n"
                )
            elif self.params['syncScreenRefresh'].val:
                code = "win.callOnFlip(%(name)s.sendCommand, %(args)s)\n"
            else:
                code = "%(name)s.sendCommand(%(args)s)\n"
            if self._no_stop():
                # A command is sent once: without a stop time the component
                # is done, otherwise its Routine would never end
                code += "%(name)s.status = FINISHED\n"
            buff.writeIndentedLines(code % params)
            buff.setIndentLevel(-indented, relative=True)
        if self._no_stop():
            return
        indented = self.writeStopTestCode(buff)
        if indented:
            buff.setIndentLevel(-indented, relative=True)

    def _no_stop(self):
        return str(self.params['stopVal'].val).strip() in ('', 'None')


for _component in (RadboudboxTriggerComponent, RadboudboxControlComponent):
    _component.registerBackend(RadboudboxButtonBoxBackend)
    _component.registerBackend(RadboudboxSoundSensorBackend)
