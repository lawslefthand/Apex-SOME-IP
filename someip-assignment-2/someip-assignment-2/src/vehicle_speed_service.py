"""
Virtual Vehicle ECU — VehicleSpeedService provider.

Methods:
  GetSpeed()        -> uint16, km/h
  GetVehicleState() -> uint8, 0=STOPPED / 1=MOVING

Events:
  SpeedChanged      -> uint16, km/h, event group 0x0001
  OverspeedWarning  -> uint16, km/h, event group 0x0002
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

from vehicle_speed_interface import (
    GET_SPEED_METHOD_ID,
    GET_VEHICLE_STATE_METHOD_ID,
    INSTANCE_ID,
    INTERFACE_IP,
    MAJOR_VERSION,
    MOVING,
    OVERSPEED_EVENTGROUP_ID,
    OVERSPEED_WARNING_EVENT_ID,
    PROVIDER_PORT,
    SERVICE_ID,
    SPEED_CHANGED_EVENT_ID,
    SPEED_EVENTGROUP_ID,
    STOPPED,
    SpeedPayload,
    VehicleStatePayload,
    overspeed_eventgroup,
    speed_eventgroup,
)

current_speed_kmph = 0


async def get_speed_handler(
    input_data: bytes,
    client_address: Tuple[str, int],
) -> MethodResult:
    print(f"\nGetSpeed request from {client_address[0]}:{client_address[1]}")
    payload = SpeedPayload(current_speed_kmph).serialize()

    result = MethodResult()
    result.message_type = MessageType.RESPONSE
    result.return_code = ReturnCode.E_OK
    result.payload = payload
    print(f"GetSpeed response: {current_speed_kmph} km/h")
    return result


async def get_vehicle_state_handler(
    input_data: bytes,
    client_address: Tuple[str, int],
) -> MethodResult:
    state = STOPPED if current_speed_kmph == 0 else MOVING
    state_name = "STOPPED" if state == STOPPED else "MOVING"

    print(
        f"\nGetVehicleState request from "
        f"{client_address[0]}:{client_address[1]}"
    )
    payload = VehicleStatePayload(state).serialize()

    result = MethodResult()
    result.message_type = MessageType.RESPONSE
    result.return_code = ReturnCode.E_OK
    result.payload = payload
    print(f"GetVehicleState response: {state_name} ({state})")
    return result


def build_provider_service():
    get_speed = Method(
        id=GET_SPEED_METHOD_ID,
        protocol=TransportLayerProtocol.UDP,
        method_handler=get_speed_handler,
    )
    get_vehicle_state = Method(
        id=GET_VEHICLE_STATE_METHOD_ID,
        protocol=TransportLayerProtocol.UDP,
        method_handler=get_vehicle_state_handler,
    )

    return (
        ServiceBuilder()
        .with_service_id(SERVICE_ID)
        .with_major_version(MAJOR_VERSION)
        .with_method(get_speed)
        .with_method(get_vehicle_state)
        .with_eventgroup(speed_eventgroup)
        .with_eventgroup(overspeed_eventgroup)
        .build()
    )


async def simulate_vehicle(service_instance: ServerServiceInstance):
    global current_speed_kmph

    while True:
        current_speed_kmph += 10
        if current_speed_kmph > 100:
            current_speed_kmph = 0

        speed_payload = SpeedPayload(current_speed_kmph).serialize()
        print(f"\nVehicle speed changed: {current_speed_kmph} km/h")

        service_instance.send_event(
            SPEED_EVENTGROUP_ID,
            SPEED_CHANGED_EVENT_ID,
            speed_payload,
        )
        print("SpeedChanged event sent")

        if current_speed_kmph > 80:
            service_instance.send_event(
                OVERSPEED_EVENTGROUP_ID,
                OVERSPEED_WARNING_EVENT_ID,
                speed_payload,
            )
            print("!!! OverspeedWarning event sent !!!")

        await asyncio.sleep(2)


async def main():
    set_someipy_log_level(logging.INFO)

    print("=" * 60)
    print("VEHICLE ECU — VehicleSpeedService Provider")
    print(f"Service ID: 0x{SERVICE_ID:04X}")
    print(f"Instance ID: 0x{INSTANCE_ID:04X}")
    print(f"Endpoint: {INTERFACE_IP}:{PROVIDER_PORT}")
    print("=" * 60)

    daemon = await connect_to_someipy_daemon()
    service = build_provider_service()

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
    print("VehicleSpeedService offered.")

    simulation_task = asyncio.create_task(simulate_vehicle(instance))

    try:
        await asyncio.Future()
    finally:
        simulation_task.cancel()
        try:
            await simulation_task
        except asyncio.CancelledError:
            pass
        await instance.stop_offer()
        await daemon.disconnect_from_daemon()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nVehicle ECU stopped.")
