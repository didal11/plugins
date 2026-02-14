#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""NPC 일정 플래닝 로직."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ScheduledActivity(Enum):
    WORK = "work"
    MEAL = "meal"
    SLEEP = "sleep"


@dataclass(frozen=True)
class DailyPlanner:
    """고정 일과 플래너.

    - 08시: 기상 및 식사
    - 12시: 식사
    - 18시: 식사
    - 20시~익일 07시: 취침
    - 그 외 시간: 업무
    """

    wake_and_meal_hour: int = 8
    lunch_hour: int = 12
    dinner_hour: int = 18
    sleep_hour: int = 20

    def activity_for_hour(self, hour: int) -> ScheduledActivity:
        hour = hour % 24
        if hour in (self.wake_and_meal_hour, self.lunch_hour, self.dinner_hour):
            return ScheduledActivity.MEAL
        if hour >= self.sleep_hour or hour < self.wake_and_meal_hour:
            return ScheduledActivity.SLEEP
        return ScheduledActivity.WORK
