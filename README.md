[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge)](https://github.com/custom-components/hacs)

# jablotron80
Home Assistant custom component for JABLOTRON 80 alarm system

## Preparation

1. Connect the USB or Serial cable to Jablotron central unit
2. Restart the Home Assistant OS
3. Use the following command line to identify the port:

    ```
    $ dmesg | grep usb
    ```

    The cable should be connected as `/dev/hidraw[x]`, `/dev/ttyUSB0` or similar.

## Installation

### HACS

1. Just use [HACS](https://hacs.xyz/) (Home Assistant Community Store)  
    <small>*HACS is a third party community store and is not included in Home Assistant out of the box.*</small>

### Manual

1. [Download integration](https://github.com/tahvane1/jablotron80)
2. Copy the folder `custom_components/jablotron80` from the zip to your config directory
3. Restart Home Assistant
4. Jablotron integration should be available in the integrations UI

## Issues

Report [issue](https://github.com/tahvane1/jablotron80/issues)

## Supported devices

This integration has been tested with JA-80K /JA-82K central units, JA-81F keypad and both JA-82T usb and JA-80T serial cables.
Tested sensors include wired/wireless PIRs & door sensors and wired/wireless fire alarms.

## Remote Support
The JA-80T serial cable setup can work with remote serial devices using a device address of 'socket://[ipaddress:socket]', see section at bottom of page for more details. This can be made to work even without a JA-80T serial cable (as these are hard to source)

## Examples & configuration

### Initial configuration
Integration support configuration flow via UI. 

It will ask for serial device to use and master passcode.
It will ask also for number of devices to be included as jablotron will by default have 50 devices (those could be configured off but at least in my case were not). This is just for convenience. 
Master passcode will be used to fetch configuration from central unit (device types, reactions, serial numbers, codes, arming without code). It will also be used to arm/disarm system if it is allowed without code in Home Assistant side (integration options).

### Configured integration
<img src="examples/integration.png" alt="Integration overview" width="200" />


#### Devices
Integration will create one device per configured devices and additionally one for central unit (tamper alarm), one for connection and one for Home Assistant panel.

<img src="examples/integration_devices.png" alt="Integration devices" width="600"/>


#### Entities

Integration will create one binary sensor per jablotron device, one for each led in keypad and one for each configured code. It will also create RF level sensor for RF signal and status sensor for each used zone.

<img src="examples/integration_entities.png" alt="Integration entities" width="600"/>

Each sensor has additional state attributes depending in jablotron configuration.

<img src="examples/integration_example_sensor.png" alt="Example sensor" width="200"/>

#### Example control panel

Example of a configuration in lovelace which attempts to reproduce the Jablotron panel on top of the standard home assistant alarm panel: 

```
type: vertical-stack
cards:
  - type: horizontal-stack
    cards:
      - type: button
        entity: binary_sensor.ja_80k_alarm
        icon: mdi:alert-outline
        color_type: icon
        show_name: false
        show_state: false
        state:
          - value: 'on'
            color: rgb(255,5,5)
          - value: 'off'
            color: var(--disabled-text-color)
        tap_action:
          action: call-service
          service: button.press
          service_data:
            entity_id: button.ja_80k_query_button
      - type: button
        entity: binary_sensor.ja_80k_zone_a_armed
        icon: mdi:alpha-a
        color_type: icon
        show_name: false
        show_state: false
        state:
          - value: 'on'
            color: rgb(255,5,5)
          - value: 'off'
            color: var(--disabled-text-color)
      - type: button
        entity: binary_sensor.ja_80k_zone_b_armed
        icon: mdi:alpha-b
        color_type: icon
        show_name: false
        show_state: false
        state:
          - value: 'on'
            color: rgb(255,5,5)
          - value: 'off'
            color: var(--disabled-text-color)
      - type: button
        entity: binary_sensor.ja_80k_zone_c_armed
        icon: mdi:alpha-c
        color_type: icon
        show_name: false
        show_state: false
        state:
          - value: 'on'
            color: rgb(255,5,5)
          - value: 'off'
            color: var(--disabled-text-color)
      - type: button
        entity: binary_sensor.ja_80k_power
        icon: mdi:power
        color_type: icon
        show_name: false
        show_state: false
        state:
          - value: 'on'
            color: rgb(5,255,5)
          - value: 'off'
            color: var(--disabled-text-color)
  - type: conditional
    conditions:
      - entity: sensor.ja_80k_alert
        state_not: OK
    card:
      type: entity
      entity: sensor.ja_80k_alert
      attribute: message
      name: Alert
      state_color: false
      icon: mdi:alert
      style: |
        ha-card
        .value {
          font-size: 22px
        }
  - type: conditional
    conditions:
      - entity: binary_sensor.ja_80k_status_text
        state: 'on'
    card:
      type: entity
      entity: binary_sensor.ja_80k_status_text
      icon: mdi:information
      name: Keypad Message
      attribute: message
  - type: alarm-panel
    states:
      - arm_home
      - arm_away
      - arm_night
    entity: alarm_control_panel.jablotron_control_panel_a_ab_abc
    name: House Alarm
  - type: entity
    entity: binary_sensor.ja_80k_control_panel
    attribute: last event
    name: Last Event
    icon: mdi:history
    style: |
      ha-card
      .value {
        font-size: 16px
      }
```

Screenshot of alarm control panel

<img src="examples/lovelace-card.png" alt="Alarm control panel" width="200"/>



#### Enhanced control panel

If you would like to enhance the example with coloured buttons and flashing Warning and Power 'leds' and are prepared to install the custom button card https://github.com/custom-cards/button-card (installable via HACS), you can use the following snippet

Screenshot of enhanced alarm control panel

<img src="examples/lovelace-card-custom.png" alt="Enhanced Alarm control panel" width="200"/>

```
type: horizontal-stack
cards:
  - type: custom:button-card
    entity: sensor.ja_80k_alert
    icon: mdi:alert-outline
    color_type: icon
    show_name: false
    show_state: false
    state:
      - value: Fault
        color: rgb(255,5,5)
      - value: Alarm
        color: rgb(255,5,5)
        styles:
          card:
            - animation: blink 2s ease infinite
      - value: OK
        color: var(--disabled-text-color)
    tap_action:
      action: call-service
      service: button.press
      service_data:
        entity_id: button.ja_80k_query_button
    hold_action:
      action: more-info
  - type: custom:button-card
    entity: binary_sensor.ja_80k_zone_a_armed
    icon: mdi:alpha-a
    color_type: icon
    show_name: false
    show_state: false
    state:
      - value: 'on'
        color: rgb(255,5,5)
      - value: 'off'
        color: var(--disabled-text-color)
  - type: custom:button-card
    entity: binary_sensor.ja_80k_zone_b_armed
    icon: mdi:alpha-b
    color_type: icon
    show_name: false
    show_state: false
    state:
      - value: 'on'
        color: rgb(255,5,5)
      - value: 'off'
        color: var(--disabled-text-color)
  - type: custom:button-card
    entity: binary_sensor.ja_80k_zone_c_armed
    icon: mdi:alpha-c
    color_type: icon
    show_name: false
    show_state: false
    state:
      - value: 'on'
        color: rgb(255,5,5)
      - value: 'off'
        color: var(--disabled-text-color)
  - type: custom:button-card
    entity: binary_sensor.ja_80k_power
    icon: mdi:power
    color_type: icon
    show_name: false
    show_state: false
    state:
      - value: 'on'
        color: rgb(5,255,5)
      - value: 'off'
        color: rgb(5,255,5)
        styles:
          card:
            - animation: blink 2s ease infinite

```

## Remote
Generic remote serial devices are expected to be able to be made to work with this integration.

A confirmed workinging confiuration is documented below:

|Description   |Supplier   |Part Number   |Comment   |URL/Search Terms   |
|---|---|---|---|---|
|TTL to Ethernet Converter|USR IOT Technology Limited  |USR-TCP232-T2|Direct connection prefered as opposed to WiFi for performance|   |
|TTL to RS485 converter|MAX|MAX3485||
|3.3V or 5v step down power transformer|||Connected to the 12V power supply on the Jablotron board||

Serial Port to be setup as `9600 baud, 8 bit, no partity, 1 stop bit`. Must be set-up as `TCP Server`

Additional expected similar solutions could be constructed from USR-TCP232-306, USR-TCP232-304 connected directly to the control panel or
USR-TCP232-302 conected to an existing JA-80T serial cable.

## Troubleshooting

Additional logging can be enabled in configuration.yaml

```
logger:
 logs:
   custom_components.jablotron80: debug
```
Raw data send by cable can be seen in logs by setting above and uncommentting following lines in jablotron.py (around line number )
```
			#UNCOMMENT THESE LINES TO SEE RAW DATA (produces a lot of logs)
			#if LOGGER.isEnabledFor(logging.DEBUG):
			#	formatted_data = " ".join(["%02x" % c for c in data])
			#	LOGGER.debug(f'Received raw data {formatted_data}')
```
## Credits

Thanks to [kukulich](https://github.com/kukulich/home-assistant-jablotron100), [fwpt](https://github.com/fwpt/HASS-Jablotron80-T/tree/master/custom_components/Jablotron80) and [mattsaxon](https://github.com/mattsaxon/HASS-Jablotron80) for figuring out Jablotron functionality and Home Assistant essentials.
