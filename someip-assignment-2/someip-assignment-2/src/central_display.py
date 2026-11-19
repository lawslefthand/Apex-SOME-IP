"""
Virtual Central Display ECU.

Consumes:
  - VehicleSpeedService from Vehicle ECU
  - ClimateService from Climate ECU

Run with --target-tenths 220 for 22.0 °C.
Use --target-tenths 350 to demonstrate an invalid 35.0 °C request.
"""

import argparse
import asyncio
import logging

from someipy import ClientServiceInstance, MessageType, ReturnCode, connect_to_someipy_daemon
from someipy.someipy_logging import set_someipy_log_level

from vehicle_speed_interface import (
    DISPLAY_VEHICLE_PORT,
    GET_SPEED_METHOD_ID,
    GET_VEHICLE_STATE_METHOD_ID,
    INSTANCE_ID as VEHICLE_INSTANCE_ID,
    INTERFACE_IP as VEHICLE_IP,
    MOVING,
    OVERSPEED_WARNING_EVENT_ID,
    SERVICE_ID as VEHICLE_SERVICE_ID,
    SpeedPayload,
    VehicleStatePayload,
    overspeed_eventgroup,
    speed_eventgroup,
    vehicle_speed_service,
)
from climate_interface import (
    ACCEPTED,
    DISPLAY_PORT,
    GET_CABIN_TEMPERATURE_METHOD_ID,
    INSTANCE_ID as CLIMATE_INSTANCE_ID,
    INTERFACE_IP as CLIMATE_IP,
    SERVICE_ID as CLIMATE_SERVICE_ID,
    SET_TARGET_TEMPERATURE_METHOD_ID,
    SetTemperatureRequest,
    SetTemperatureResponse,
    TemperaturePayload,
    cabin_temperature_eventgroup,
    climate_service,
)


def vehicle_event_callback(event_id: int, payload: bytes):
    try:
        speed = SpeedPayload().deserialize(payload).speed_kmph.value
        if event_id == OVERSPEED_WARNING_EVENT_ID:
            print("\n" + "!" * 55)
            print(f"CENTRAL DISPLAY — OVERSPEED WARNING: {speed} km/h")
            print("!" * 55)
        else:
            print(f"\nCentral Display — vehicle speed updated: {speed} km/h")
    except Exception as exc:
        print(f"Vehicle event decode error: {exc}")


def climate_event_callback(event_id: int, payload: bytes):
    try:
        temperature = TemperaturePayload().deserialize(payload)
        print(
            f"\nCentral Display — cabin temperature updated: "
            f"{temperature.temperature_tenths_c.value / 10:.1f} °C"
        )
    except Exception as exc:
        print(f"Climate event decode error: {exc}")


async def wait_for_service(client, label: str):
    while not await client.is_available():
        print(f"{label}: NOT AVAILABLE — waiting...")
        await asyncio.sleep(1)
    print(f"{label}: AVAILABLE")


async def vehicle_poll_loop(client):
    while True:
        try:
            speed_result = await client.call_method(GET_SPEED_METHOD_ID, b"")
            if (
                speed_result.message_type == MessageType.RESPONSE
                and speed_result.return_code == ReturnCode.E_OK
            ):
                speed = SpeedPayload().deserialize(speed_result.payload)
                print(f"\nCentral Display — vehicle speed: {speed.speed_kmph.value} km/h")

            state_result = await client.call_method(GET_VEHICLE_STATE_METHOD_ID, b"")
            if (
                state_result.message_type == MessageType.RESPONSE
                and state_result.return_code == ReturnCode.E_OK
            ):
                state = VehicleStatePayload().deserialize(state_result.payload)
                name = "MOVING" if state.state.value == MOVING else "STOPPED"
                print(f"Central Display — vehicle state: {name}")
        except Exception as exc:
            print(f"VehicleSpeedService request failed: {exc}")
        await asyncio.sleep(6)


async def climate_poll_loop(client, target_tenths):
    first_cycle = True
    while True:
        try:
            if first_cycle:
                request = SetTemperatureRequest(target_tenths).serialize()
                result = await client.call_method(
                    SET_TARGET_TEMPERATURE_METHOD_ID,
                    request,
                )
                if (
                    result.message_type == MessageType.RESPONSE
                    and result.return_code == ReturnCode.E_OK
                ):
                    response = SetTemperatureResponse().deserialize(result.payload)
                    if response.status.value == ACCEPTED:
                        print(
                            f"\nCentral Display — target temperature "
                            f"{target_tenths / 10:.1f} °C ACCEPTED"
                        )
                    else:
                        print(
                            f"\nCentral Display — target temperature "
                            f"{target_tenths / 10:.1f} °C INVALID"
                        )
                first_cycle = False

            result = await client.call_method(GET_CABIN_TEMPERATURE_METHOD_ID, b"")
            if (
                result.message_type == MessageType.RESPONSE
                and result.return_code == ReturnCode.E_OK
            ):
                temperature = TemperaturePayload().deserialize(result.payload)
                print(
                    f"Central Display — cabin temperature: "
                    f"{temperature.temperature_tenths_c.value / 10:.1f} °C"
                )
        except Exception as exc:
            print(f"ClimateService request failed: {exc}")
        await asyncio.sleep(6)


async def main(target_tenths):
    set_someipy_log_level(logging.INFO)

    print("=" * 60)
    print("CENTRAL DISPLAY ECU")
    print("Consumes VehicleSpeedService and ClimateService")
    print("=" * 60)

    daemon = await connect_to_someipy_daemon()

    vehicle_client = ClientServiceInstance(
        daemon=daemon,
        service=vehicle_speed_service,
        instance_id=VEHICLE_INSTANCE_ID,
        endpoint_ip=VEHICLE_IP,
        endpoint_port=DISPLAY_VEHICLE_PORT,
    )
    vehicle_client.register_callback(vehicle_event_callback)

    climate_client = ClientServiceInstance(
        daemon=daemon,
        service=climate_service,
        instance_id=CLIMATE_INSTANCE_ID,
        endpoint_ip=CLIMATE_IP,
        endpoint_port=DISPLAY_PORT,
    )
    climate_client.register_callback(climate_event_callback)

    # Discover and consume each service independently. The Central Display
    # can use one provider even while the other provider is unavailable.
    async def consume_vehicle_service():
        await wait_for_service(vehicle_client, "VehicleSpeedService")
        vehicle_client.subscribe_eventgroup(speed_eventgroup, 5)
        vehicle_client.subscribe_eventgroup(overspeed_eventgroup, 5)
        print("Central Display subscribed to vehicle event groups.")
        await vehicle_poll_loop(vehicle_client)

    async def consume_climate_service():
        await wait_for_service(climate_client, "ClimateService")
        climate_client.subscribe_eventgroup(cabin_temperature_eventgroup, 5)
        print("Central Display subscribed to climate event group.")
        await climate_poll_loop(climate_client, target_tenths)

    tasks = [
        asyncio.create_task(consume_vehicle_service()),
        asyncio.create_task(consume_climate_service()),
    ]

    try:
        await asyncio.gather(*tasks)
    finally:
        for task in tasks:
            task.cancel()
        for task in tasks:
            try:
                await task
            except asyncio.CancelledError:
                pass
        await daemon.disconnect_from_daemon()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--target-tenths",
        type=int,
        default=220,
        help="Requested target temperature in tenths of °C (default: 220 = 22.0 °C)",
    )
    args = parser.parse_args()

    try:
        asyncio.run(main(args.target_tenths))
    except KeyboardInterrupt:
        print("\nCentral Display stopped.")
