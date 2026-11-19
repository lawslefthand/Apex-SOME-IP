"""
Shared SOME/IP interface definitions for ClimateService.
"""

from dataclasses import dataclass

from someipy import Event, EventGroup, Method, ServiceBuilder, TransportLayerProtocol
from someipy.serialization import SomeIpPayload, Int16, Uint8


SERVICE_ID = 0x2234
INSTANCE_ID = 0x0001
MAJOR_VERSION = 1

GET_CABIN_TEMPERATURE_METHOD_ID = 0x0001
SET_TARGET_TEMPERATURE_METHOD_ID = 0x0002

CABIN_TEMPERATURE_CHANGED_EVENT_ID = 0x8001
CABIN_TEMPERATURE_EVENTGROUP_ID = 0x0001

INTERFACE_IP = "127.0.0.1"
PROVIDER_PORT = 3010
DISPLAY_PORT = 3012

MIN_TARGET_TEMPERATURE = 160
MAX_TARGET_TEMPERATURE = 300

ACCEPTED = 0
INVALID_TEMPERATURE = 1


@dataclass
class TemperaturePayload(SomeIpPayload):
    temperature_tenths_c: Int16

    def __init__(self, temperature_tenths_c: int = 240):
        self.temperature_tenths_c = Int16(temperature_tenths_c)


@dataclass
class SetTemperatureRequest(SomeIpPayload):
    target_temperature_tenths_c: Int16

    def __init__(self, target_temperature_tenths_c: int = 220):
        self.target_temperature_tenths_c = Int16(target_temperature_tenths_c)


@dataclass
class SetTemperatureResponse(SomeIpPayload):
    status: Uint8

    def __init__(self, status: int = ACCEPTED):
        self.status = Uint8(status)


get_cabin_temperature_method = Method(
    id=GET_CABIN_TEMPERATURE_METHOD_ID,
    protocol=TransportLayerProtocol.UDP,
)

set_target_temperature_method = Method(
    id=SET_TARGET_TEMPERATURE_METHOD_ID,
    protocol=TransportLayerProtocol.UDP,
)

cabin_temperature_changed_event = Event(
    id=CABIN_TEMPERATURE_CHANGED_EVENT_ID,
    protocol=TransportLayerProtocol.UDP,
)

cabin_temperature_eventgroup = EventGroup(
    id=CABIN_TEMPERATURE_EVENTGROUP_ID,
    events=[cabin_temperature_changed_event],
)

climate_service = (
    ServiceBuilder()
    .with_service_id(SERVICE_ID)
    .with_major_version(MAJOR_VERSION)
    .with_method(get_cabin_temperature_method)
    .with_method(set_target_temperature_method)
    .with_eventgroup(cabin_temperature_eventgroup)
    .build()
)
