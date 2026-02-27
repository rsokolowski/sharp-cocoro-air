"""Sharp COCORO Air EU Cloud API client.

Reverse-engineered from the Sharp Life AIR EU app (jp.co.sharp.hms.smartlink.eu).
"""

import http.cookiejar
import logging
import random
import string
import urllib.error
import urllib.parse
import urllib.request

import httpx

_LOGGER = logging.getLogger(__name__)

# EU Configuration (extracted from APK)
APP_SECRET = "pngtfljRoYsJE9NW7opn1t2cXA5MtZDKbwon368hs80="
API_BASE = "https://eu-hms.cloudlabs.sharp.co.jp/hems/pfApi/ta/"
AUTH_BASE = "https://auth-eu.global.sharp"
CLIENT_ID = "8c7f4378-5f26-4618-9854-483ad86bec0a"
CLIENT_SECRET = "mdESudik3JxWTrpWw3y6jQLi3zERaTBP"
REDIRECT_URI = "sharp-cocoroair-eu://authorize"
USER_AGENT = (
    "smartlink_v200a_eu Mozilla/5.0 (Linux; Android 14) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Mobile"
)
BROWSER_UA = (
    "Mozilla/5.0 (Linux; Android 14) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Mobile"
)
HA_APP_NAME = "spremote_ha_eu:1:1.0.0"

# ECHONET Lite mode mappings
ECHONET_OPERATION_MODES = {
    0x10: "Auto", 0x11: "Night", 0x13: "Pollen", 0x14: "Silent",
    0x15: "Medium", 0x16: "High", 0x20: "AI Auto", 0x40: "Realize",
}

ECHONET_CLEANING_MODES = {
    0x41: "Cleaning", 0x42: "Humidifying",
    0x43: "Cleaning + Humidifying", 0x44: "Off",
}


class SharpAuthError(Exception):
    """Authentication failed."""


class SharpConnectionError(Exception):
    """Network/connection error."""


class SharpApiError(Exception):
    """General API error."""


class _StopOnCustomScheme(urllib.request.HTTPRedirectHandler):
    """Capture redirects to custom URI schemes instead of following them."""

    def __init__(self):
        self.redirect_url = None

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if newurl.startswith("sharp-cocoroair-eu://"):
            self.redirect_url = newurl
            return None
        return super().redirect_request(req, fp, code, msg, headers, newurl)

    def http_error_302(self, req, fp, code, msg, headers):
        loc = headers.get("Location", "")
        if loc.startswith("sharp-cocoroair-eu://"):
            self.redirect_url = loc
            return fp
        return super().http_error_302(req, fp, code, msg, headers)

    http_error_301 = http_error_302
    http_error_303 = http_error_302


def decode_echonet_property(hex_string: str) -> dict:
    """Decode ECHONET Lite property hex from the Sharp cloud API."""
    if not hex_string or len(hex_string) < 16:
        return {}

    data = bytes.fromhex(hex_string)

    # Parse TLV properties starting at byte 8 (after header)
    raw_props = {}
    i = 8
    while i + 1 < len(data):
        code = data[i]
        length = data[i + 1]
        if i + 2 + length > len(data):
            break
        raw_props[code] = data[i + 2 : i + 2 + length]
        i += 2 + length

    result = {}

    # 0x80: Power status
    if 0x80 in raw_props:
        v = raw_props[0x80][0]
        result["power"] = "on" if v == 0x30 else "off" if v == 0x31 else f"0x{v:02X}"

    # 0x84: Instantaneous power consumption (W)
    if 0x84 in raw_props:
        result["power_watts"] = int.from_bytes(raw_props[0x84], "big")

    # 0x85: Cumulative energy (Wh)
    if 0x85 in raw_props:
        result["energy_wh"] = int.from_bytes(raw_props[0x85], "big")

    # 0x88: Fault status
    if 0x88 in raw_props:
        v = raw_props[0x88][0]
        result["fault"] = v == 0x41

    # 0x8B: Firmware version (ASCII)
    if 0x8B in raw_props:
        result["firmware"] = raw_props[0x8B].decode("ascii", errors="replace")

    # 0xA0: Air flow rate
    if 0xA0 in raw_props:
        v = raw_props[0xA0][0]
        result["airflow"] = (
            "auto"
            if v == 0x41
            else f"level_{v - 0x30}" if 0x31 <= v <= 0x38 else f"0x{v:02X}"
        )

    # 0xC0: Cleaning mode
    if 0xC0 in raw_props:
        v = raw_props[0xC0][0]
        result["cleaning_mode"] = ECHONET_CLEANING_MODES.get(v, f"0x{v:02X}")

    # 0xF1: State detail (Sharp proprietary - 40 bytes)
    if 0xF1 in raw_props:
        f1 = raw_props[0xF1]
        if len(f1) >= 5:
            result["temperature_c"] = int.from_bytes(
                bytes([f1[3]]), "big", signed=True
            )
            result["humidity_pct"] = f1[4]
        if len(f1) >= 38:
            result["pci_sensor"] = (f1[15] << 8) | f1[16]
            result["filter_usage"] = (
                (f1[21] << 24) | (f1[22] << 16) | (f1[23] << 8) | f1[24]
            )
            result["dust"] = (f1[29] << 8) | f1[30]
            result["smell"] = (f1[31] << 8) | f1[32]
            result["humidity_filter"] = (f1[35] << 8) | f1[36]
            result["light_sensor"] = f1[37]

    # 0xF3: Operation mode (Sharp proprietary - 27 bytes)
    if 0xF3 in raw_props:
        f3 = raw_props[0xF3]
        if len(f3) >= 5:
            result["operation_mode"] = ECHONET_OPERATION_MODES.get(
                f3[4], f"0x{f3[4]:02X}"
            )
        if len(f3) >= 16:
            result["humidify"] = f3[15] == 0xFF

    return result


class SharpAPI:
    """Client for the Sharp EU HMS cloud API."""

    def __init__(self, email: str, password: str) -> None:
        self.email = email
        self.password = password
        self.terminal_app_id: str | None = None
        self._client: httpx.Client | None = None

    def _ensure_client(self) -> httpx.Client:
        """Create httpx client lazily (avoids blocking the event loop on init)."""
        if self._client is None:
            self._client = httpx.Client(
                timeout=30,
                headers={
                    "User-Agent": USER_AGENT,
                    "Content-Type": "application/json; charset=utf-8",
                    "Accept": "application/json",
                },
            )
        return self._client

    def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None:
            self._client.close()

    def full_init(self) -> None:
        """Perform the complete initialization sequence."""
        self._ensure_client()
        self.login()
        self.get_user_info()
        self.register_terminal()
        self.pair_boxes()

    def _hms_request(
        self, path: str, method: str = "GET", body: dict | None = None,
        extra_params: dict | None = None,
    ) -> dict:
        """Make a request to the HMS API."""
        parts = [f"appSecret={APP_SECRET}"]
        if extra_params:
            for k, v in extra_params.items():
                parts.append(f"{k}={v}")
        query = "&".join(parts)
        url = f"{API_BASE}{path}?{query}"

        client = self._ensure_client()
        try:
            if method == "GET":
                resp = client.get(url)
            else:
                resp = client.post(url, json=body)
        except httpx.ConnectError as err:
            raise SharpConnectionError(f"Connection failed: {err}") from err
        except httpx.TimeoutException as err:
            raise SharpConnectionError(f"Request timed out: {err}") from err

        if resp.status_code in (401, 403):
            raise SharpAuthError(
                f"Auth error {resp.status_code} on {path}: {resp.text[:200]}"
            )
        if resp.status_code >= 400:
            raise SharpApiError(
                f"API error {resp.status_code} on {path}: {resp.text[:200]}"
            )

        return resp.json() if resp.text else {}

    def login(self) -> None:
        """Full login: get terminalAppId, OAuth, then HMS login."""
        # Step 1: Get terminalAppId
        data = self._hms_request("setting/terminalAppId/")
        self.terminal_app_id = data["terminalAppId"]

        # Step 2: OAuth login
        nonce = "".join(random.choices(string.ascii_letters + string.digits, k=32))
        auth_cookies = http.cookiejar.CookieJar()
        redirect_handler = _StopOnCustomScheme()
        auth_opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(auth_cookies), redirect_handler
        )

        auth_params = urllib.parse.urlencode({
            "scope": "openid profile email",
            "client_id": CLIENT_ID,
            "response_type": "code",
            "redirect_uri": REDIRECT_URI,
            "nonce": nonce,
            "ui_locales": "en",
            "prompt": "login",
        })
        auth_url = f"{AUTH_BASE}/oxauth/restv1/authorize?{auth_params}"

        try:
            req = urllib.request.Request(auth_url)
            req.add_header("User-Agent", BROWSER_UA)
            resp = auth_opener.open(req, timeout=30)
            resp.read()

            form_data = urllib.parse.urlencode({
                "loginForm": "loginForm",
                "javax.faces.ViewState": "stateless",
                "loginForm:username": self.email,
                "loginForm:password": self.password,
                "loginForm:loginButton": "",
            }).encode()

            login_url = f"{AUTH_BASE}/oxauth/login.htm"
            req = urllib.request.Request(login_url, data=form_data, method="POST")
            req.add_header("User-Agent", BROWSER_UA)
            req.add_header("Content-Type", "application/x-www-form-urlencoded")
            req.add_header("Referer", auth_url)

            resp = auth_opener.open(req, timeout=30)
            resp.read()
        except urllib.error.URLError as err:
            raise SharpConnectionError(f"OAuth connection failed: {err}") from err

        if not redirect_handler.redirect_url:
            raise SharpAuthError("OAuth login failed - invalid credentials")

        parsed = urllib.parse.urlparse(redirect_handler.redirect_url)
        params = urllib.parse.parse_qs(parsed.query)
        auth_code = params.get("code", [None])[0]
        if not auth_code:
            raise SharpAuthError("No auth code in redirect URL")

        # Step 3: HMS login with auth code + nonce
        body = {
            "terminalAppId": self.terminal_app_id,
            "tempAccToken": auth_code,
            "password": nonce,
        }
        self._hms_request(
            "setting/login/",
            method="POST",
            body=body,
            extra_params={"serviceName": "sharp-eu"},
        )

    def get_user_info(self) -> dict:
        """GET setting/userInfo - called after login in the app flow."""
        return self._hms_request(
            "setting/userInfo",
            extra_params={"terminalAppId": self.terminal_app_id},
        )

    def register_terminal(self) -> dict:
        """POST setting/terminal - register terminal info with the server.

        This step is required before control/ POST endpoints will work.
        """
        body = {
            "name": "HomeAssistant",
            "os": "Android",
            "osVersion": "14",
            "pushId": "",
            "appName": HA_APP_NAME,
        }
        url = f"{API_BASE}setting/terminal?appSecret={APP_SECRET}"
        client = self._ensure_client()
        try:
            resp = client.post(url, json=body)
        except (httpx.ConnectError, httpx.TimeoutException) as err:
            raise SharpConnectionError(
                f"Terminal registration failed: {err}"
            ) from err

        if resp.status_code in (401, 403):
            raise SharpAuthError(
                f"Terminal registration auth error: {resp.status_code}"
            )
        if resp.status_code != 200:
            raise SharpApiError(
                f"Terminal registration failed: {resp.status_code} "
                f"{resp.text[:200]}"
            )
        return resp.json() if resp.text else {}

    def get_boxes(self) -> dict:
        """List all registered devices (boxes) with full echonet data."""
        return self._hms_request("setting/boxInfo", extra_params={"mode": "other"})

    def pair_boxes(self) -> None:
        """Pair our terminalAppId with all boxes.

        Cleans up stale TAIs to stay within the 5-TAI limit:
        - appName=None: orphaned script-generated TAIs
        - appName starting with "spremote_ha_eu": old HA integration TAIs
        Never touches the real phone app entries (spremote_a_eu).
        """
        client = self._ensure_client()
        boxes = self.get_boxes()
        for box in boxes.get("box", []):
            box_id = box["boxId"]
            for tai in box.get("terminalAppInfo", []):
                if tai["terminalAppId"] == self.terminal_app_id:
                    continue  # keep our own
                app_name = tai.get("appName")
                if app_name is not None and not app_name.startswith("spremote_ha_eu"):
                    continue  # keep phone app and other real entries
                url = (
                    f"{API_BASE}setting/pairing/"
                    f"?appSecret={APP_SECRET}"
                    f"&terminalAppId={tai['terminalAppId']}"
                    f"&boxId={box_id}&houseFlag=true"
                )
                try:
                    client.put(url)
                except (httpx.ConnectError, httpx.TimeoutException):
                    _LOGGER.warning("Failed to unpair TAI %s", tai["terminalAppId"])
            # Pair our TAI
            url = (
                f"{API_BASE}setting/pairing/"
                f"?appSecret={APP_SECRET}&boxId={box_id}&houseFlag=true"
            )
            try:
                resp = client.post(url, content=b"")
            except (httpx.ConnectError, httpx.TimeoutException) as err:
                _LOGGER.warning("Failed to pair box %s: %s", box_id, err)
                continue
            if resp.status_code not in (200, 201):
                _LOGGER.warning(
                    "Pairing box %s: %s %s",
                    box_id, resp.status_code, resp.text[:100],
                )

    def get_devices(self) -> list[dict]:
        """Get parsed device list with decoded sensor data."""
        boxes = self.get_boxes()
        devices = []
        for box in boxes.get("box", []):
            box_id = box.get("boxId")
            for edev in box.get("echonetData", []):
                label = edev.get("labelData", {})
                props = decode_echonet_property(edev.get("echonetProperty", ""))
                devices.append({
                    "box_id": box_id,
                    "device_id": edev.get("deviceId"),
                    "name": label.get("name", "Sharp Air Purifier"),
                    "maker": edev.get("maker"),
                    "model": edev.get("model"),
                    "echonet_node": edev.get("echonetNode"),
                    "echonet_object": edev.get("echonetObject"),
                    "updated_at": edev.get("propertyUpdatedAt"),
                    "properties": props,
                })
        return devices

    def send_device_control(self, device: dict, status_list: list[dict]) -> dict:
        """Send a control command to a device."""
        body = {
            "controlList": [{
                "deviceId": device["device_id"],
                "echonetNode": device["echonet_node"],
                "echonetObject": device["echonet_object"],
                "status": status_list,
            }]
        }
        return self._hms_request(
            "control/deviceControl",
            method="POST",
            body=body,
            extra_params={
                "boxId": device["box_id"],
                "terminalAppId": self.terminal_app_id,
            },
        )

    def power_on(self, device: dict) -> dict:
        """Turn device on."""
        return self.send_device_control(device, [
            {"statusCode": "80", "valueType": "valueSingle",
             "valueSingle": {"code": "30"}},
            {"statusCode": "F3", "valueType": "valueBinary",
             "valueBinary": {"code": "00030000000000000000000000FF00000000000000000000000000"}},
        ])

    def power_off(self, device: dict) -> dict:
        """Turn device off."""
        return self.send_device_control(device, [
            {"statusCode": "80", "valueType": "valueSingle",
             "valueSingle": {"code": "31"}},
            {"statusCode": "F3", "valueType": "valueBinary",
             "valueBinary": {"code": "000300000000000000000000000000000000000000000000000000"}},
        ])

    def set_mode(self, device: dict, mode: str) -> dict:
        """Set operation mode."""
        mode_codes = {
            "auto":    "010100001000000000000000000000000000000000000000000000",
            "night":   "010100001100000000000000000000000000000000000000000000",
            "pollen":  "010100001300000000000000000000000000000000000000000000",
            "silent":  "010100001400000000000000000000000000000000000000000000",
            "medium":  "010100001500000000000000000000000000000000000000000000",
            "high":    "010100001600000000000000000000000000000000000000000000",
            "ai_auto": "010100002000000000000000000000000000000000000000000000",
            "realize": "010100004000000000000000000000000000000000000000000000",
        }
        code = mode_codes.get(mode)
        if not code:
            raise ValueError(f"Unknown mode '{mode}'. Valid: {', '.join(mode_codes)}")
        return self.send_device_control(device, [
            {"statusCode": "F3", "valueType": "valueBinary",
             "valueBinary": {"code": code}},
        ])

    def set_humidify(self, device: dict, on: bool = True) -> dict:
        """Turn humidification on or off."""
        code = (
            "000900000000000000000000000000FF0000000000000000000000" if on
            else "000900000000000000000000000000000000000000000000000000"
        )
        return self.send_device_control(device, [
            {"statusCode": "F3", "valueType": "valueBinary",
             "valueBinary": {"code": code}},
        ])
