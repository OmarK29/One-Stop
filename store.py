"""Google Sheets storage. One spreadsheet, six tabs. Reads are cached per session and
cleared on every write, so the app stays fast without going stale."""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

import pandas as pd

import seed

CONFIG_DIR = Path.home() / ".one-stop"
CONFIG_FILE = CONFIG_DIR / "config.json"
KEY_FILE = CONFIG_DIR / "service_account.json"
CRM_KEY_FILE = Path.home() / ".simple-crm" / "service_account.json"
CACHE_SECONDS = 90

DROPDOWNS = {  # Items column -> allowed values, applied as sheet dropdowns
    "Domain": ["Physical", "Mental", "Spiritual"],
    "Kind": ["Good", "Unideal"],
    "Period": ["Daily", "Weekly"],
    "Priority": ["Floor", "High", "Normal", "Low"],
}


class SetupError(Exception):
    """A problem the person can fix; the message says how."""


# ---------- local config (desktop) ----------

def load_local_config() -> dict:
    try:
        return json.loads(CONFIG_FILE.read_text())
    except (OSError, ValueError):
        return {}


def save_local_config(sheet_url: str, key_info: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    KEY_FILE.write_text(json.dumps(key_info, indent=2))
    try:
        KEY_FILE.chmod(0o600)
    except OSError:
        pass
    CONFIG_FILE.write_text(json.dumps({"sheet_url": sheet_url}, indent=2))


def clear_local_config() -> None:
    for f in (CONFIG_FILE, KEY_FILE):
        try:
            f.unlink()
        except OSError:
            pass


def load_local_key() -> dict | None:
    try:
        return json.loads(KEY_FILE.read_text())
    except (OSError, ValueError):
        return None


def check_key(info: dict) -> dict:
    if not isinstance(info, dict) or info.get("type") != "service_account" or "client_email" not in info:
        raise SetupError("That file isn't a Google service-account key. It should be the .json file you "
                         "downloaded from Google Cloud (it contains \"type\": \"service_account\").")
    return info


def sheet_key(url_or_key: str) -> str:
    s = (url_or_key or "").strip()
    m = re.search(r"/spreadsheets/d/([a-zA-Z0-9_-]+)", s)
    if m:
        return m.group(1)
    if re.fullmatch(r"[a-zA-Z0-9_-]{25,}", s):
        return s
    raise SetupError("Paste the full link to your Google Sheet (it contains /spreadsheets/d/…).")


def secrets_toml(sheet_url: str, key_info: dict) -> str:
    """What to paste into Streamlit Community Cloud → App settings → Secrets."""
    lines = [f'sheet_url = "{sheet_url}"', "", "[gcp_service_account]"]
    for k, v in key_info.items():
        lines.append(f"{k} = {json.dumps(v)}")
    return "\n".join(lines) + "\n"


# ---------- connecting ----------

def open_spreadsheet(key_info: dict, sheet_url: str):
    import gspread
    from gspread.exceptions import APIError, SpreadsheetNotFound

    check_key(key_info)
    key = sheet_key(sheet_url)
    try:
        client = gspread.service_account_from_dict(key_info)
        return client.open_by_key(key)
    except SpreadsheetNotFound:
        raise SetupError(f"The app can't open that sheet. In Google Sheets, click Share and add "
                         f"{key_info['client_email']} as an Editor.")
    except APIError as e:
        msg = str(e)
        code = getattr(e, "code", None) or getattr(getattr(e, "response", None), "status_code", None)
        if "has not been used" in msg or "is disabled" in msg or "SERVICE_DISABLED" in msg:
            raise SetupError("The Google Sheets API is turned off for this key's Google Cloud project. "
                             "Open console.cloud.google.com → APIs & Services → Library → Google Sheets API → Enable, "
                             "wait a minute, then try again.")
        if code in (403, 404):
            raise SetupError(f"The app can't open that sheet. Share it with {key_info['client_email']} as an Editor.")
        raise SetupError(f"Google said: {msg[:300]}")
    except Exception as e:  # network, bad key, etc.
        raise SetupError(f"Couldn't reach Google Sheets: {e}")


# ---------- the store ----------

def _col_letter(n: int) -> str:
    s = ""
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


class Store:
    def __init__(self, spreadsheet, cache: dict | None = None):
        self.ss = spreadsheet
        self.cache = cache if cache is not None else {}
        self._ws = {}

    # -- setup --
    def ensure_tabs(self) -> list[str]:
        """Create any missing tabs (with starting data) and add missing columns. Returns tabs created."""
        existing = {ws.title: ws for ws in self.ss.worksheets()}
        created = []
        for title, (header, rows) in seed.TABS.items():
            ws = existing.get(title)
            if ws is None:
                ws = self.ss.add_worksheet(title=title, rows=max(200, len(rows) + 50), cols=len(header) + 2)
                ws.update(range_name="A1", values=[header] + rows, value_input_option="RAW")
                self._style_header(ws, len(header))
                created.append(title)
            else:
                values = ws.get_all_values()
                current = values[0] if values else []
                missing = [h for h in header if h not in current]
                if not values:
                    ws.update(range_name="A1", values=[header] + rows, value_input_option="RAW")
                    self._style_header(ws, len(header))
                elif missing:
                    new_header = current + missing
                    ws.update(range_name="A1", values=[new_header], value_input_option="RAW")
            self._ws[title] = ws
        # Google gives new spreadsheets an empty "Sheet1"; remove it once our tabs exist.
        blank = existing.get("Sheet1")
        if blank is not None and created and not any(any(r) for r in blank.get_all_values()):
            try:
                self.ss.del_worksheet(blank)
            except Exception:
                pass
        if "Items" in created:
            self._add_dropdowns()
        self.cache.clear()
        return created

    def _style_header(self, ws, ncols: int) -> None:
        try:
            ws.freeze(rows=1)
            ws.format(f"A1:{_col_letter(ncols)}1", {"textFormat": {"bold": True},
                                                     "backgroundColor": {"red": 0.90, "green": 0.95, "blue": 0.94}})
        except Exception:
            pass

    def _add_dropdowns(self) -> None:
        try:
            ws = self.ws("Items")
            header = seed.ITEMS_HEADER
            reqs = []
            for col, values in DROPDOWNS.items():
                idx = header.index(col)
                reqs.append({"setDataValidation": {
                    "range": {"sheetId": ws.id, "startRowIndex": 1, "endRowIndex": 1000,
                              "startColumnIndex": idx, "endColumnIndex": idx + 1},
                    "rule": {"condition": {"type": "ONE_OF_LIST",
                                           "values": [{"userEnteredValue": v} for v in values]},
                             "strict": False, "showCustomUi": True}}})
            idx = header.index("Active")
            reqs.append({"setDataValidation": {
                "range": {"sheetId": ws.id, "startRowIndex": 1, "endRowIndex": 1000,
                          "startColumnIndex": idx, "endColumnIndex": idx + 1},
                "rule": {"condition": {"type": "BOOLEAN"}}}})
            self.ss.batch_update({"requests": reqs})
        except Exception:
            pass

    def ws(self, title: str):
        if title not in self._ws:
            self._ws[title] = self.ss.worksheet(title)
        return self._ws[title]

    # -- reading --
    def read(self, title: str, fresh: bool = False) -> pd.DataFrame:
        hit = self.cache.get(title)
        if hit and not fresh and time.time() - hit[0] < CACHE_SECONDS:
            return hit[1].copy()
        header_expected = seed.TABS[title][0]
        values = self.ws(title).get_all_values()
        header = values[0] if values else list(header_expected)
        width = len(header)
        rows = [(r + [""] * width)[:width] for r in values[1:]]
        df = pd.DataFrame(rows, columns=header)
        for h in header_expected:
            if h not in df.columns:
                df[h] = ""
        df["_row"] = range(2, len(df) + 2)
        keep = df[header_expected].apply(lambda r: any(str(v).strip() for v in r), axis=1) if len(df) else []
        df = df[keep] if len(df) else df
        if title == "Items":
            df = self._fill_item_ids(df, header)
        self.cache[title] = (time.time(), df)
        return df.copy()

    def _fill_item_ids(self, df: pd.DataFrame, header: list[str]) -> pd.DataFrame:
        """Rows typed straight into the sheet get an ID so the log can point at them."""
        ids = [str(x).strip() for x in df["ID"]]
        used = {i for i in ids if i}
        nums = [int(m.group(1)) for i in used if (m := re.fullmatch(r"I(\d+)", i))]
        nxt = max(nums, default=0) + 1
        updates, col = [], _col_letter(header.index("ID") + 1) if "ID" in header else None
        seen = set()
        for ix, (item_id, name, row) in enumerate(zip(ids, df["Item"], df["_row"])):
            if str(name).strip() and (not item_id or item_id in seen):
                while f"I{nxt:03d}" in used:
                    nxt += 1
                item_id = f"I{nxt:03d}"
                used.add(item_id)
                df.iloc[ix, df.columns.get_loc("ID")] = item_id
                if col:
                    updates.append({"range": f"{col}{row}", "values": [[item_id]]})
            seen.add(item_id)
        if updates:
            try:
                self.ws("Items").batch_update(updates, value_input_option="RAW")
            except Exception:
                pass
        return df

    def settings(self) -> dict:
        df = self.read("Settings")
        return {str(k).strip(): v for k, v in zip(df["Key"], df["Value"]) if str(k).strip()}

    # -- writing --
    def append(self, title: str, row: list) -> None:
        self.ws(title).append_row(row, value_input_option="RAW", table_range="A1")
        self.cache.pop(title, None)

    def replace(self, title: str, df: pd.DataFrame) -> None:
        header = seed.TABS[title][0]
        df = df.reindex(columns=header)
        rows = []
        for r in df.itertuples(index=False):
            vals = ["" if (v is None or (isinstance(v, float) and pd.isna(v))) else v for v in r]
            if any(str(v).strip() for v in vals):
                rows.append([_cell(v) for v in vals])
        ws = self.ws(title)
        ws.clear()
        ws.update(range_name="A1", values=[header] + rows, value_input_option="RAW")
        self._style_header(ws, len(header))
        self.cache.pop(title, None)

    def delete_row(self, title: str, sheet_row: int) -> None:
        self.ws(title).delete_rows(int(sheet_row))
        self.cache.pop(title, None)

    def refresh(self) -> None:
        self.cache.clear()


def _cell(v):
    """Keep numbers as numbers and TRUE/FALSE as booleans in the sheet."""
    if isinstance(v, bool):
        return v
    if hasattr(v, "item"):  # numpy scalars
        v = v.item()
    if isinstance(v, float) and v.is_integer():
        return int(v)
    if isinstance(v, (int, float)):
        return v
    s = str(v)
    if s.upper() in ("TRUE", "FALSE"):
        return s.upper() == "TRUE"
    if re.fullmatch(r"-?\d+", s.strip()):
        return int(s)
    return s
