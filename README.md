# Novo SysControl for Home Assistant

Custom Home Assistant integration for controlling Novo ND-M1000 screens over the local network. Add each screen separately to control multiple screens independently.

## Prepare the screen

Connect the screen to a network reachable from Home Assistant. Use a fixed IP address or DHCP reservation so its address stays the same.

Check the screen's settings for **SysControl**, **Network-based control**, or an equivalent option, and enable it if present. An ND-M1000-specific menu path and default enabled state have not been confirmed. Some other Novo models require this option to be enabled; do not assume those models' menu paths apply to the ND-M1000.

Home Assistant must be able to connect to the screen over **TCP port 5050**, or your configured port. The ND-M1000 sends this greeting before accepting commands:

```text
[ND-M1000] Hello, please enter your command :
```

The integration's TCP client must wait for the complete greeting before sending a command.

## Install

Once the integration files are available:

1. Copy the entire `novo_syscontrol` integration directory into your Home Assistant configuration directory under `custom_components`.
2. Confirm that the resulting path includes `custom_components/novo_syscontrol/manifest.json`, alongside the integration's Python files. Avoid an extra nested `novo_syscontrol` directory.
3. Restart Home Assistant.
4. Open **Settings → Devices & services → Add integration**.
5. Search for **Novo SysControl** and select it.
6. Complete the configuration form:
   - **Name**: a friendly name for this screen, such as `Meeting Room`.
   - **Host**: the screen's IP address or resolvable hostname, without a URL scheme or port.
   - **Port**: the TCP control port; default **5050**.
7. Submit the form. Repeat **Add integration** for each additional screen, using its own host and name.

## Entities

Each screen is intended to create these entities. Home Assistant derives their entity IDs from the device name; IDs can change if renamed or if a name is already in use.

- **Power switch**: wake the screen or place it in standby.
- **Mute switch**: mute or unmute audio.
- **Volume number**: set audio volume from **0 to 100**.
- **Backlight number**: set backlight level from **0 to 100**.
- **Source select**: choose **HDMI 1**, **HDMI 2**, **VGA**, or **Android**. These map to protocol arguments `hdmi1`, `hdmi2`, `VGA`, and `android`, respectively.
- **Power sensor**: report the power state, such as `wakeup` or `standby`.
- **Source sensor**: report the current input source.
- **Model sensor**: report the device model, such as `ND-M1000`.

The source list above reflects the agreed design. Additional physical inputs are not automatically supported; their command values and implementation would need to be confirmed first.

## Send a raw command

The intended action **`novo_syscontrol.send_command`** sends one SysControl command to one configured screen. It accepts these fields:

- **`entry_id`** (required): the Home Assistant **configuration entry ID** for that screen. This is not its entity ID, device ID, name, or IP address.
- **`command`** (required): the ASCII command string, including any argument, for example `volume 40`. Do not include the greeting or a newline.

To look up an entry ID, open **Developer tools → Template** and use an entity belonging to the desired screen:

```jinja
{{ config_entry_id('switch.meeting_room_power') }}
```

Replace that entity ID with the actual entity shown in your installation. Copy the resulting entry ID into the action data.

For example, in **Developer tools → Actions**, select YAML mode and run:

```yaml
action: novo_syscontrol.send_command
data:
  entry_id: "REPLACE_WITH_YOUR_SCREEN_CONFIG_ENTRY_ID"
  command: "volume 40"
```

Use the same action block in an automation's action sequence. For routine control, the switches, numbers, and source select provide a simpler interface.

The action's response data and whether it immediately refreshes entities depend on the implementation; neither is verified in this repository. Query commands below describe the device protocol, not a guarantee that their replies are returned to the Home Assistant action caller.

### Device commands

The ND-M1000 command set used by this integration design is:

**Set commands**

- `wakeup`: wake the screen.
- `standby`: enter standby.
- `mute` / `unmute`: enable or disable audio muting.
- `volume N`: set volume, where `N` is an integer from 0 to 100.
- `backlight N`: set backlight, where `N` is an integer from 0 to 100.
- `source hdmi1`, `source hdmi2`, `source VGA`, `source android`: choose an input. Preserve the shown capitalization.

**Query commands**

- `powerstate`: power state.
- `sourcestate`: selected input.
- `volstate`: volume.
- `mutestate`: mute state.
- `blstate`: backlight level.
- `query`: model name.

The ND-M1000 supports source and backlight control, as confirmed by the screen owner. Signage commands **`play`**, **`stop`**, and **`getlist`** are **not supported** on this model.

## Troubleshooting

- **Integration does not appear**: check the installation directory and restart Home Assistant. The complete integration must be installed, not just this README.
- **Cannot connect**: check the host, port, network routing, firewall rules, and the screen's network-control setting if available.
- **Connects but commands fail**: verify the greeting is received completely before the client sends commands. Command line endings and reply parsing must match the screen's firmware.
- **Cannot wake from standby**: check whether the screen keeps network control available in standby. Network wake capability for every power-saving mode has not been confirmed.
- **Action targets the wrong screen or fails**: verify `entry_id` belongs to the intended configuration entry.

## References

- [Novo SysControl protocol documentation](https://support.launchnovo.com/kb/bk3-syscontrol-network-based-control/) — TCP transport and general command reference; it is not an ND-M1000-specific compatibility guarantee.
- [Novo NC-X910/NC-X710 release notes](https://support.launchnovo.com/kb/nc-x910-nc-x710-release-notes/?print=print) — evidence that enabling SysControl is required on some other Novo models; ND-M1000 settings may differ.
