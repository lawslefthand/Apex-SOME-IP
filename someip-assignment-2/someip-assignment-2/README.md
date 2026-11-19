# SOME/IP Assignment 2 — Multi-ECU Vehicle Network

This project extends Assignment 1 into four logical ECUs:

1. Vehicle ECU — provides `VehicleSpeedService`
2. Instrument Cluster ECU — consumes `VehicleSpeedService`
3. Climate ECU — provides `ClimateService`
4. Central Display ECU — consumes both services

The applications use the `someipy` Python library and a separate `someipyd` daemon.

## Project layout

```text
someip-assignment-2/
├── src/
│   ├── vehicle_speed_interface.py
│   ├── vehicle_speed_service.py
│   ├── cluster_client.py
│   ├── climate_interface.py
│   ├── climate_service.py
│   └── central_display.py
├── config/someipyd.json
├── captures/
├── images/
├── requirements.txt
└── README.md
```

## Setup

```bash
cd ~/someip-assignment-2
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If you already have a compatible `someipy` environment, activate that environment instead of creating another one.

## Important implementation note

The subscription TTL passed to `subscribe_eventgroup()` is an integer (`5`), not a float (`5.0`), because the installed someipy API rejects floats.

The code uses the `Int16` serializer for signed 16-bit climate temperatures. Confirm that your installed `someipy.serialization` exposes `Int16` before running:

```bash
python -c "from someipy.serialization import Int16, Uint8, Uint16; print('Serializers OK')"
```

## Run order

Open five terminals. Activate the same virtual environment and change to this project directory in each terminal.

### Terminal 1 — someipy daemon

```bash
cd ~/someip-assignment-2
source .venv/bin/activate
someipyd --config config/someipyd.json
```

### Terminal 2 — Vehicle ECU provider

```bash
cd ~/someip-assignment-2
source .venv/bin/activate
python src/vehicle_speed_service.py
```

### Terminal 3 — Instrument Cluster consumer

```bash
cd ~/someip-assignment-2
source .venv/bin/activate
python src/cluster_client.py
```

### Terminal 4 — Climate ECU provider

```bash
cd ~/someip-assignment-2
source .venv/bin/activate
python src/climate_service.py
```

### Terminal 5 — Central Display consumer

```bash
cd ~/someip-assignment-2
source .venv/bin/activate
python src/central_display.py
```

## Climate validation tests

Default target request is 22.0 °C:

```bash
python src/central_display.py --target-tenths 220
```

Valid boundary values:

```bash
python src/central_display.py --target-tenths 160
python src/central_display.py --target-tenths 300
```

Invalid values:

```bash
python src/central_display.py --target-tenths 100
python src/central_display.py --target-tenths 350
```

Temperature is encoded in tenths of a degree Celsius: `220` means `22.0 °C`.

## Syntax and import checks

```bash
python -m py_compile src/*.py
python -c "from someipy.serialization import Int16, Uint8, Uint16; print('Serializer imports OK')"
```

## Wireshark

Capture on the loopback interface (`lo`). Start with:

```text
udp.port == 30490 || udp.port == 3000 || udp.port == 3002 || udp.port == 3004 || udp.port == 3010 || udp.port == 3012
```

Save the capture as:

```text
captures/assignment2-multi-ecu.pcapng
```

## Service identifiers

| Service | Service ID | Instance ID |
|---|---:|---:|
| VehicleSpeedService | `0x1234` | `0x5678` |
| ClimateService | `0x2234` | `0x0001` |

VehicleSpeedService:
- `GetSpeed`: method `0x0001`
- `GetVehicleState`: method `0x0002`
- `SpeedChanged`: event `0x8001`, group `0x0001`
- `OverspeedWarning`: event `0x8002`, group `0x0002`

ClimateService:
- `GetCabinTemperature`: method `0x0001`
- `SetTargetTemperature`: method `0x0002`
- `CabinTemperatureChanged`: event `0x8001`, group `0x0001`

Different services may reuse method and event IDs; the Service ID is also part of the SOME/IP message identity.

## Runtime compatibility

This code is based on the API pattern in the supplied Assignment 1 code and the Assignment 2 interface specification. Python syntax checks do not guarantee compatibility with every `someipy` release. Resolve any version-specific API errors against the installed package before treating the system as validated.
