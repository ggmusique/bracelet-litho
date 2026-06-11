"""Calcul des phases de pleine lune (algorithme de Meeus, hors-ligne).

Utilise pour proposer un calendrier de rechargement des pierres a la pleine lune.
Aucune dependance externe (uniquement la librairie standard).
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

_DEG = math.pi / 180.0


def _local_tz():
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo("Europe/Brussels")
    except Exception:
        return timezone(timedelta(hours=1))


def _jd_to_datetime_utc(jd: float) -> datetime:
    """Convertit un jour julien en datetime (UTC approx, TD ~ UTC pour une date)."""
    jd = jd + 0.5
    z = int(math.floor(jd))
    f = jd - z
    if z < 2299161:
        a = z
    else:
        alpha = int((z - 1867216.25) / 36524.25)
        a = z + 1 + alpha - int(alpha / 4)
    b = a + 1524
    c = int((b - 122.1) / 365.25)
    d = int(365.25 * c)
    e = int((b - d) / 30.6001)
    day = b - d - int(30.6001 * e) + f
    month = e - 1 if e < 14 else e - 13
    year = c - 4716 if month > 2 else c - 4715
    day_int = int(math.floor(day))
    secs = (day - day_int) * 86400.0
    return datetime(year, month, day_int) + timedelta(seconds=secs)


def _full_moon_jde(k: float) -> float:
    """Jour julien (TD) de la pleine lune d'indice k (k = entier + 0.5)."""
    T = k / 1236.85
    jde = (2451550.09766 + 29.530588861 * k
           + 0.00015437 * T * T - 0.000000150 * T ** 3 + 0.00000000073 * T ** 4)
    E = 1 - 0.002516 * T - 0.0000074 * T * T
    M = (2.5534 + 29.10535670 * k - 0.0000014 * T * T - 0.00000011 * T ** 3) * _DEG
    Mp = (201.5643 + 385.81693528 * k + 0.0107582 * T * T + 0.00001238 * T ** 3 - 0.000000058 * T ** 4) * _DEG
    F = (160.7108 + 390.67050284 * k - 0.0016118 * T * T - 0.00000227 * T ** 3 + 0.000000011 * T ** 4) * _DEG
    Om = (124.7746 - 1.56375588 * k + 0.0020672 * T * T + 0.00000215 * T ** 3) * _DEG
    s = math.sin
    corr = (
        -0.40614 * s(Mp)
        + 0.17302 * E * s(M)
        + 0.01614 * s(2 * Mp)
        + 0.01043 * s(2 * F)
        + 0.00734 * E * s(Mp - M)
        - 0.00514 * E * s(Mp + M)
        + 0.00209 * E * E * s(2 * M)
        - 0.00111 * s(Mp - 2 * F)
        - 0.00057 * s(Mp + 2 * F)
        + 0.00056 * E * s(2 * Mp + M)
        - 0.00042 * s(3 * Mp)
        + 0.00042 * E * s(M + 2 * F)
        + 0.00038 * E * s(M - 2 * F)
        - 0.00024 * E * s(2 * Mp - M)
        - 0.00017 * s(Om)
        - 0.00007 * s(Mp + 2 * M)
        + 0.00004 * s(2 * Mp - 2 * F)
        + 0.00004 * s(3 * M)
        + 0.00003 * s(Mp + M - 2 * F)
        + 0.00003 * s(2 * Mp + 2 * F)
        - 0.00003 * s(Mp + M + 2 * F)
        + 0.00003 * s(Mp - M + 2 * F)
        - 0.00002 * s(Mp - M - 2 * F)
        - 0.00002 * s(3 * Mp + M)
        + 0.00002 * s(4 * Mp)
    )
    jde += corr
    a_args = [
        (299.77, 0.107408, -0.009173, 0.000325),
        (251.88, 0.016321, 0.0, 0.000165),
        (251.83, 26.651886, 0.0, 0.000164),
        (349.42, 36.412478, 0.0, 0.000126),
        (84.66, 18.206239, 0.0, 0.000110),
        (141.74, 53.303771, 0.0, 0.000062),
        (207.14, 2.453732, 0.0, 0.000060),
        (154.84, 7.306860, 0.0, 0.000056),
        (34.52, 27.261239, 0.0, 0.000047),
        (207.19, 0.121824, 0.0, 0.000042),
        (291.34, 1.844379, 0.0, 0.000040),
        (161.72, 24.198154, 0.0, 0.000037),
        (239.56, 25.513099, 0.0, 0.000035),
        (331.55, 3.592518, 0.0, 0.000023),
    ]
    for c0, c1, c2, amp in a_args:
        ang = (c0 + c1 * k + c2 * T * T) * _DEG
        jde += amp * math.sin(ang)
    return jde


def next_full_moons(count: int = 4, from_dt: datetime | None = None) -> list[datetime]:
    """Retourne les `count` prochaines pleines lunes (datetime locaux, Europe/Brussels)."""
    tz = _local_tz()
    if from_dt is None:
        now = datetime.now(timezone.utc)
    elif from_dt.tzinfo is None:
        now = from_dt.replace(tzinfo=timezone.utc)
    else:
        now = from_dt.astimezone(timezone.utc)
    yfrac = now.year + now.timetuple().tm_yday / 366.0
    k0 = int(math.floor((yfrac - 2000.0) * 12.3685)) - 2
    out: list[datetime] = []
    k = k0
    while len(out) < count and k < k0 + 80:
        dt = _jd_to_datetime_utc(_full_moon_jde(k + 0.5)).replace(tzinfo=timezone.utc)
        if dt >= now:
            out.append(dt.astimezone(tz))
        k += 1
    return out


def full_moons_in_year(year: int) -> list[datetime]:
    start = datetime(year, 1, 1, tzinfo=timezone.utc)
    tz = _local_tz()
    res = []
    for m in next_full_moons(20, start):
        if m.year == year:
            res.append(m)
        elif m.year > year:
            break
    return res
