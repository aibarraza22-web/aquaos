"""Rule-based tank-level controls.

This is how most small and mid-size utilities actually run pumps: start below a low level, stop above a high level,
with lead/lag setpoints for multi-pump stations. It is the mandatory Phase 2 baseline, so it is kept deliberately
conventional.
"""

from __future__ import annotations

from dataclasses import dataclass

import wntr
from wntr.network import LinkStatus
from wntr.network.controls import (
    AndCondition,
    Comparison,
    Control,
    ControlAction,
    ControlPriority,
    Rule,
    ValueCondition,
)


@dataclass(frozen=True)
class TankLevelRule:
    """Open ``link`` when ``tank`` level < ``on_below_m``; close it when level > ``off_above_m``.

    Optional suction guard: never run while ``guard_tank`` (e.g. a clearwell) is below ``guard_below_m``. Pumps
    are allowed to restart once it recovers above ``guard_resume_m``. Guarded pumps use prioritized EPANET rules.
    """

    link: str
    tank: str
    on_below_m: float
    off_above_m: float
    guard_tank: str | None = None
    guard_below_m: float = 0.0
    guard_resume_m: float = 0.0

    def __post_init__(self) -> None:
        if self.on_below_m >= self.off_above_m:
            raise ValueError(f"{self.link}: on level {self.on_below_m} must be below off level {self.off_above_m}")


@dataclass(frozen=True)
class ValveLevelRule:
    """Throttle a flow-control valve to 0 above ``close_above_m`` and back to ``setting`` below ``reopen_below_m``.

    Used for the treatment plant: production stops when the clearwell is full.
    """

    valve: str
    tank: str
    setting: float
    close_above_m: float
    reopen_below_m: float


def _level_control(wn: wntr.network.WaterNetworkModel, name: str, tank: str, rel: Comparison, level: float,
                   link: str, attr: str, value: float) -> None:
    cond = ValueCondition(wn.get_node(tank), "level", rel, level)
    act = ControlAction(wn.get_link(link), attr, value)
    wn.add_control(name, Control(cond, act, name=name))


def _guarded_rules(wn: wntr.network.WaterNetworkModel, r: TankLevelRule) -> None:
    assert r.guard_tank is not None
    link, tank, guard = wn.get_link(r.link), wn.get_node(r.tank), wn.get_node(r.guard_tank)
    on_cond = AndCondition(ValueCondition(tank, "level", Comparison.lt, r.on_below_m),
                           ValueCondition(guard, "level", Comparison.gt, r.guard_resume_m))
    rules = [
        (f"{r.link}__on", on_cond, 1, ControlPriority.medium),
        (f"{r.link}__off", ValueCondition(tank, "level", Comparison.gt, r.off_above_m), 0, ControlPriority.medium),
        (f"{r.link}__guard", ValueCondition(guard, "level", Comparison.lt, r.guard_below_m), 0,
         ControlPriority.high),
    ]
    for name, cond, status, prio in rules:
        wn.add_control(name, Rule(cond, [ControlAction(link, "status", status)], priority=prio, name=name))


def apply_tank_rules(wn: wntr.network.WaterNetworkModel, rules: list[TankLevelRule]) -> None:
    for r in rules:
        if r.guard_tank is not None:
            _guarded_rules(wn, r)
            continue
        _level_control(wn, f"{r.link}__on", r.tank, Comparison.lt, r.on_below_m, r.link, "status", 1)
        _level_control(wn, f"{r.link}__off", r.tank, Comparison.gt, r.off_above_m, r.link, "status", 0)


def initialize_statuses(wn: wntr.network.WaterNetworkModel, rules: list[TankLevelRule]) -> None:
    """Start each pump in the state its rule implies at the initial tank levels.

    A pump starts only if its tank is already below the start level (and its suction guard is satisfied).
    Otherwise every pump would run at t=0 (EPANET's default "Open"), which produces an artificial demand peak.
    """
    for r in rules:
        level = wn.get_node(r.tank).init_level
        on = level < r.on_below_m
        if r.guard_tank is not None:
            on = on and wn.get_node(r.guard_tank).init_level > r.guard_resume_m
        wn.get_link(r.link).initial_status = LinkStatus.Open if on else LinkStatus.Closed


def apply_valve_rules(wn: wntr.network.WaterNetworkModel, rules: list[ValveLevelRule]) -> None:
    for r in rules:
        _level_control(wn, f"{r.valve}__close", r.tank, Comparison.gt, r.close_above_m, r.valve, "setting", 0.0)
        _level_control(wn, f"{r.valve}__reopen", r.tank, Comparison.lt, r.reopen_below_m, r.valve, "setting",
                       r.setting)


def controls_targeting(wn: wntr.network.WaterNetworkModel, link: str,
                       attribute: str | None = None) -> list[str]:
    """Names of controls/rules with an action on ``link`` (optionally only on ``attribute``).

    Matching is by action target, not by name, because simple controls read from an ``.inp`` file are renamed
    ("control 1", ...).
    """
    out = []
    for name in wn.control_name_list:
        for action in wn.get_control(name).actions():
            obj, attr = action.target()
            if getattr(obj, "name", None) == link and (attribute is None or attr == attribute):
                out.append(name)
                break
    return out


def set_valve_setting(wn: wntr.network.WaterNetworkModel, valve: str, setting: float) -> None:
    """Change an FCV's production setting everywhere: its initial setting and every control that reopens it."""
    v = wn.get_link(valve)
    v.initial_setting = setting
    for name in controls_targeting(wn, valve, "setting"):
        ctrl = wn.get_control(name)
        acts = ctrl.actions()
        if len(acts) != 1 or float(getattr(acts[0], "_value", 0.0)) <= 0.0:
            continue  # leave "close" (setting 0) controls alone
        cond, prio = ctrl.condition, ctrl.priority
        wn.remove_control(name)
        new = (Control(cond, ControlAction(v, "setting", setting), priority=prio, name=name)
               if isinstance(ctrl, Control) else
               Rule(cond, [ControlAction(v, "setting", setting)], priority=prio, name=name))
        wn.add_control(name, new)


def remove_link_controls(wn: wntr.network.WaterNetworkModel, links: list[str]) -> None:
    """Remove every control acting on the given links. An optimizer schedule replaces the rule-based controls
    this way, and a failed or disabled asset is taken out of service this way."""
    for link in links:
        for name in controls_targeting(wn, link):
            if name in wn.control_name_list:
                wn.remove_control(name)
