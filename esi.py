"""
EVE Rock – ESI data-fetching layer.

Covers:
  • Character mining ledger
  • Corporation moon-mining observers + their ledger
  • Universe type info (name, volume, group)
  • Universe name resolution (bulk)
  • Market prices (public, cached 1 h)
  • Structure name lookup
"""

import concurrent.futures
import time
from typing import Optional

import requests

ESI_BASE = "https://esi.evetech.net/latest"

# ---------------------------------------------------------------------------
# Module-level caches
# ---------------------------------------------------------------------------
_market_prices: dict[int, float] = {}
_market_prices_ts: float = 0.0
_PRICES_TTL = 3600          # seconds


def _h(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}


# ---------------------------------------------------------------------------
# Character / corporation basics
# ---------------------------------------------------------------------------

def get_character_info(access_token: str) -> dict | None:
    """Return character_id, character_name, corporation_id."""
    r = requests.get(
        "https://login.eveonline.com/oauth/verify",
        headers=_h(access_token),
        timeout=10,
    )
    if not r.ok:
        return None
    v       = r.json()
    char_id = v.get("CharacterID")
    if not char_id:
        return None
    cr = requests.get(f"{ESI_BASE}/characters/{char_id}/", headers=_h(access_token), timeout=10)
    corp_id = cr.json().get("corporation_id") if cr.ok else None
    return {"character_id": char_id, "character_name": v.get("CharacterName", ""), "corporation_id": corp_id}


def get_corporation_name(corp_id: int, access_token: str) -> str:
    r = requests.get(f"{ESI_BASE}/corporations/{corp_id}/", headers=_h(access_token), timeout=10)
    return r.json().get("name", f"Corp {corp_id}") if r.ok else f"Corp {corp_id}"


# ---------------------------------------------------------------------------
# Character mining ledger  (up to 30 days, all pages)
# ---------------------------------------------------------------------------

def get_character_mining(character_id: int, access_token: str) -> list[dict]:
    """
    Returns a list of raw ESI mining entries:
      [{date, solar_system_id, type_id, quantity}, ...]
    """
    url     = f"{ESI_BASE}/characters/{character_id}/mining/"
    entries = []
    page    = 1
    while True:
        r = requests.get(url, headers=_h(access_token), params={"page": page}, timeout=15)
        if not r.ok:
            break
        batch = r.json()
        if not batch:
            break
        entries.extend(batch)
        if page >= int(r.headers.get("X-Pages", 1)):
            break
        page += 1
    return entries


# ---------------------------------------------------------------------------
# Corporation moon-mining observers
# ---------------------------------------------------------------------------

def get_corp_mining_observers(corp_id: int, access_token: str) -> list[dict] | None:
    """
    Returns list of {observer_id, observer_type, last_updated}, or
    None if the character lacks the required corporation role (403).
    """
    url       = f"{ESI_BASE}/corporation/{corp_id}/mining/observers/"
    observers = []
    page      = 1
    while True:
        r = requests.get(url, headers=_h(access_token), params={"page": page}, timeout=15)
        if r.status_code == 403:
            return None
        if not r.ok:
            return []
        batch = r.json()
        if not batch:
            break
        observers.extend(batch)
        if page >= int(r.headers.get("X-Pages", 1)):
            break
        page += 1
    return observers


def get_observer_mining(corp_id: int, observer_id: int, access_token: str) -> list[dict]:
    """
    Returns list of {character_id, recorded_corporation_id, type_id, quantity, last_updated}.
    Quantities are cumulative from the last moon-pop event.
    """
    url     = f"{ESI_BASE}/corporation/{corp_id}/mining/observers/{observer_id}/"
    entries = []
    page    = 1
    while True:
        r = requests.get(url, headers=_h(access_token), params={"page": page}, timeout=15)
        if not r.ok:
            break
        batch = r.json()
        if not batch:
            break
        entries.extend(batch)
        if page >= int(r.headers.get("X-Pages", 1)):
            break
        page += 1
    return entries


# ---------------------------------------------------------------------------
# Structure names (player-built structures)
# ---------------------------------------------------------------------------

def get_structure_name(structure_id: int, access_token: str) -> str:
    """Resolve a player structure name (requires character to have access)."""
    r = requests.get(
        f"{ESI_BASE}/universe/structures/{structure_id}/",
        headers=_h(access_token),
        timeout=10,
    )
    if r.ok:
        return r.json().get("name", f"Structure {structure_id}")
    return f"Structure {structure_id}"


# ---------------------------------------------------------------------------
# Universe name resolution (bulk – up to 1 000 IDs per call)
# ---------------------------------------------------------------------------

def resolve_names(ids: list[int], access_token: str) -> dict[int, str]:
    """Return {id: name} for a list of universe entity IDs."""
    if not ids:
        return {}
    names: dict[int, str] = {}
    for i in range(0, len(ids), 1000):
        chunk = list(ids[i:i + 1000])
        r = requests.post(
            f"{ESI_BASE}/universe/names/",
            json=chunk,
            headers=_h(access_token),
            timeout=15,
        )
        if r.ok:
            for item in r.json():
                names[item["id"]] = item["name"]
    return names


# ---------------------------------------------------------------------------
# Type info (name, volume, group)
# ---------------------------------------------------------------------------

def get_type_info(type_id: int, access_token: str) -> dict | None:
    """
    Return {name, volume, group_id} for a single type.
    volume is m³ per unit in a cargo hold.
    """
    r = requests.get(f"{ESI_BASE}/universe/types/{type_id}/", headers=_h(access_token), timeout=10)
    if not r.ok:
        return None
    d = r.json()
    return {
        "name":     d.get("name", f"Type {type_id}"),
        "volume":   d.get("volume") or d.get("packaged_volume") or 0.0,
        "group_id": d.get("group_id"),
    }


def get_types_batch(type_ids: list[int], access_token: str) -> dict[int, dict]:
    """Fetch type info for multiple IDs concurrently (up to 20 parallel requests)."""
    if not type_ids:
        return {}
    results: dict[int, dict] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(get_type_info, tid, access_token): tid for tid in type_ids}
        for future in concurrent.futures.as_completed(futures):
            tid = futures[future]
            try:
                info = future.result()
                if info:
                    results[tid] = info
            except Exception:
                pass
    return results


def get_group_name(group_id: int, access_token: str = "") -> str:
    headers = _h(access_token) if access_token else {"Accept": "application/json"}
    r = requests.get(f"{ESI_BASE}/universe/groups/{group_id}/", headers=headers, timeout=10)
    return r.json().get("name", f"Group {group_id}") if r.ok else f"Group {group_id}"


def get_groups_batch(group_ids: list[int], access_token: str = "") -> dict[int, str]:
    """Fetch group names for multiple group IDs concurrently (public endpoint, no auth required)."""
    if not group_ids:
        return {}
    results: dict[int, str] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(get_group_name, gid, access_token): gid for gid in group_ids}
        for future in concurrent.futures.as_completed(futures):
            gid = futures[future]
            try:
                results[gid] = future.result()
            except Exception:
                results[gid] = f"Group {gid}"
    return results


# ---------------------------------------------------------------------------
# Market prices (public endpoint, no auth required; cached in-process)
# ---------------------------------------------------------------------------

def get_market_prices() -> dict[int, float]:
    """
    Return {type_id: average_price}.  Falls back to adjusted_price if
    average is absent.  Cached for PRICES_TTL seconds.
    """
    global _market_prices, _market_prices_ts
    if time.time() - _market_prices_ts < _PRICES_TTL and _market_prices:
        return _market_prices
    r = requests.get(
        f"{ESI_BASE}/markets/prices/",
        headers={"Accept": "application/json"},
        timeout=20,
    )
    if r.ok:
        prices: dict[int, float] = {}
        for item in r.json():
            price = item.get("average_price") or item.get("adjusted_price") or 0.0
            prices[item["type_id"]] = price
        _market_prices    = prices
        _market_prices_ts = time.time()
    return _market_prices
