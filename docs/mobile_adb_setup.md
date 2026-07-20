# Mobile ADB Setup

This is a one-time setup so the sync daemon can reach your phone over the same Wi-Fi network.

## Phase 3 prerequisites for phone notifications

1. Install `mkcert` on the laptop and run `mkcert -install` to add the local CA to the machine trust store.
2. Generate a certificate for the laptop LAN IP and localhost together, for example: `mkcert 192.168.x.x localhost 127.0.0.1`.
3. Save the generated certificate and key paths into `config.json` under an `https` section with `use_https: true`.
4. Export the mkcert root CA location from `mkcert -CAROOT` and install that root CA on the phone so Chrome trusts the local HTTPS endpoint.
5. If Android asks for the certificate type, install it as a CA certificate, not a VPN or Wi-Fi certificate.

1. On the phone: Settings → About Phone → tap "Build Number" 7 times to enable Developer Options.
2. Settings → Developer Options → enable "Wireless debugging".
3. Tap "Wireless debugging" → "Pair device with pairing code". This shows an IP:port and a 6-digit code.
4. On the laptop, run `adb pair <ip>:<port>` and enter the code when prompted.
5. Note the phone's regular Wireless Debugging IP:port shown on the same screen. This is the address the sync daemon will use going forward as long as both devices remain on the same Wi-Fi.
6. Confirm `adb connect <ip>:<port>` then `adb devices` shows the phone as `device`.

Known limitation: if the phone gets a new Wi-Fi IP address, the ADB target can change. If syncing stops after a network change, re-run the pairing/connect steps above.

The laptop LAN IP can change too. If it does, regenerate the mkcert certificate and update the paths in `config.json`.

## Phone notifications

1. Open the dashboard in Chrome on your phone.
2. Grant notification permission when prompted.
3. Use the browser menu to add the dashboard to your home screen.
4. Open the installed shortcut from the home screen so Web Push can register and receive alerts even when the tab is not open.