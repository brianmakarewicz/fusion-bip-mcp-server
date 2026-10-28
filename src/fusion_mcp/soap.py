"""Low-level BIP v2 SOAP client — direct from this host to Fusion.

SecurityService returns a session token from a login envelope; the token then
authorizes catalog and report calls.

Auth model: BIP SOAP is token-based, not Basic Auth. login(user, pass) -> token;
every catalog call carries the token. runReport is the one exception — it takes
userID/password inline and returns the report output directly.
"""

from __future__ import annotations

import base64
import re
import ssl
import urllib.error
import urllib.request

from .errors import FusionToolError

_NS = ('xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" '
       'xmlns:v2="http://xmlns.oracle.com/oxp/service/v2"')
_ACT = "http://xmlns.oracle.com/oxp/service/v2"
_CTX = ssl.create_default_context()


def _post(base_url: str, service: str, action: str, body: str) -> str:
    url = f"{base_url.rstrip('/')}/xmlpserver/services/v2/{service}"
    req = urllib.request.Request(
        url, data=body.encode("utf-8"), method="POST",
        headers={"Content-Type": "text/xml; charset=utf-8", "SOAPAction": action})
    try:
        with urllib.request.urlopen(req, timeout=120, context=_CTX) as r:
            return r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.read().decode("utf-8", "replace")
    except Exception as e:  # network/DNS/TLS
        raise FusionToolError(f"Fusion unreachable: {e}") from e


def _fault(resp: str) -> str | None:
    m = re.search(r"faultstring>(.*?)</faultstring>", resp, re.S)
    return m.group(1).strip() if m else None


def _raise_if_fault(resp: str, what: str) -> str:
    f = _fault(resp)
    if f or "soapenv:Fault" in resp or "soap:Fault" in resp:
        raise FusionToolError(f or f"{what}: SOAP fault: {resp[:300]}")
    return resp


def _b64(text: str) -> str:
    return base64.b64encode(text.encode("utf-8")).decode()


def decode_report_bytes(resp: str) -> str:
    """Decode <reportBytes> base64 from a runReport/runDataModel response."""
    m = re.search(r"<reportBytes>(.*?)</reportBytes>", resp, re.S)
    return base64.b64decode(m.group(1)).decode("utf-8", "replace") if m else resp


def login(base_url: str, user: str, pw: str) -> str:
    env = (f'<soapenv:Envelope {_NS}><soapenv:Body><v2:login>'
           f'<v2:userID>{user}</v2:userID><v2:password>{pw}</v2:password>'
           f'</v2:login></soapenv:Body></soapenv:Envelope>')
    resp = _post(base_url, "SecurityService", f"{_ACT}/SecurityService/loginRequest", env)
    m = re.search(r"loginReturn>(.*?)</", resp, re.S)
    if not m:
        raise FusionToolError(_fault(resp) or "login returned no session token")
    return m.group(1)


def create_object(base_url: str, token: str, folder: str, name: str,
                  otype: str, xml: str) -> None:
    env = (f'<soapenv:Envelope {_NS}><soapenv:Body><v2:createObjectInSession>'
           f'<v2:folderAbsolutePathURL>{folder}</v2:folderAbsolutePathURL>'
           f'<v2:objectName>{name}</v2:objectName><v2:objectType>{otype}</v2:objectType>'
           f'<v2:bipSessionToken>{token}</v2:bipSessionToken>'
           f'<v2:objectData>{_b64(xml)}</v2:objectData>'
           f'</v2:createObjectInSession></soapenv:Body></soapenv:Envelope>')
    _raise_if_fault(
        _post(base_url, "CatalogService",
              f"{_ACT}/CatalogService/createObjectInSessionRequest", env),
        f"create {otype} {folder}/{name}")


def delete_object(base_url: str, token: str, path: str) -> None:
    env = (f'<soapenv:Envelope {_NS}><soapenv:Body><v2:deleteObjectInSession>'
           f'<v2:objectAbsolutePath>{path}</v2:objectAbsolutePath>'
           f'<v2:bipSessionToken>{token}</v2:bipSessionToken>'
           f'</v2:deleteObjectInSession></soapenv:Body></soapenv:Envelope>')
    _raise_if_fault(
        _post(base_url, "CatalogService",
              f"{_ACT}/CatalogService/deleteObjectInSessionRequest", env),
        f"delete {path}")


def run_data_model_in_session(base_url: str, token: str, dm_path: str) -> str:
    env = (f'<soapenv:Envelope {_NS}><soapenv:Body><v2:runDataModelInSession>'
           f'<v2:reportRequest><v2:reportAbsolutePath>{dm_path}</v2:reportAbsolutePath>'
           f'<v2:sizeOfDataChunkDownload>-1</v2:sizeOfDataChunkDownload></v2:reportRequest>'
           f'<v2:bipSessionToken>{token}</v2:bipSessionToken>'
           f'</v2:runDataModelInSession></soapenv:Body></soapenv:Envelope>')
    return _raise_if_fault(
        _post(base_url, "ReportService",
              f"{_ACT}/ReportService/runDataModelInSessionRequest", env),
        f"run data model {dm_path}")
