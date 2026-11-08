"""Gym reservation coverage logic.

Computes whether each home game's required time window (game duration plus
before/after margins) is covered by at least one gym reservation, and
identifies surplus time in reservations that can be returned.
"""

from datetime import date, datetime, time, timedelta

from hoops_planner.core.models import Game, GymReservation, Season, SiteConfig


def _to_datetime(d: date, t: time) -> datetime:
    return datetime.combine(d, t)


def get_gym_coverage(season: Season) -> dict:
    """Compute coverage status for all home games in a season.

    Returns a dict with:
    - ``uncovered_games``: list of game dicts whose required window is not
      fully contained in any reservation.
    - ``covered_games``: count of home games that are fully covered.
    - ``total_home_games``: total number of home games.
    - ``surplus``: list of surplus windows per reservation (time blocks with
      no games that could potentially be returned).
    """
    config = SiteConfig.load()
    duration = timedelta(minutes=config.gym_game_duration_minutes)
    margin_before = timedelta(minutes=config.gym_margin_before_minutes)
    margin_after = timedelta(minutes=config.gym_margin_after_minutes)

    home_games = list(
        Game.objects.filter(
            season=season, game_type=Game.GameType.HOME
        ).order_by("date", "time")
    )
    reservations = list(season.gym_reservations.all())

    res_windows = [
        (
            _to_datetime(r.date, r.start_time),
            _to_datetime(r.date, r.end_time),
        )
        for r in reservations
    ]

    uncovered = []
    covered_count = 0

    for game in home_games:
        start = _to_datetime(game.date, game.time)
        required_start = start - margin_before
        required_end = start + duration + margin_after

        is_covered = any(
            rs <= required_start and re >= required_end
            for rs, re in res_windows
        )

        if is_covered:
            covered_count += 1
        else:
            uncovered.append(
                {
                    "game_id": game.id,
                    "date": game.date.isoformat(),
                    "time": game.time.strftime("%H:%M"),
                    "own_team": game.own_team.name,
                    "opponent": game.opponent,
                    "required_start": required_start.strftime("%H:%M"),
                    "required_end": required_end.strftime("%H:%M"),
                }
            )

    surplus = _compute_surplus(
        reservations, home_games, duration, margin_before, margin_after
    )

    return {
        "uncovered_games": uncovered,
        "covered_games": covered_count,
        "total_home_games": len(home_games),
        "surplus": surplus,
    }


def _compute_surplus(
    reservations: list[GymReservation],
    home_games: list[Game],
    duration: timedelta,
    margin_before: timedelta,
    margin_after: timedelta,
) -> list[dict]:
    """Find gaps within each reservation that contain no game windows.

    A "game window" is [start - margin_before, end + margin_after]. Surplus
    is any contiguous stretch inside a reservation that doesn't overlap any
    game window. Only gaps of at least 30 minutes are reported.
    """
    min_gap = timedelta(minutes=30)
    result = []

    for res in reservations:
        res_start = _to_datetime(res.date, res.start_time)
        res_end = _to_datetime(res.date, res.end_time)

        game_windows = []
        for game in home_games:
            if game.date != res.date:
                continue
            gs = _to_datetime(game.date, game.time)
            game_windows.append((gs - margin_before, gs + duration + margin_after))

        if not game_windows:
            gap = res_end - res_start
            if gap >= min_gap:
                result.append(
                    {
                        "reservation_id": res.id,
                        "date": res.date.isoformat(),
                        "start": res_start.strftime("%H:%M"),
                        "end": res_end.strftime("%H:%M"),
                        "minutes": int(gap.total_seconds() // 60),
                    }
                )
            continue

        game_windows.sort()
        cursor = res_start
        for ws, we in game_windows:
            if ws > cursor and (ws - cursor) >= min_gap:
                result.append(
                    {
                        "reservation_id": res.id,
                        "date": res.date.isoformat(),
                        "start": cursor.strftime("%H:%M"),
                        "end": ws.strftime("%H:%M"),
                        "minutes": int((ws - cursor).total_seconds() // 60),
                    }
                )
            cursor = max(cursor, we)
        if res_end > cursor and (res_end - cursor) >= min_gap:
            result.append(
                {
                    "reservation_id": res.id,
                    "date": res.date.isoformat(),
                    "start": cursor.strftime("%H:%M"),
                    "end": res_end.strftime("%H:%M"),
                    "minutes": int((res_end - cursor).total_seconds() // 60),
                }
            )

    return result
