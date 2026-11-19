"""
Virtual Instrument Cluster ECU — VehicleSpeedService consumer.
Consumes both methods and both event groups from Vehicle ECU.
"""

import asyncio
import logging

from someipy import ClientServiceInstance, MessageType, ReturnCode, connect_to_someipy_daemon
from someipy.someipy_logging import set_someipy_log_level

from vehicle_speed_interface import (
    CLUSTER_PORT,
    GET_SPEED_METHOD_ID,
    GET_VEHICLE_STATE_METHOD_ID,
    INSTANCE_ID,
    INTERFACE_IP,
    MOVING,
    SERVICE_ID,
    SpeedPayload,
    VehicleStatePayload,
    OVERSPEED_WARNING_EVENT_ID,
    speed_eventgroup,
    overspeed_eventgroup,
    vehicle_speed_service,
)


def event_callback(event_id: int, event_payload: bytes):
    try:
        if event_id == OVERSPEED_WARNING_EVENT_ID:
            decoded = SpeedPayload().deserialize(event_payload)
            print("\n" + "!" * 50)
            print("OVERSPEED WARNING")
            print(f"Vehicle speed: {decoded.speed_kmph.value} km/h")
            print("!" * 50)
        else:
            decoded = SpeedPayload().deserialize(event_payload)
            print(
                f"\nSpeedChanged notification: "
                f"{decoded.speed_kmph.value} km/h"
            )
    except Exception as exc:
        print(f"Could not decode event 0x{event_id:04X}: {exc}")


async def request_loop(client: ClientServiceInstance):
    while True:
        try:
            speed_result = await client.call_method(GET_SPEED_METHOD_ID, b"")
            if (
                speed_result.message_type == MessageType.RESPONSE
                and speed_result.return_code == ReturnCode.E_OK
            ):
                speed = SpeedPayload().deserialize(speed_result.payload)
                print(f"\nCurrent vehicle speed: {speed.speed_kmph.value} km/h")

            state_result = await client.call_method(GET_VEHICLE_STATE_METHOD_ID, b"")
            if (
                state_result.message_type == MessageType.RESPONSE
                and state_result.return_code == ReturnCode.E_OK
            ):
                state = VehicleStatePayload().deserialize(state_result.payload)
                state_name = "MOVING" if state.state.value == MOVING else "STOPPED"
                print(f"Vehicle state: {state_name}")

        except Exception as exc:
            print(f"Vehicle service method call failed: {exc}")

        await asyncio.sleep(5)


async def main():
    set_someipy_log_level(logging.INFO)

    print("=" * 60)
    print("INSTRUMENT CLUSTER ECU")
    print(f"Looking for VehicleSpeedService 0x{SERVICE_ID:04X}")
    print("=" * 60)

    daemon = await connect_to_someipy_daemon()
    client = ClientServiceInstance(
        daemon=daemon,
        service=vehicle_speed_service,
        instance_id=INSTANCE_ID,
        endpoint_ip=INTERFACE_IP,
        endpoint_port=CLUSTER_PORT,
    )
    client.register_callback(event_callback)

    print("Searching for VehicleSpeedService...")
    while not await client.is_available():
        print("VehicleSpeedService not available yet.")
        await asyncio.sleep(1)

    print("VehicleSpeedService AVAILABLE")

    # someipy requires this TTL argument to be an integer.
    client.subscribe_eventgroup(speed_eventgroup, 5)
    client.subscribe_eventgroup(overspeed_eventgroup, 5)
    print("Subscribed to SpeedChanged and OverspeedWarning.")

    task = asyncio.create_task(request_loop(client))
    try:
        await asyncio.Future()
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        await daemon.disconnect_from_daemon()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nInstrument Cluster stopped.")
