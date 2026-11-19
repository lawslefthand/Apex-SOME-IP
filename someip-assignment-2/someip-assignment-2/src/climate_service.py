"""
Virtual Climate ECU — ClimateService provider.

Methods:
  GetCabinTemperature() -> int16, tenths of degree Celsius
  SetTargetTemperature(int16) -> uint8 status

Event:
  CabinTemperatureChanged -> int16, tenths of degree Celsius
"""

import asyncio
import logging
from typing import Tuple

from someipy import (
    MessageType,
    Method,
    MethodResult,
    ReturnCode,
    ServerServiceInstance,
    ServiceBuilder,
    TransportLayerProtocol,
    connect_to_someipy_daemon,
)
from someipy.someipy_logging import set_someipy_log_level

from climate_interface import (
    ACCEPTED,
    CABIN_TEMPERATURE_CHANGED_EVENT_ID,
    CABIN_TEMPERATURE_EVENTGROUP_ID,
    DISPLAY_PORT,
    GET_CABIN_TEMPERATURE_METHOD_ID,
    INSTANCE_ID,
    INTERFACE_IP,
    INVALID_TEMPERATURE,
    MAJOR_VERSION,
    MAX_TARGET_TEMPERATURE,
    MIN_TARGET_TEMPERATURE,
    PROVIDER_PORT,
    SERVICE_ID,
    SetTemperatureRequest,
    SetTemperatureResponse,
    TemperaturePayload,
    cabin_temperature_eventgroup,
)

current_cabin_temperature = 240
target_temperature = 220


async def get_cabin_temperature_handler(
    input_data: bytes,
    client_address: Tuple[str, int],
) -> MethodResult:
    print(
        f"\nGetCabinTemperature request from "
        f"{client_address[0]}:{client_address[1]}"
    )
    payload = TemperaturePayload(current_cabin_temperature).serialize()

    result = MethodResult()
    result.message_type = MessageType.RESPONSE
    result.return_code = ReturnCode.E_OK
    result.payload = payload
    print(
        f"Returning cabin temperature: "
        f"{current_cabin_temperature / 10:.1f} °C"
    )
    return result


async def set_target_temperature_handler(
    input_data: bytes,
    client_address: Tuple[str, int],
) -> MethodResult:
    global target_temperature

    request = SetTemperatureRequest().deserialize(input_data)
    requested = request.target_temperature_tenths_c.value

    print(
        f"\nSetTargetTemperature request from "
        f"{client_address[0]}:{client_address[1]}: "
        f"{requested / 10:.1f} °C"
    )

    if MIN_TARGET_TEMPERATURE <= requested <= MAX_TARGET_TEMPERATURE:
        target_temperature = requested
        status = ACCEPTED
        print(f"Target temperature updated to {target_temperature / 10:.1f} °C")
    else:
        status = INVALID_TEMPERATURE
        print("Invalid target temperature; previous target retained.")

    payload = SetTemperatureResponse(status).serialize()
    result = MethodResult()
    result.message_type = MessageType.RESPONSE
    result.return_code = ReturnCode.E_OK
    result.payload = payload
    return result


def build_climate_service():
    get_method = Method(
        id=GET_CABIN_TEMPERATURE_METHOD_ID,
        protocol=TransportLayerProtocol.UDP,
        method_handler=get_cabin_temperature_handler,
    )
    set_method = Method(
        id=0x0002,
        protocol=TransportLayerProtocol.UDP,
        method_handler=set_target_temperature_handler,
    )

    return (
        ServiceBuilder()
        .with_service_id(SERVICE_ID)
        .with_major_version(MAJOR_VERSION)
        .with_method(get_method)
        .with_method(set_method)
        .with_eventgroup(cabin_temperature_eventgroup)
        .build()
    )


async def simulate_cabin_temperature(instance: ServerServiceInstance):
    global current_cabin_temperature

    values = [240, 245, 250, 255, 260]
    index = 0

    while True:
        current_cabin_temperature = values[index]
        index = (index + 1) % len(values)

        payload = TemperaturePayload(current_cabin_temperature).serialize()
        print(
            f"\nCabin temperature changed: "
            f"{current_cabin_temperature / 10:.1f} °C"
        )
        instance.send_event(
            CABIN_TEMPERATURE_EVENTGROUP_ID,
            CABIN_TEMPERATURE_CHANGED_EVENT_ID,
            payload,
        )
        print("CabinTemperatureChanged event sent.")
        await asyncio.sleep(3)


async def main():
    set_someipy_log_level(logging.INFO)

    print("=" * 60)
    print("CLIMATE ECU — ClimateService Provider")
    print(f"Service ID: 0x{SERVICE_ID:04X}")
    print(f"Instance ID: 0x{INSTANCE_ID:04X}")
    print(f"Endpoint: {INTERFACE_IP}:{PROVIDER_PORT}")
    print("=" * 60)

    daemon = await connect_to_someipy_daemon()
    service = build_climate_service()

    instance = ServerServiceInstance(
        daemon=daemon,
        service=service,
        instance_id=INSTANCE_ID,
        endpoint_ip=INTERFACE_IP,
        endpoint_port=PROVIDER_PORT,
        ttl=5,
        cyclic_offer_delay_ms=2000,
    )

    await instance.start_offer()
    print("ClimateService offered.")

    task = asyncio.create_task(simulate_cabin_temperature(instance))
    try:
        await asyncio.Future()
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        await instance.stop_offer()
        await daemon.disconnect_from_daemon()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nClimate ECU stopped.")
