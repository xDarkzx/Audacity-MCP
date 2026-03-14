import re
from shared.error_codes import AudacityMCPError, ErrorCode


_DANGEROUS_CHARS = re.compile(r"[\n\r\x00]")


def _validate_value(value: str) -> str:
    if _DANGEROUS_CHARS.search(value):
        raise AudacityMCPError(
            ErrorCode.INJECTION_DETECTED,
            f"Value contains illegal characters: {value!r}",
        )
    return value


def _quote_value(value: str) -> str:
    if " " in value or '"' in value or "=" in value:
        return f'"{value}"'
    return value


def format_command(command: str, extra_params: dict | None = None, **params: str | int | float | bool) -> str:
    _validate_value(command)
    parts = [command + ":"]
    all_params = dict(params)
    if extra_params:
        all_params.update(extra_params)
    for key, val in all_params.items():
        _validate_value(key)
        if isinstance(val, bool):
            str_val = "1" if val else "0"
        else:
            str_val = str(val)
        _validate_value(str_val)
        parts.append(f"{key}={_quote_value(str_val)}")
    return " ".join(parts) + "\n"


def parse_response(raw: str) -> dict:
    lines = raw.strip().split("\n")
    result: dict = {"raw": raw.strip(), "success": False, "message": "", "data": {}}

    for line in lines:
        line = line.strip()
        if not line:
            continue

        if line.startswith("BatchCommand finished:"):
            if "OK" in line:
                result["success"] = True
            else:
                result["message"] = line
            continue

        if "=" in line:
            key, _, value = line.partition("=")
            result["data"][key.strip()] = value.strip()
        else:
            if result["message"]:
                result["message"] += "\n" + line
            else:
                result["message"] = line

    return result
