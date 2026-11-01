"""Google Sheets storage. One spreadsheet, eight tabs. Reads are cached per session and
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

DROPDOWNS = {  # tab -> column -> allowed values, applied as sheet dropdowns
    "Items": {
        "Domain": ["Physical", "Mental", "Spiritual"],
        "Kind": ["Good", "Unideal", "Group"],
        "Period": ["Daily", "Weekly"],
        "Priority": ["Floor", "High", "Normal", "Low"],
        "Measure": ["Check", "Reps", "Time", "Both"],
        "Unit": ["Logs", "Reps", "Minutes"],
    },
    "Trackers": {"Show": ["Auto", "Reps", "Time", "Count"]},
}
CHECKBOXES = {"Items": ["Active", "Pinned"]}


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
        self._headers = {}  # tab -> header row, for update_row

    # -- setup --
    def ensure_tabs(self) -> list[str]:
        """Create any missing tabs (with starting data) and add missing columns. Returns tabs created."""
        existing = {ws.title: ws for ws in self.ss.worksheets()}
        upgrading = "Items" in existing and "Trackers" not in existing  # sheet made before skills existed
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
                    if ws.col_count < len(new_header):
                        ws.add_cols(len(new_header) - ws.col_count)
                    ws.update(range_name="A1", values=[new_header], value_input_option="RAW")
            self._ws[title] = ws
            if title == "Items" and upgrading:
                self._add_starter_skills()
        # Google gives new spreadsheets an empty "Sheet1"; remove it once our tabs exist.
        blank = existing.get("Sheet1")
        if blank is not None and created and not any(any(r) for r in blank.get_all_values()):
            try:
                self.ss.del_worksheet(blank)
            except Exception:
                pass
        for title in created + (["Items"] if upgrading else []):
            self._add_dropdowns(title)
        self.cache.clear()
        return created

    def _style_header(self, ws, ncols: int) -> None:
        try:
            ws.freeze(rows=1)
            ws.format(f"A1:{_col_letter(ncols)}1", {"textFormat": {"bold": True},
                                                     "backgroundColor": {"red": 0.90, "green": 0.95, "blue": 0.94}})
        except Exception:
            pass

    def _add_dropdowns(self, title: str) -> None:
        try:
            ws = self.ws(title)
            header = ws.row_values(1)  # the sheet's own order, which can differ from seed on older sheets

            def rule(col: str, condition: dict) -> dict:
                idx = header.index(col)
                return {"setDataValidation": {
                    "range": {"sheetId": ws.id, "startRowIndex": 1, "endRowIndex": 1000,
                              "startColumnIndex": idx, "endColumnIndex": idx + 1},
                    "rule": condition}}

            reqs = [rule(col, {"condition": {"type": "ONE_OF_LIST",
                                             "values": [{"userEnteredValue": v} for v in values]},
                               "strict": False, "showCustomUi": True})
                    for col, values in DROPDOWNS.get(title, {}).items() if col in header]
            reqs += [rule(col, {"condition": {"type": "BOOLEAN"}})
                     for col in CHECKBOXES.get(title, []) if col in header]
            if reqs:
                self.ss.batch_update({"requests": reqs})
        except Exception:
            pass

    def _add_starter_skills(self) -> None:
        """Once, on a sheet made before skills existed: add the starter umbrellas and skills whose names
        aren't there yet, file existing items under them where Parents is blank, and mark old rows Pinned."""
        ws = self.ws("Items")
        values = ws.get_all_values()
        header = values[0]
        rows = [(r + [""] * len(header))[:len(header)] for r in values[1:]]
        col = {h: i for i, h in enumerate(header)}
        names = {r[col["Item"]].strip().lower(): n for n, r in enumerate(rows, start=2) if r[col["Item"]].strip()}
        parents = {k.lower(): v for k, v in seed.ITEM_PARENTS.items()}
        updates = []
        for n, r in enumerate(rows, start=2):
            name = r[col["Item"]].strip().lower()
            if not name:
                continue
            if name in parents and not r[col["Parents"]].strip():
                updates.append({"range": f"{_col_letter(col['Parents'] + 1)}{n}", "values": [[parents[name]]]})
            if not r[col["Pinned"]].strip():
                updates.append({"range": f"{_col_letter(col['Pinned'] + 1)}{n}", "values": [[True]]})
        used = {r[col["ID"]].strip() for r in rows}
        nxt = max([int(m.group(1)) for i in used if (m := re.fullmatch(r"I(\d+)", i))], default=0) + 1
        new = []
        for skill in seed.SKILLS:
            if skill[0].lower() in names:
                continue
            rec = dict(zip(seed.ITEMS_HEADER, seed.skill_row(f"I{nxt:03d}", skill)))
            nxt += 1
            new.append([_cell(rec.get(h, "")) for h in header])
        if updates:
            ws.batch_update(updates, value_input_option="RAW")
        if new:
            ws.append_rows(new, value_input_option="RAW", table_range="A1")

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
        self._headers.pop(title, None)
        self._style_header(ws, len(header))
        self.cache.pop(title, None)

    def update_row(self, title: str, sheet_row: int, values: dict) -> None:
        """Set some cells of one row, by column name. Columns the sheet doesn't have are skipped."""
        ws = self.ws(title)
        if title not in self._headers:
            self._headers[title] = ws.row_values(1)
        header = self._headers[title]
        updates = [{"range": f"{_col_letter(header.index(k) + 1)}{int(sheet_row)}", "values": [[_cell(v)]]}
                   for k, v in values.items() if k in header]
        if updates:
            ws.batch_update(updates, value_input_option="RAW")
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
