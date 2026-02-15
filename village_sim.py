#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Fantasy village simulation (pygame).

✅ 포함 기능(요청 반영)
- 400x300 맵, 타일 크기 축소 + 카메라
- 마을(구역) + 건물(4x3)
- 마을 밖(Outside) 영역 존재
- 휠 줌(마우스 기준 줌), WASD/화살표 이동
- 미니맵 + 미니맵 클릭 시 카메라 이동
- 건물 모달(인원/재고/작업중 탭)
- NPC 모달(트레잇/스테이터스/인벤토리 탭)  ✅ 이번 요청
- NPC/건물 선택 후 I키로 모달 열기

✅ 분리(10개 제한 준수)
- config.py: 상수
- model.py : enums + dataclasses
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import pygame
from combat import resolve_combat_round

from config import (
    BASE_TILE_SIZE,
    GRID_W,
    GRID_H,
    SCREEN_W,
    SCREEN_H,
    FPS,
    SIM_TICK_MS,
    SIM_TICK_MINUTES,
    CAMERA_SPEED,
    ZOOM_MIN,
    ZOOM_MAX,
    ZOOM_STEP,
    MINIMAP_W,
    MINIMAP_H,
    MINIMAP_PAD,
    MODAL_W,
    MODAL_H,
)

from economy import EconomySystem
from planning import DailyPlanner, ScheduledActivity
from behavior_decision import BehaviorDecisionEngine
from action_execution import ActionExecutor
from entity_manager import EntityManager
from editable_data import (
    ensure_data_files,
    load_entities,
    load_all_data,
    load_item_defs,
    load_job_defs,
    load_action_defs,
    load_races,
)

from model import (
    TileRect,
    Building,
    BoardTab,
    BuildingState,
    BuildingTab,
    ItemDef,
    JobType,
    ModalKind,
    NPCTab,
    NPC,
    RegionType,
    SelectionType,
    Status,
    Traits,
    Zone,
    ZoneType,
)


# ============================================================
# Utility
# ============================================================
def clamp(v: int, lo: int = 0, hi: int = 100) -> int:
    return max(lo, min(hi, v))


def world_w_px() -> int:
    return GRID_W * BASE_TILE_SIZE


def world_h_px() -> int:
    return GRID_H * BASE_TILE_SIZE


def tile_to_world_px_center(tx: int, ty: int) -> Tuple[int, int]:
    return tx * BASE_TILE_SIZE + BASE_TILE_SIZE // 2, ty * BASE_TILE_SIZE + BASE_TILE_SIZE // 2


def world_px_to_tile(wx: float, wy: float) -> Tuple[int, int]:
    return int(wx // BASE_TILE_SIZE), int(wy // BASE_TILE_SIZE)


def manhattan_path(start: Tuple[int, int], goal: Tuple[int, int]) -> List[Tuple[int, int]]:
    sx, sy = start
    gx, gy = goal
    path: List[Tuple[int, int]] = []
    x, y = sx, sy

    if gx != x:
        step_x = 1 if gx > x else -1
        while x != gx:
            x += step_x
            path.append((x, y))

    if gy != y:
        step_y = 1 if gy > y else -1
        while y != gy:
            y += step_y
            path.append((x, y))

    return path


def rect_union(rects: List[TileRect]) -> TileRect:
    if not rects:
        return TileRect(0, 0, 0, 0)
    r = rects[0].copy()
    for rr in rects[1:]:
        r.union_ip(rr)
    return r

ADVENTURER_GATHER_ACTIONS: Set[str] = {"약초채집", "벌목", "채광", "동물사냥", "몬스터사냥"}




# ============================================================
# Time
# ============================================================
class TimeSystem:
    MINUTES_PER_DAY = 24 * 60
    DAYS_PER_MONTH = 30
    MONTHS_PER_YEAR = 12

    def __init__(self):
        self.total_minutes = 0

    def advance(self, minutes: int = SIM_TICK_MINUTES) -> None:
        self.total_minutes += int(minutes)

    @property
    def hour(self) -> int:
        return (self.total_minutes // 60) % 24

    @property
    def minute(self) -> int:
        return self.total_minutes % 60

    @property
    def _total_days(self) -> int:
        return self.total_minutes // self.MINUTES_PER_DAY

    @property
    def day(self) -> int:
        return (self._total_days % self.DAYS_PER_MONTH) + 1

    @property
    def month(self) -> int:
        total_months = self._total_days // self.DAYS_PER_MONTH
        return (total_months % self.MONTHS_PER_YEAR) + 1

    @property
    def year(self) -> int:
        total_months = self._total_days // self.DAYS_PER_MONTH
        return total_months // self.MONTHS_PER_YEAR

    def __str__(self) -> str:
        return f"{self.year}년 {self.month}월 {self.day}일 {self.hour:02d}:{self.minute:02d}"


# ============================================================
# Camera
# ============================================================
class Camera:
    def __init__(self):
        self.x = 0.0
        self.y = 0.0
        self.zoom = 1.0

    def clamp_to_world(self) -> None:
        view_w = SCREEN_W / self.zoom
        view_h = SCREEN_H / self.zoom
        max_x = max(0.0, world_w_px() - view_w)
        max_y = max(0.0, world_h_px() - view_h)
        self.x = max(0.0, min(max_x, self.x))
        self.y = max(0.0, min(max_y, self.y))

    def world_to_screen(self, wx: float, wy: float) -> Tuple[int, int]:
        return int((wx - self.x) * self.zoom), int((wy - self.y) * self.zoom)

    def screen_to_world(self, sx: int, sy: int) -> Tuple[float, float]:
        return float(sx / self.zoom + self.x), float(sy / self.zoom + self.y)

    def center_on_world(self, wx: float, wy: float) -> None:
        view_w = SCREEN_W / self.zoom
        view_h = SCREEN_H / self.zoom
        self.x = wx - view_w / 2
        self.y = wy - view_h / 2
        self.clamp_to_world()

    def zoom_at(self, sx: int, sy: int, new_zoom: float) -> None:
        new_zoom = max(ZOOM_MIN, min(ZOOM_MAX, new_zoom))
        if abs(new_zoom - self.zoom) < 1e-6:
            return
        wx_before, wy_before = self.screen_to_world(sx, sy)
        self.zoom = new_zoom
        wx_after, wy_after = self.screen_to_world(sx, sy)
        self.x += (wx_before - wx_after)
        self.y += (wy_before - wy_after)
        self.clamp_to_world()


# ============================================================
# Fonts
# ============================================================
def make_font(size: int) -> pygame.font.Font:
    candidates = ["malgungothic", "NanumGothic", "AppleGothic", "NotoSansCJKkr", "Noto Sans CJK KR"]
    for name in candidates:
        f = pygame.font.SysFont(name, size)
        if f is not None:
            return f
    return pygame.font.SysFont(None, size)


# ============================================================
# UI helpers
# ============================================================
def modal_rect() -> pygame.Rect:
    x = (SCREEN_W - MODAL_W) // 2
    y = (SCREEN_H - MODAL_H) // 2
    return pygame.Rect(x, y, MODAL_W, MODAL_H)


def draw_text_lines(surface: pygame.Surface, font: pygame.font.Font, x: int, y: int, lines: List[str], color=(230, 230, 230), line_h: int = 20):
    yy = y
    for ln in lines:
        surface.blit(font.render(ln, True, color), (x, yy))
        yy += line_h


def draw_modal_frame(screen: pygame.Surface, title: str, font: pygame.font.Font) -> pygame.Rect:
    rect = modal_rect()
    dim = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
    dim.fill((0, 0, 0, 130))
    screen.blit(dim, (0, 0))
    pygame.draw.rect(screen, (20, 20, 24), rect)
    pygame.draw.rect(screen, (0, 0, 0), rect, 2)
    screen.blit(font.render(title, True, (240, 240, 240)), (rect.x + 16, rect.y + 12))
    return rect


def draw_tabs(screen: pygame.Surface, rect: pygame.Rect, tabs: List[Tuple[str, object]], active: object, small: pygame.font.Font) -> Dict[object, pygame.Rect]:
    tab_rects: Dict[object, pygame.Rect] = {}
    tab_y = rect.y + 48
    tab_x = rect.x + 16
    tab_w = 190
    tab_h = 34
    gap = 10
    for label, enumv in tabs:
        r = pygame.Rect(tab_x, tab_y, tab_w, tab_h)
        tab_rects[enumv] = r
        tab_x += tab_w + gap
    for enumv, r in tab_rects.items():
        active_now = (enumv == active)
        pygame.draw.rect(screen, (55, 55, 65) if active_now else (35, 35, 42), r)
        pygame.draw.rect(screen, (0, 0, 0), r, 2)
        screen.blit(small.render(str(getattr(enumv, "value", "")) or "", True, (240, 240, 240)), (r.x + 12, r.y + 8))
    return tab_rects


# ============================================================
# Game
# ============================================================
class VillageGame:
    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)
        self.time = TimeSystem()
        self.camera = Camera()
        ensure_data_files()
        data = load_all_data()
        self.sim_settings = data["sim"] if isinstance(data.get("sim"), dict) else {}
        self.combat_settings: Dict[str, object] = {"hostile_race": "적대"}
        combat_path = Path(__file__).parent / "data" / "combat.json"
        if combat_path.exists():
            try:
                raw = json.loads(combat_path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    self.combat_settings.update(raw)
            except Exception:
                pass
        self.last_economy_snapshot = None

        # Logs
        self.logs: List[str] = []
        self.planner = DailyPlanner()

        # Selection / modal
        self.selection_type: SelectionType = SelectionType.NONE
        self.selected_npc: Optional[int] = None
        self.selected_building: Optional[str] = None
        self.modal_open: bool = False
        self.modal_kind: ModalKind = ModalKind.NONE
        self.building_tab: BuildingTab = BuildingTab.PEOPLE
        self.npc_tab: NPCTab = NPCTab.TRAITS
        self.board_tab: BoardTab = BoardTab.ENTITIES

        # Data (single-source loader)
        loaded_items = data.get("items", []) if isinstance(data.get("items"), list) else []
        if not loaded_items:
            loaded_items = load_item_defs()
        self.items: Dict[str, ItemDef] = {it["key"]: ItemDef(it["key"], it["display"]) for it in loaded_items if isinstance(it, dict) and "key" in it and "display" in it}
        self.item_display_to_key: Dict[str, str] = {
            v.display: k for k, v in self.items.items()
        }

        loaded_races = data.get("races", []) if isinstance(data.get("races"), list) else []
        if not loaded_races:
            loaded_races = load_races()
        self.races = loaded_races
        self.race_map: Dict[str, Dict[str, object]] = {str(r.get("name", "")): r for r in self.races if isinstance(r, dict)}

        loaded_entities = data.get("entities", []) if isinstance(data.get("entities"), list) else []
        if not loaded_entities:
            loaded_entities = load_entities()
        self.entities: List[Dict[str, object]] = [e for e in loaded_entities if isinstance(e, dict)]

        if not isinstance(data.get("npcs"), list):
            raise ValueError("load_all_data()['npcs'] must be a list")
        if not isinstance(data.get("monsters"), list):
            raise ValueError("load_all_data()['monsters'] must be a list")

        self.npc_templates: List[Dict[str, object]] = [n for n in data["npcs"] if isinstance(n, dict)]
        self.monster_templates: List[Dict[str, object]] = [m for m in data["monsters"] if isinstance(m, dict)]
        if not self.npc_templates:
            raise ValueError("load_all_data()['npcs'] must contain at least one npc template")
        if not self.monster_templates:
            raise ValueError("load_all_data()['monsters'] must contain at least one monster template")

        jobs_for_economy = data.get("jobs", []) if isinstance(data.get("jobs"), list) else []
        if not jobs_for_economy:
            jobs_for_economy = load_job_defs()
        self.economy = EconomySystem(jobs_for_economy, self.sim_settings)

        action_rows = data.get("actions", []) if isinstance(data.get("actions"), list) else []
        if not action_rows:
            action_rows = load_action_defs()
        self.action_defs: Dict[str, Dict[str, object]] = {
            str(row.get("name", "")).strip(): row for row in action_rows if isinstance(row, dict) and str(row.get("name", "")).strip()
        }
        self.job_work_actions: Dict[str, List[str]] = {
            str(row.get("job", "")).strip(): [str(x).strip() for x in row.get("work_actions", []) if str(x).strip()]
            for row in jobs_for_economy if isinstance(row, dict)
        }
        # jobs.json(work_actions) 와 actions.json(action_defs)를 선-조인한 실제 사용 가능 액션 테이블
        self.job_action_defs: Dict[str, List[Dict[str, object]]] = {
            job_name: [self.action_defs[action_name] for action_name in action_names if action_name in self.action_defs]
            for job_name, action_names in self.job_work_actions.items()
        }
        self.behavior = BehaviorDecisionEngine(self.planner, self.rng, self.job_work_actions, self.action_defs)

        # Table-driven building names
        self.market_building_names = ["식당", "잡화점", "사치상점"]
        self.job_building_names = ["농장", "목장", "낚시터"]
        self.interaction_building_names = ["대장간", "약국", "모험가 길드"]
        self.res_building_names = ["주택A", "주택B", "주택C", "주택D", "주택E", "주택F"]

        # Zones / buildings
        self.zones: List[Zone] = self._create_zones_table_layout()
        self.buildings: List[Building] = [b for z in self.zones for b in z.buildings]
        self.building_by_name: Dict[str, Building] = {b.name: b for b in self.buildings}

        # Village outline for outside logic
        self.village_rect_tiles = rect_union([z.rect_tiles for z in self.zones]).inflate(4, 4)
        self.village_rect_tiles.clamp_ip(TileRect(0, 0, GRID_W, GRID_H))

        # Building state
        self.bstate: Dict[str, BuildingState] = {}
        self._init_building_states()
        self.entity_manager = EntityManager(self.entities, self.rng)
        self.guild_board_state: Dict[str, object] = {"known_entities": {}, "quests": []}
        self.guild_board_tile: Optional[Tuple[int, int]] = self.entity_manager.resolve_target_tile("guild_board")
        configured_ticks = int(self.sim_settings.get("explore_duration_ticks", 6))
        self.explore_duration_ticks: int = configured_ticks if configured_ticks in (6, 12, 18) else 6
        self._init_guild_board_state()
        self.action_executor = ActionExecutor(
            self.rng,
            self.sim_settings,
            self.items,
            self.item_display_to_key,
            self.action_defs,
            self.bstate,
            self.building_by_name,
            self.entities,
            self.entity_manager,
            self.behavior,
            self._status_clamp,
        )

        # NPC
        self.npcs: List[NPC] = []
        self._create_npcs()

        # Initial plans
        for npc in self.npcs:
            self._plan_next_target(npc)

        # Camera to village center
        cx = self.village_rect_tiles.centerx * BASE_TILE_SIZE
        cy = self.village_rect_tiles.centery * BASE_TILE_SIZE
        self.camera.center_on_world(cx, cy)

    # -----------------------------
    # Worldgen
    # -----------------------------
    def _create_buildings_grid(self, zone_type: ZoneType, zone_rect: TileRect, names: List[str], cols: int, rows: int, pad: int = 1) -> List[Building]:
        b_w, b_h = 4, 3
        out: List[Building] = []
        start_x = zone_rect.x + 1
        start_y = zone_rect.y + 1
        cell_w = b_w + pad
        cell_h = b_h + pad
        idx = 0
        for r in range(rows):
            for c in range(cols):
                if idx >= len(names):
                    break
                bx = start_x + c * cell_w
                by = start_y + r * cell_h
                if bx + b_w > zone_rect.x + zone_rect.w - 1:
                    continue
                if by + b_h > zone_rect.y + zone_rect.h - 1:
                    continue
                out.append(Building(zone_type, names[idx], TileRect(bx, by, b_w, b_h)))
                idx += 1
        return out

    def _create_zones_table_layout(self) -> List[Zone]:
        gap = 3
        zone_w, zone_h = 18, 10
        inter_w, inter_h = 18, 8
        job_w, job_h = 18, 6

        block_w = zone_w * 2 + gap
        block_h = zone_h + gap + inter_h + gap + job_h

        start_x = max(1, min(GRID_W - block_w - 1, (GRID_W // 2) - (block_w // 2)))
        start_y = max(1, min(GRID_H - block_h - 1, (GRID_H // 2) - (block_h // 2)))

        market_rect = TileRect(start_x, start_y, zone_w, zone_h)
        res_rect = TileRect(start_x + zone_w + gap, start_y, zone_w, zone_h)
        inter_rect = TileRect(start_x, start_y + zone_h + gap, inter_w, inter_h)
        job_rect = TileRect(start_x, inter_rect.y + inter_h + gap, job_w, job_h)

        zones: List[Zone] = []
        zones.append(Zone(ZoneType.MARKET, market_rect, self._create_buildings_grid(ZoneType.MARKET, market_rect, self.market_building_names, cols=3, rows=1, pad=1)))
        zones.append(Zone(ZoneType.RESIDENTIAL, res_rect, self._create_buildings_grid(ZoneType.RESIDENTIAL, res_rect, self.res_building_names, cols=3, rows=2, pad=1)))
        zones.append(Zone(ZoneType.INTERACTION, inter_rect, self._create_buildings_grid(ZoneType.INTERACTION, inter_rect, self.interaction_building_names, cols=3, rows=1, pad=1)))
        zones.append(Zone(ZoneType.JOB, job_rect, self._create_buildings_grid(ZoneType.JOB, job_rect, self.job_building_names, cols=3, rows=1, pad=1)))
        return zones

    def is_outside_tile(self, tx: int, ty: int) -> bool:
        return not self.village_rect_tiles.collidepoint(tx, ty)

    def random_outside_tile(self) -> Tuple[int, int]:
        for _ in range(2000):
            tx = self.rng.randint(0, GRID_W - 1)
            ty = self.rng.randint(0, GRID_H - 1)
            if self.is_outside_tile(tx, ty):
                return tx, ty
        return 2, 2

    # -----------------------------
    # Building state
    # -----------------------------
    def _init_building_states(self) -> None:
        for b in self.buildings:
            inv: Dict[str, int] = {}
            task = "대기"
            prog = 0
            if b.zone == ZoneType.MARKET:
                if b.name == "식당":
                    inv = {"bread": 16, "meat": 8, "fish": 8, "wheat": 10}
                    task = "조리/서빙"
                elif b.name == "잡화점":
                    inv = {"bread": 20, "wheat": 30, "wood": 16, "ore": 12, "fish": 16, "meat": 10, "herb": 10, "potion": 6, "ingot": 4}
                    task = "매매"
                elif b.name == "사치상점":
                    inv = {"potion": 10, "meat": 6, "artifact": 2, "leather": 4}
                    task = "매매"
            elif b.zone == ZoneType.JOB:
                if b.name == "농장":
                    inv = {"wheat": 20, "bread": 8}
                    task = "농사"
                elif b.name == "목장":
                    inv = {"meat": 8, "hide": 6}
                    task = "사육"
                elif b.name == "낚시터":
                    inv = {"fish": 10}
                    task = "낚시"
            elif b.zone == ZoneType.INTERACTION:
                if b.name == "대장간":
                    inv = {"ore": 10, "wood": 10, "ingot": 4, "lumber": 4}
                    task = "제작/판매"
                elif b.name == "약국":
                    inv = {"potion": 10, "herb": 12}
                    task = "제약/판매"
                elif b.name == "모험가 길드":
                    inv = {}
                    task = "납품/정산"
            else:
                inv = {}
                task = "거주"
                prog = 0
            self.bstate[b.name] = BuildingState(inventory=inv, task=task, task_progress=prog, last_event="")

    # -----------------------------
    # NPC creation
    # -----------------------------
    def _random_traits(self, name: str) -> Traits:
        races = [str(r.get("name")) for r in self.races if not bool(r.get("is_hostile", False))]
        genders = ["남", "여", "기타"]
        jobs = [JobType.ADVENTURER, JobType.FARMER, JobType.FISHER, JobType.BLACKSMITH, JobType.PHARMACIST]
        race = self.rng.choice(races or ["인간"])
        gender = self.rng.choice(genders)
        age = self.rng.randint(18, 58)
        bonus = self.race_map.get(race, {})
        return Traits(
            name=name,
            race=race,
            gender=gender,
            age=age,
            job=self.rng.choice(jobs),
            race_str_bonus=int(bonus.get("str_bonus", 0)),
            race_agi_bonus=int(bonus.get("agi_bonus", 0)),
            race_hp_bonus=int(bonus.get("hp_bonus", 0)),
            race_speed_bonus=float(bonus.get("speed_bonus", 0.0)),
            is_hostile=bool(bonus.get("is_hostile", False)),
        )

    def _job_from_text(self, job_text: str) -> JobType:
        mapping = {
            JobType.ADVENTURER.value: JobType.ADVENTURER,
            JobType.FARMER.value: JobType.FARMER,
            JobType.FISHER.value: JobType.FISHER,
            JobType.BLACKSMITH.value: JobType.BLACKSMITH,
            JobType.PHARMACIST.value: JobType.PHARMACIST,
        }
        return mapping.get(job_text, JobType.FARMER)

    def _create_npcs(self) -> None:
        templates = list(self.npc_templates) + list(self.monster_templates)
        res_buildings = [b for b in self.buildings if b.zone == ZoneType.RESIDENTIAL]
        for t in templates:
            nm = str(t.get("name", "이름없음"))
            race = str(t.get("race", "인간"))
            race_cfg = self.race_map.get(race, {})
            hostile = bool(race_cfg.get("is_hostile", False))
            if hostile:
                tx, ty = self.random_outside_tile()
                home = self.rng.choice(res_buildings)
            else:
                home = self.rng.choice(res_buildings)
                tx, ty = home.random_tile_inside(self.rng)
            wx, wy = tile_to_world_px_center(tx, ty)
            max_hp = max(1, int(t.get("max_hp", self.rng.randint(85, 125))) + int(race_cfg.get("hp_bonus", 0)))
            hp = max(0, min(max_hp, int(t.get("hp", max_hp))))
            tr = Traits(
                name=nm,
                race=race,
                gender=str(t.get("gender", "기타")),
                age=int(t.get("age", self.rng.randint(18, 58))),
                job=self._job_from_text(str(t.get("job", JobType.FARMER.value))),
                race_str_bonus=int(race_cfg.get("str_bonus", 0)),
                race_agi_bonus=int(race_cfg.get("agi_bonus", 0)),
                race_hp_bonus=int(race_cfg.get("hp_bonus", 0)),
                race_speed_bonus=float(race_cfg.get("speed_bonus", 0.0)),
                is_hostile=hostile,
            )
            st = Status(
                money=int(t.get("money", self.rng.randint(60, 180))),
                happiness=self.rng.randint(45, 75),
                hunger=self.rng.randint(15, 55),
                fatigue=self.rng.randint(15, 55),
                max_hp=max_hp,
                hp=hp,
                strength=max(1, int(t.get("strength", self.rng.randint(8, 16))) + int(race_cfg.get("str_bonus", 0))),
                agility=max(1, int(t.get("agility", self.rng.randint(8, 16))) + int(race_cfg.get("agi_bonus", 0))),
            )
            npc = NPC(
                traits=tr,
                status=st,
                x=float(wx),
                y=float(wy),
                path=[],
                home_building=home,
                location_building=home if not hostile else None,
                inventory={},
                target_outside_tile=None,
                target_entity_tile=None,
            )
            if self.rng.random() < 0.6 and "bread" in self.items:
                npc.inventory["bread"] = self.rng.randint(0, 2)
            if self.rng.random() < 0.45 and "wheat" in self.items:
                npc.inventory["wheat"] = self.rng.randint(0, 3)
            if self.rng.random() < 0.30 and "wood" in self.items:
                npc.inventory["wood"] = 1
            if self.rng.random() < 0.25 and "ore" in self.items:
                npc.inventory["ore"] = 1
            if self.rng.random() < 0.20 and "herb" in self.items:
                npc.inventory["herb"] = 1
            if (not hostile) and "tool" in self.items and npc.inventory.get("tool", 0) <= 0:
                npc.inventory["tool"] = 1
            self.npcs.append(npc)

    # -----------------------------
    # Helper
    # -----------------------------
    def find_building_by_tile(self, tx: int, ty: int) -> Optional[Building]:
        for b in self.buildings:
            if b.contains_tile(tx, ty):
                return b
        return None

    def get_building_world_rect(self, b: Building) -> pygame.Rect:
        bx, by, bw, bh = b.rect_tiles
        return pygame.Rect(bx * BASE_TILE_SIZE, by * BASE_TILE_SIZE, bw * BASE_TILE_SIZE, bh * BASE_TILE_SIZE)

    # -----------------------------
    # Selection
    # -----------------------------
    def pick_npc_at_screen(self, sx: int, sy: int) -> Optional[int]:
        wx, wy = self.camera.screen_to_world(sx, sy)
        r = 12.0
        for i, npc in enumerate(self.npcs):
            dx = wx - npc.x
            dy = wy - npc.y
            if dx * dx + dy * dy <= r * r:
                return i
        return None

    def pick_building_at_screen(self, sx: int, sy: int) -> Optional[str]:
        wx, wy = self.camera.screen_to_world(sx, sy)
        for b in self.buildings:
            if self.get_building_world_rect(b).collidepoint(wx, wy):
                return b.name
        return None

    def pick_guild_board_at_screen(self, sx: int, sy: int) -> bool:
        tile = self.guild_board_tile or self.entity_manager.resolve_target_tile("guild_board")
        if tile is None:
            return False
        wx, wy = self.camera.screen_to_world(sx, sy)
        gx, gy = tile_to_world_px_center(tile[0], tile[1])
        dx = wx - gx
        dy = wy - gy
        return (dx * dx + dy * dy) <= (BASE_TILE_SIZE * BASE_TILE_SIZE)

    def set_explore_duration_ticks(self, ticks: int) -> None:
        ticks = int(ticks)
        if ticks in (6, 12, 18):
            self.explore_duration_ticks = ticks

    def _init_guild_board_state(self) -> None:
        known = self.guild_board_state.setdefault("known_entities", {})
        known_cells = self.guild_board_state.setdefault("known_cells", {})
        if not isinstance(known, dict):
            known = {}
            self.guild_board_state["known_entities"] = known
        if not isinstance(known_cells, dict):
            known_cells = {}
            self.guild_board_state["known_cells"] = known_cells

        # 시작 시 길드 게시판에 마을 범위 셀 정보를 기본 등록한다.
        vr = self.village_rect_tiles
        for tx in range(vr.x, vr.x + vr.w):
            for ty in range(vr.y, vr.y + vr.h):
                cell_key = self._tile_key(tx, ty)
                if cell_key in known_cells:
                    continue
                known_cells[cell_key] = {
                    "entities": [],
                    "monsters": [],
                    "updated_at": self.time.total_minutes,
                }

        for ent in self.entities:
            if bool(ent.get("is_workbench", False)):
                continue
            if bool(ent.get("is_discovered", False)):
                key = str(ent.get("key", "")).strip()
                if key:
                    known[key] = {
                        "x": int(ent.get("x", 0)),
                        "y": int(ent.get("y", 0)),
                        "qty": int(ent.get("current_quantity", 0)),
                        "name": str(ent.get("name", key)),
                    }
                    self.guild_board_state["known_cells"][self._tile_key(int(ent.get("x", 0)), int(ent.get("y", 0)))] = {
                        "entities": [{"key": key, "name": str(ent.get("name", key)), "qty": int(ent.get("current_quantity", 0))}],
                        "monsters": [],
                        "updated_at": self.time.total_minutes,
                    }

    def _tile_key(self, tx: int, ty: int) -> str:
        return f"{int(tx)},{int(ty)}"

    def _tile_from_key(self, key: str) -> Optional[Tuple[int, int]]:
        parts = str(key).split(",")
        if len(parts) != 2:
            return None
        try:
            return int(parts[0]), int(parts[1])
        except ValueError:
            return None

    def _snapshot_known_cell(self, tx: int, ty: int) -> Dict[str, object]:
        entities_info: List[Dict[str, object]] = []
        for ent in self.entities:
            if bool(ent.get("is_workbench", False)):
                continue
            if int(ent.get("current_quantity", 0)) <= 0:
                continue
            ex = int(ent.get("x", 0))
            ey = int(ent.get("y", 0))
            if (ex, ey) != (tx, ty):
                continue
            ent["is_discovered"] = True
            entities_info.append({
                "key": str(ent.get("key", "")),
                "name": str(ent.get("name", ent.get("key", "미상"))),
                "qty": int(ent.get("current_quantity", 0)),
            })

        monsters_info: List[Dict[str, object]] = []
        for npc in self.npcs:
            if npc.status.hp <= 0 or not self._is_hostile(npc):
                continue
            ntx, nty = world_px_to_tile(npc.x, npc.y)
            if (ntx, nty) != (tx, ty):
                continue
            monsters_info.append({"name": npc.traits.name, "hp": npc.status.hp})

        return {
            "entities": entities_info,
            "monsters": monsters_info,
            "updated_at": self.time.total_minutes,
        }

    def _record_known_area_to_buffer(self, npc: NPC, center_tile: Tuple[int, int]) -> None:
        cx, cy = center_tile
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                tx = max(0, min(GRID_W - 1, cx + dx))
                ty = max(0, min(GRID_H - 1, cy + dy))
                npc.explore_known_buffer[self._tile_key(tx, ty)] = self._snapshot_known_cell(tx, ty)

    def _flush_explore_buffer_to_board(self, npc: NPC) -> int:
        known_cells = self.guild_board_state.setdefault("known_cells", {})
        if not isinstance(known_cells, dict):
            known_cells = {}
            self.guild_board_state["known_cells"] = known_cells
        known_entities = self.guild_board_state.setdefault("known_entities", {})
        if not isinstance(known_entities, dict):
            known_entities = {}
            self.guild_board_state["known_entities"] = known_entities

        merged = 0
        for key, info in npc.explore_known_buffer.items():
            if not isinstance(info, dict):
                continue
            known_cells[key] = info
            merged += 1
            tile = self._tile_from_key(key)
            if tile is None:
                continue
            tx, ty = tile
            for entity in info.get("entities", []):
                if not isinstance(entity, dict):
                    continue
                ekey = str(entity.get("key", "")).strip()
                if not ekey:
                    continue
                known_entities[ekey] = {
                    "x": tx,
                    "y": ty,
                    "qty": int(entity.get("qty", 0)),
                    "name": str(entity.get("name", ekey)),
                    "updated_at": int(info.get("updated_at", self.time.total_minutes)),
                }

        npc.explore_known_buffer.clear()
        return merged

    def _sync_guild_board_quantities(self) -> None:
        known = self.guild_board_state.get("known_entities", {})
        if not isinstance(known, dict):
            return
        remove_keys: List[str] = []
        for key in list(known.keys()):
            ent = self.entity_manager.find_by_key(key)
            if ent is None or int(ent.get("current_quantity", 0)) <= 0:
                remove_keys.append(key)
                continue
            known[key]["qty"] = int(ent.get("current_quantity", 0))
            known[key]["x"] = int(ent.get("x", 0))
            known[key]["y"] = int(ent.get("y", 0))
        for key in remove_keys:
            known.pop(key, None)

    def _guild_board_known_keys(self) -> Set[str]:
        known = self.guild_board_state.get("known_entities", {})
        if not isinstance(known, dict):
            return set()
        return set(str(k) for k in known.keys())

    def _known_cell_keys_for_explore(self, npc: NPC) -> Set[str]:
        known_cells = self.guild_board_state.get("known_cells", {})
        merged: Set[str] = set(known_cells.keys()) if isinstance(known_cells, dict) else set()
        merged.update(str(k) for k in npc.explore_known_buffer.keys())
        return merged

    def _pick_known_entity_tile(self, required_entity_key: str) -> Optional[Tuple[int, int]]:
        known = self.guild_board_state.get("known_entities", {})
        if not isinstance(known, dict):
            return None
        candidates: List[Tuple[int, int]] = []
        req = str(required_entity_key).strip()
        for key, info in known.items():
            k = str(key).strip()
            if not (k == req or k.startswith(f"{req}_")):
                continue
            if not isinstance(info, dict):
                continue
            qty = int(info.get("qty", 0))
            if qty <= 0:
                continue
            candidates.append((int(info.get("x", 0)), int(info.get("y", 0))))
        if not candidates:
            return None
        return self.rng.choice(candidates)

    def _pick_frontier_explore_tile(self, npc: NPC) -> Optional[Tuple[int, int]]:
        known_keys = self._known_cell_keys_for_explore(npc)

        frontier: Set[Tuple[int, int]] = set()
        for key in known_keys:
            tile = self._tile_from_key(key)
            if tile is None:
                continue
            tx, ty = tile
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx = max(0, min(GRID_W - 1, tx + dx))
                ny = max(0, min(GRID_H - 1, ty + dy))
                nkey = self._tile_key(nx, ny)
                if nkey not in known_keys and self.is_outside_tile(nx, ny):
                    frontier.add((nx, ny))

        if frontier:
            return self.rng.choice(list(frontier))
        return self.random_outside_tile()

    def _assign_next_explore_target(self, npc: NPC) -> bool:
        tile = self._pick_frontier_explore_tile(npc)
        if tile is None:
            npc.explore_target_tile = None
            return False
        npc.explore_target_tile = tile
        return True

    def _submit_adventurer_loot_to_board(self, npc: NPC) -> int:
        guild = self.bstate.get("모험가 길드")
        if guild is None:
            return 0
        gathered_keys: Set[str] = set()
        for action_name in ADVENTURER_GATHER_ACTIONS:
            action = self.action_defs.get(action_name, {})
            if not isinstance(action, dict):
                continue
            outputs = action.get("outputs", {})
            if not isinstance(outputs, dict):
                continue
            for item_key in outputs.keys():
                key = str(item_key).strip()
                if key:
                    gathered_keys.add(key)

        moved = 0
        for key in sorted(gathered_keys):
            qty = int(npc.inventory.get(key, 0))
            if qty <= 0:
                continue
            npc.inventory.pop(key, None)
            guild.inventory[key] = int(guild.inventory.get(key, 0)) + qty
            moved += qty

        if moved > 0:
            guild.last_event = f"{npc.traits.name} 채집물 제출({moved})"
            npc.status.happiness += 1
            self._status_clamp(npc)
        return moved

    def _do_board_check(self, npc: NPC) -> str:
        npc.adventurer_board_visited = True
        npc.explore_target_tile = None
        npc.explore_chain_remaining = 0
        merged = self._flush_explore_buffer_to_board(npc)
        submitted = self._submit_adventurer_loot_to_board(npc) if npc.traits.job == JobType.ADVENTURER else 0
        self._sync_guild_board_quantities()
        known = self.guild_board_state.get("known_entities", {})
        known_count = len(known) if isinstance(known, dict) else 0
        if submitted > 0:
            return f"{npc.traits.name}: 길드 게시판 확인(등록 {known_count}, 셀갱신 {merged}, 제출 {submitted})"
        return f"{npc.traits.name}: 길드 게시판 확인(등록 {known_count}, 셀갱신 {merged})"

    def _do_explore_action(self, npc: NPC) -> str:
        tx, ty = world_px_to_tile(npc.x, npc.y)
        npc.adventurer_board_visited = False
        npc.explore_target_tile = None

        if npc.explore_chain_remaining > 0:
            npc.explore_chain_remaining -= 1

        if npc.explore_chain_remaining > 0 and self._assign_next_explore_target(npc):
            self._set_target_outside(npc, npc.explore_target_tile)
            ntx, nty = npc.explore_target_tile or (tx, ty)
            npc.current_action_detail = f"탐색연속({ntx},{nty})/잔여 {npc.explore_chain_remaining}틱"
            npc.status.current_action = npc.current_action_detail
            return f"{npc.traits.name}: 탐색 지점 도착({tx},{ty}) -> 다음 탐색({ntx},{nty}), 잔여 {npc.explore_chain_remaining}틱"

        planned_ticks = int(self.explore_duration_ticks)
        npc.current_work_action = "게시판확인"
        npc.work_ticks_remaining = 0
        npc.explore_chain_remaining = 0
        board_tile = self.guild_board_tile or self.entity_manager.resolve_target_tile("guild_board")
        if board_tile is not None:
            self._set_target_entity(npc, board_tile)
        else:
            self._set_target_outside(npc, self.random_outside_tile())
        return f"{npc.traits.name}: 탐색 지점 도착({tx},{ty}) 후 게시판 복귀(계획 지속 {planned_ticks}틱)"

    def _pick_adventurer_work_action(self, npc: NPC) -> Optional[str]:
        if not npc.adventurer_board_visited:
            return "게시판확인"
        known_keys = self._guild_board_known_keys()
        if not known_keys:
            return "탐색"
        candidate_actions = self.job_work_actions.get(JobType.ADVENTURER.value, [])
        viable: List[str] = []
        for action_name in candidate_actions:
            if action_name in ("게시판확인", "탐색"):
                continue
            action = self.action_defs.get(action_name, {})
            entity_key = str(action.get("required_entity", "")).strip() if isinstance(action, dict) else ""
            if not entity_key:
                continue
            if entity_key in known_keys or any(x.startswith(f"{entity_key}_") for x in known_keys):
                viable.append(action_name)
        if not viable:
            return "탐색"
        return self.rng.choice(viable)

    def _execute_primary_action(self, npc: NPC) -> str:
        prev_action = npc.current_work_action
        result = self._primary_action(npc)
        if prev_action == "게시판확인":
            result = self._do_board_check(npc)
            npc.current_work_action = None
            npc.work_ticks_remaining = 0
        if npc.traits.job == JobType.ADVENTURER and prev_action in ADVENTURER_GATHER_ACTIONS and npc.current_work_action is None:
            npc.adventurer_board_visited = False
        return result

    # -----------------------------
    # Planning / actions
    # -----------------------------
    def _status_clamp(self, npc: NPC) -> None:
        s = npc.status
        s.money = max(0, s.money)
        s.happiness = clamp(s.happiness)
        s.hunger = clamp(s.hunger)
        s.fatigue = clamp(s.fatigue)
        s.max_hp = max(1, s.max_hp)
        s.hp = max(0, min(s.max_hp, s.hp))
        s.strength = max(1, s.strength)
        s.agility = max(1, s.agility)

    def npc_passive_tick(self, npc: NPC) -> None:
        s = npc.status
        npc.hunger_tick_buffer += float(self.sim_settings.get("hunger_gain_per_tick", 1.0))
        npc.fatigue_tick_buffer += float(self.sim_settings.get("fatigue_gain_per_tick", 1.0))

        hunger_inc = int(npc.hunger_tick_buffer)
        fatigue_inc = int(npc.fatigue_tick_buffer)
        if hunger_inc > 0:
            s.hunger += hunger_inc
            npc.hunger_tick_buffer -= hunger_inc
        if fatigue_inc > 0:
            s.fatigue += fatigue_inc
            npc.fatigue_tick_buffer -= fatigue_inc

        if s.hunger >= 80:
            s.happiness -= 3
        if s.fatigue >= 80:
            s.happiness -= 3
        self._status_clamp(npc)

    def _scheduled_destination_entity_key(self, npc: NPC) -> Optional[str]:
        activity = self.planner.activity_for_hour(self.time.hour)
        if activity == ScheduledActivity.MEAL:
            self.behavior.set_meal_state(npc)
            return "dining_table"
        if activity == ScheduledActivity.SLEEP:
            self.behavior.set_sleep_state(npc)
            return "bed"
        return None

    def _set_target_outside(self, npc: NPC, tile: Tuple[int, int]) -> None:
        npc.target_outside_tile = tile
        npc.target_entity_tile = None
        npc.path = manhattan_path(world_px_to_tile(npc.x, npc.y), tile)

    def _set_target_entity(self, npc: NPC, tile: Tuple[int, int]) -> None:
        npc.target_outside_tile = None
        npc.target_entity_tile = tile
        npc.path = manhattan_path(world_px_to_tile(npc.x, npc.y), tile)


    def _is_matching_entity_target(self, entity_key: str, tile: Tuple[int, int]) -> bool:
        tx, ty = tile
        candidates = self.entity_manager.candidates_by_key(entity_key, discovered_only=False)
        return any(int(ent.get("x", -1)) == tx and int(ent.get("y", -1)) == ty for ent in candidates)

    def _has_valid_work_target(self, npc: NPC) -> bool:
        action_name = npc.current_work_action or ""
        if not action_name:
            return True
        if action_name == "탐색":
            return npc.target_outside_tile is not None
        action = self.action_defs.get(action_name, {})
        required_entity = str(action.get("required_entity", "")).strip() if isinstance(action, dict) else ""
        if not required_entity:
            return True
        if npc.target_entity_tile is None:
            return False
        return self._is_matching_entity_target(required_entity, npc.target_entity_tile)


    def _is_hostile(self, npc: NPC) -> bool:
        return bool(getattr(npc.traits, "is_hostile", False))

    def _nearest_hostile(self, npc: NPC) -> Optional[NPC]:
        candidates = [x for x in self.npcs if x is not npc and self._is_hostile(x) and x.status.hp > 0]
        if not candidates:
            return None
        ntx, nty = world_px_to_tile(npc.x, npc.y)
        return min(candidates, key=lambda x: abs(ntx - world_px_to_tile(x.x, x.y)[0]) + abs(nty - world_px_to_tile(x.x, x.y)[1]))

    def _plan_next_target(self, npc: NPC) -> None:
        if npc.status.hp <= 0:
            npc.path = []
            npc.target_outside_tile = None
            npc.target_entity_tile = None
            self.behavior.set_dead_state(npc)
            return

        if self._is_hostile(npc):
            self.behavior.set_wander_state(npc)
            self._set_target_outside(npc, self.random_outside_tile())
            return

        override_entity_key = self._scheduled_destination_entity_key(npc)
        if override_entity_key is not None:
            tile = self.entity_manager.resolve_target_tile(override_entity_key)
            if tile is not None:
                self._set_target_entity(npc, tile)
            else:
                self._set_target_outside(npc, self.random_outside_tile())
            return

        activity = self.behavior.activity_for_hour(self.time.hour)
        if activity == ScheduledActivity.WORK:
            if npc.current_work_action is None:
                npc.current_work_action = self._pick_work_action(npc)
                npc.work_ticks_remaining = 0
            npc.current_action_detail = npc.current_work_action or "업무"
            npc.status.current_action = npc.current_work_action or "업무"

            if npc.traits.job == JobType.ADVENTURER and npc.current_work_action == "게시판확인":
                board_tile = self.guild_board_tile or self.entity_manager.resolve_target_tile("guild_board")
                if board_tile is not None:
                    self._set_target_entity(npc, board_tile)
                else:
                    self._set_target_outside(npc, self.random_outside_tile())
                return

            if npc.traits.job == JobType.ADVENTURER and npc.current_work_action == "탐색":
                if npc.explore_chain_remaining <= 0:
                    npc.explore_chain_remaining = int(self.explore_duration_ticks)
                if npc.explore_target_tile is None:
                    if not self._assign_next_explore_target(npc):
                        npc.current_work_action = "게시판확인"
                        board_tile = self.guild_board_tile or self.entity_manager.resolve_target_tile("guild_board")
                        if board_tile is not None:
                            self._set_target_entity(npc, board_tile)
                        else:
                            self._set_target_outside(npc, self.random_outside_tile())
                        return
                self._set_target_outside(npc, npc.explore_target_tile)
                if npc.explore_target_tile is not None:
                    tx, ty = npc.explore_target_tile
                    npc.current_action_detail = f"탐색목표({tx},{ty})/잔여 {npc.explore_chain_remaining}틱"
                    npc.status.current_action = npc.current_action_detail
                return

            if npc.traits.job == JobType.ADVENTURER and (npc.current_work_action or "") in ADVENTURER_GATHER_ACTIONS:
                action = self.action_defs.get(npc.current_work_action or "", {})
                required_key = str(action.get("required_entity", "")).strip() if isinstance(action, dict) else ""
                known_tile = self._pick_known_entity_tile(required_key)
                if known_tile is not None:
                    self._set_target_entity(npc, known_tile)
                else:
                    npc.current_work_action = "탐색"
                    npc.work_ticks_remaining = 0
                    npc.explore_chain_remaining = int(self.explore_duration_ticks)
                    if self._assign_next_explore_target(npc):
                        self._set_target_outside(npc, npc.explore_target_tile)
                    else:
                        npc.current_work_action = "게시판확인"
                        board_tile = self.guild_board_tile or self.entity_manager.resolve_target_tile("guild_board")
                        if board_tile is not None:
                            self._set_target_entity(npc, board_tile)
                        else:
                            self._set_target_outside(npc, self.random_outside_tile())
                return

            target_entity, target_outside = self.action_executor.resolve_work_destination(npc, self.random_outside_tile)
            if target_entity is not None:
                self._set_target_entity(npc, target_entity)
            elif target_outside is not None:
                self._set_target_outside(npc, target_outside)
            else:
                self._set_target_outside(npc, self.random_outside_tile())
            return

        home_tile = self.entity_manager.resolve_target_tile("bed")
        if home_tile is not None:
            self._set_target_entity(npc, home_tile)
        else:
            self._set_target_outside(npc, self.random_outside_tile())

    def _pick_work_action(self, npc: NPC) -> Optional[str]:
        if npc.traits.job == JobType.ADVENTURER:
            return self._pick_adventurer_work_action(npc)
        actions = self.job_work_actions.get(npc.traits.job.value, [])
        if not actions:
            return None
        return self.rng.choice(actions)

    def _do_eat_at_restaurant(self, npc: NPC) -> str:
        return self.action_executor.do_eat_at_restaurant(npc)

    def _do_rest_at_home(self, npc: NPC) -> str:
        return self.action_executor.do_rest_at_home(npc)

    def _primary_action(self, npc: NPC) -> str:
        return self.action_executor.primary_action(npc)

    def _profit_action(self, npc: NPC) -> str:
        return self.action_executor.profit_action(npc)

    def _try_execute_arrived_work(self, npc: NPC, tx: int, ty: int) -> bool:
        if npc.current_work_action is None:
            return False

        # 게시판확인/탐색은 반드시 각 목표 지점(게시판 엔티티/탐색 타일) 도착 후에만 실행한다.
        # 건물 목표 잔재 없이, 엔티티/외부 타일 목표 도착 기준으로만 업무를 실행한다.
        if npc.current_work_action == "탐색" and npc.target_outside_tile is not None:
            if (tx, ty) == npc.target_outside_tile:
                self.logs.append(self._do_explore_action(npc))
                self._plan_next_target(npc)
                return True
            return False

        if npc.current_work_action == "게시판확인" and npc.target_entity_tile is not None:
            if self._is_matching_entity_target("guild_board", npc.target_entity_tile):
                ex, ey = npc.target_entity_tile
                if (tx, ty) == (ex, ey) or (abs(tx - ex) + abs(ty - ey) <= 1):
                    self.logs.append(self._execute_primary_action(npc))
                    self._plan_next_target(npc)
                    return True
            return False

        if npc.target_entity_tile is not None and self._has_valid_work_target(npc):
            ex, ey = npc.target_entity_tile
            if (tx, ty) == (ex, ey) or (abs(tx - ex) + abs(ty - ey) <= 1):
                self.logs.append(self._execute_primary_action(npc))
                self._plan_next_target(npc)
                return True

        return False

    # -----------------------------
    # Tick + movement
    # -----------------------------
    def _ensure_work_actions_selected(self) -> None:
        if self.behavior.activity_for_hour(self.time.hour) != ScheduledActivity.WORK:
            return
        for npc in self.npcs:
            if npc.status.hp <= 0 or self._is_hostile(npc):
                continue
            if npc.current_work_action is None:
                npc.current_work_action = self._pick_work_action(npc)
                npc.work_ticks_remaining = 0
            detail = npc.current_work_action or "업무선택실패"
            self.behavior.set_activity(npc, "업무", detail)

    def sim_tick(self) -> None:
        self.time.advance(SIM_TICK_MINUTES)
        self._ensure_work_actions_selected()
        for npc in self.npcs:
            if npc.status.hp > 0:
                self.npc_passive_tick(npc)

        if self.time.total_minutes % 60 == 0:
            self.logs.extend(resolve_combat_round(self.npcs, self.combat_settings, self.rng))
            eco_logs: List[str] = []
            self.last_economy_snapshot = self.economy.run_hour(self.npcs, self.bstate, eco_logs)
            self.logs.extend(eco_logs[-4:])
            self._sync_guild_board_quantities()

        for npc in self.npcs:
            if npc.status.hp <= 0:
                continue
            tx, ty = world_px_to_tile(npc.x, npc.y)
            npc.location_building = self.find_building_by_tile(tx, ty)

            if len(npc.path) == 0:
                current_activity = self.planner.activity_for_hour(self.time.hour)
                if current_activity == ScheduledActivity.WORK and not self._has_valid_work_target(npc):
                    self._plan_next_target(npc)
                    if npc.path:
                        continue

                if self._try_execute_arrived_work(npc, tx, ty):
                    continue

                current_activity = self.planner.activity_for_hour(self.time.hour)
                if current_activity == ScheduledActivity.MEAL and npc.target_entity_tile is not None:
                    if (tx, ty) == npc.target_entity_tile or (abs(tx - npc.target_entity_tile[0]) + abs(ty - npc.target_entity_tile[1]) <= 1):
                        self.logs.append(self._do_eat_at_restaurant(npc))
                        self._plan_next_target(npc)
                        continue
                if current_activity == ScheduledActivity.SLEEP and npc.target_entity_tile is not None:
                    if (tx, ty) == npc.target_entity_tile or (abs(tx - npc.target_entity_tile[0]) + abs(ty - npc.target_entity_tile[1]) <= 1):
                        self.logs.append(self._do_rest_at_home(npc))
                        self._plan_next_target(npc)
                        continue

                if self._is_hostile(npc) and npc.target_outside_tile is not None:
                    if (tx, ty) == npc.target_outside_tile:
                        self.logs.append(f"{npc.traits.name}: 적대 배회")
                        self._plan_next_target(npc)
                        continue

                if current_activity == ScheduledActivity.WORK and npc.target_entity_tile is not None:
                    if (tx, ty) == npc.target_entity_tile or (abs(tx - npc.target_entity_tile[0]) + abs(ty - npc.target_entity_tile[1]) <= 1):
                        self.logs.append(self._execute_primary_action(npc))
                        self._plan_next_target(npc)
                        continue

                action = self.action_defs.get(npc.current_work_action or "", {})
                required_entity = str(action.get("required_entity", "")).strip() if isinstance(action, dict) else ""
                needs_external_target = bool(required_entity) or (npc.current_work_action == "탐색")

                if current_activity == ScheduledActivity.WORK and not needs_external_target:
                    self.logs.append(self._execute_primary_action(npc))
                self._plan_next_target(npc)

        if len(self.logs) > 14:
            self.logs = self.logs[-14:]

    def update_movement(self, dt: float) -> None:
        for npc in self.npcs:
            if not npc.path:
                continue
            tx, ty = npc.path[0]
            gx, gy = tile_to_world_px_center(tx, ty)
            dx = gx - npc.x
            dy = gy - npc.y
            dist = (dx * dx + dy * dy) ** 0.5
            if dist < 1e-6:
                npc.x, npc.y = float(gx), float(gy)
                npc.path.pop(0)
                if npc.traits.job == JobType.ADVENTURER and npc.current_work_action == "탐색":
                    self._record_known_area_to_buffer(npc, (tx, ty))
                continue
            step = float(self.sim_settings.get("npc_speed", 220.0)) * dt
            if step >= dist:
                npc.x, npc.y = float(gx), float(gy)
                npc.path.pop(0)
                if npc.traits.job == JobType.ADVENTURER and npc.current_work_action == "탐색":
                    self._record_known_area_to_buffer(npc, (tx, ty))
            else:
                npc.x += dx / dist * step
                npc.y += dy / dist * step


# ============================================================
# Minimap
# ============================================================
def draw_minimap(screen: pygame.Surface, game: VillageGame, small: pygame.font.Font) -> pygame.Rect:
    x = SCREEN_W - MINIMAP_W - MINIMAP_PAD
    y = MINIMAP_PAD
    rect = pygame.Rect(x, y, MINIMAP_W, MINIMAP_H)
    pygame.draw.rect(screen, (15, 15, 18), rect)
    pygame.draw.rect(screen, (0, 0, 0), rect, 2)

    ww = world_w_px()
    wh = world_h_px()
    s = min(MINIMAP_W / ww, MINIMAP_H / wh)

    def w2m(wx: float, wy: float) -> Tuple[int, int]:
        return int(x + wx * s), int(y + wy * s)

    zone_colors = {
        ZoneType.MARKET: (70, 90, 120),
        ZoneType.RESIDENTIAL: (70, 110, 70),
        ZoneType.JOB: (110, 70, 70),
        ZoneType.INTERACTION: (110, 100, 70),
    }

    # Zones outlines
    for z in game.zones:
        r = z.rect_tiles
        wx0, wy0 = r.x * BASE_TILE_SIZE, r.y * BASE_TILE_SIZE
        ww0, wh0 = r.w * BASE_TILE_SIZE, r.h * BASE_TILE_SIZE
        rx, ry = w2m(wx0, wy0)
        rw, rh = max(1, int(ww0 * s)), max(1, int(wh0 * s))
        pygame.draw.rect(screen, zone_colors[z.zone_type], pygame.Rect(rx, ry, rw, rh), 1)

    # Village outline
    vr = game.village_rect_tiles
    vwx, vwy = vr.x * BASE_TILE_SIZE, vr.y * BASE_TILE_SIZE
    vww, vwh = vr.w * BASE_TILE_SIZE, vr.h * BASE_TILE_SIZE
    vx, vy = w2m(vwx, vwy)
    vw, vh = max(1, int(vww * s)), max(1, int(vwh * s))
    pygame.draw.rect(screen, (240, 240, 240), pygame.Rect(vx, vy, vw, vh), 1)

    # NPCs
    for npc in game.npcs:
        mx, my = w2m(npc.x, npc.y)
        pygame.draw.circle(screen, (230, 230, 230), (mx, my), 2)

    # Camera viewport
    view_w = SCREEN_W / game.camera.zoom
    view_h = SCREEN_H / game.camera.zoom
    mx0, my0 = w2m(game.camera.x, game.camera.y)
    mvw, mvh = max(1, int(view_w * s)), max(1, int(view_h * s))
    pygame.draw.rect(screen, (255, 255, 255), pygame.Rect(mx0, my0, mvw, mvh), 1)

    screen.blit(small.render("미니맵(클릭 이동)", True, (200, 200, 200)), (x + 8, y + 6))
    return rect


def minimap_click_to_world(pos: Tuple[int, int], minimap_rect: pygame.Rect) -> Tuple[float, float]:
    mx, my = pos
    lx = mx - minimap_rect.x
    ly = my - minimap_rect.y
    ww = world_w_px()
    wh = world_h_px()
    s = min(MINIMAP_W / ww, MINIMAP_H / wh)
    wx = max(0.0, min(float(ww), lx / s))
    wy = max(0.0, min(float(wh), ly / s))
    return wx, wy


# ============================================================
# Modals
# ============================================================
def draw_building_modal(screen: pygame.Surface, game: VillageGame, font: pygame.font.Font, small: pygame.font.Font):
    bname = game.selected_building or "(건물 없음)"
    rect = draw_modal_frame(screen, f"건물 정보 - {bname}", font)

    tabs = [(BuildingTab.PEOPLE.value, BuildingTab.PEOPLE), (BuildingTab.STOCK.value, BuildingTab.STOCK), (BuildingTab.TASK.value, BuildingTab.TASK)]
    tab_rects = draw_tabs(screen, rect, tabs, game.building_tab, small)

    body = pygame.Rect(rect.x + 16, rect.y + 90, rect.w - 32, rect.h - 110)
    pygame.draw.rect(screen, (14, 14, 18), body)
    pygame.draw.rect(screen, (0, 0, 0), body, 2)

    if game.selected_building is None:
        draw_text_lines(screen, small, body.x + 12, body.y + 12, ["선택된 건물이 없습니다."])
        return rect, tab_rects

    st = game.bstate[game.selected_building]

    if game.building_tab == BuildingTab.PEOPLE:
        occupants = [npc for npc in game.npcs if npc.location_building is not None and npc.location_building.name == game.selected_building]
        lines = [f"현재 인원: {len(occupants)}명", ""]
        draw_text_lines(screen, small, body.x + 12, body.y + 12, lines)
        y = body.y + 12 + 20 * len(lines)
        if not occupants:
            draw_text_lines(screen, small, body.x + 12, y, ["(현재 건물에 있는 인원이 없습니다.)"])
        else:
            screen.blit(small.render("이름     직업     현재행동", True, (200, 200, 200)), (body.x + 12, y))
            y += 22
            for npc in occupants:
                row = f"{npc.traits.name:6s}  {npc.traits.job.value:6s}  {npc.status.current_action}"
                screen.blit(small.render(row, True, (230, 230, 230)), (body.x + 12, y))
                y += 20

    elif game.building_tab == BuildingTab.STOCK:
        draw_text_lines(screen, small, body.x + 12, body.y + 12, ["보유 물품(재고):", ""])
        y = body.y + 12 + 40
        if not st.inventory:
            draw_text_lines(screen, small, body.x + 12, y, ["(재고 없음)"])
        else:
            screen.blit(small.render("아이템            수량", True, (200, 200, 200)), (body.x + 12, y))
            y += 22
            for k, q in sorted(st.inventory.items(), key=lambda kv: kv[0]):
                disp = game.items[k].display if k in game.items else k
                screen.blit(small.render(f"{disp:12s}   {q:>4d}", True, (230, 230, 230)), (body.x + 12, y))
                y += 20

    else:
        lines = [
            f"작업 상태: {st.task}",
            f"진행도: {st.task_progress}%",
            "",
            f"최근 이벤트: {st.last_event if st.last_event else '(없음)'}",
            "",
            "표 기준 행동:",
            "- 현재 시간표/직업에 맞는 행동을 수행",
            "- 현재 행동은 NPC 스테이터스의 '현재 행동'으로 표시",
        ]
        draw_text_lines(screen, small, body.x + 12, body.y + 12, lines)

    screen.blit(small.render("I/ESC: 닫기 | 1/2/3: 탭 | 탭 클릭 가능", True, (200, 200, 200)), (rect.x + 16, rect.bottom - 26))
    return rect, tab_rects


def draw_npc_modal(screen: pygame.Surface, game: VillageGame, font: pygame.font.Font, small: pygame.font.Font):
    # ✅ 이번 요청: NPC 모달 추가
    if game.selected_npc is None:
        rect = draw_modal_frame(screen, "NPC 정보 - (선택 없음)", font)
        body = pygame.Rect(rect.x + 16, rect.y + 90, rect.w - 32, rect.h - 110)
        pygame.draw.rect(screen, (14, 14, 18), body)
        pygame.draw.rect(screen, (0, 0, 0), body, 2)
        draw_text_lines(screen, small, body.x + 12, body.y + 12, ["선택된 NPC가 없습니다."])
        return rect, {}

    npc = game.npcs[game.selected_npc]
    rect = draw_modal_frame(screen, f"NPC 정보 - {npc.traits.name}", font)

    tabs = [(NPCTab.TRAITS.value, NPCTab.TRAITS), (NPCTab.STATUS.value, NPCTab.STATUS), (NPCTab.INVENTORY.value, NPCTab.INVENTORY)]
    tab_rects = draw_tabs(screen, rect, tabs, game.npc_tab, small)

    body = pygame.Rect(rect.x + 16, rect.y + 90, rect.w - 32, rect.h - 110)
    pygame.draw.rect(screen, (14, 14, 18), body)
    pygame.draw.rect(screen, (0, 0, 0), body, 2)

    t = npc.traits
    s = npc.status

    if game.npc_tab == NPCTab.TRAITS:
        lines = [
            "캐릭터 트레잇",
            "",
            f"이름: {t.name}",
            f"종족: {t.race}",
            f"성별: {t.gender}",
            f"나이: {t.age}",
            f"직업: {t.job.value}",
            f"종족 보너스(힘/민첩/체력/이속): {t.race_str_bonus}/{t.race_agi_bonus}/{t.race_hp_bonus}/{t.race_speed_bonus}",
            f"적대 여부: {'예' if t.is_hostile else '아니오'}",
        ]
        draw_text_lines(screen, small, body.x + 12, body.y + 12, lines)

    elif game.npc_tab == NPCTab.STATUS:
        tx, ty = world_px_to_tile(npc.x, npc.y)
        region = RegionType.OUTSIDE.value if game.is_outside_tile(tx, ty) else RegionType.VILLAGE.value
        loc = region
        if npc.location_building is not None:
            loc = f"{region} / {npc.location_building.zone.value}/{npc.location_building.name}"
        tgt = "(없음)"
        if npc.target_entity_tile is not None:
            tgt = f"엔티티 타일 {npc.target_entity_tile}"
        elif npc.target_outside_tile is not None:
            tgt = f"{RegionType.OUTSIDE.value} 타일 {npc.target_outside_tile}"
        lines = [
            "스테이터스",
            "",
            f"현재 위치: {loc}",
            f"행동 분류: {npc.current_activity}",
            f"행동 세부: {npc.current_action_detail}",
            f"현재 행동: {npc.status.current_action}",
            f"이동 목표: {tgt}",
            "",
            f"돈: {s.money}",
            f"행복: {s.happiness}",
            f"허기: {s.hunger}",
            f"피로: {s.fatigue}",
            f"체력: {s.hp}/{s.max_hp}",
            f"힘: {s.strength}",
            f"민첩: {s.agility}",
        ]
        draw_text_lines(screen, small, body.x + 12, body.y + 12, lines)

    else:
        draw_text_lines(screen, small, body.x + 12, body.y + 12, ["인벤토리", ""])
        y = body.y + 12 + 40
        if not npc.inventory:
            draw_text_lines(screen, small, body.x + 12, y, ["(인벤토리가 비어 있습니다.)"])
        else:
            screen.blit(small.render("아이템            수량", True, (200, 200, 200)), (body.x + 12, y))
            y += 22
            for k, q in sorted(npc.inventory.items(), key=lambda kv: kv[0]):
                disp = game.items[k].display if k in game.items else k
                screen.blit(small.render(f"{disp:12s}   {q:>4d}", True, (230, 230, 230)), (body.x + 12, y))
                y += 20

    screen.blit(small.render("I/ESC: 닫기 | 1/2/3: 탭 | 탭 클릭 가능", True, (200, 200, 200)), (rect.x + 16, rect.bottom - 26))
    return rect, tab_rects


def draw_board_modal(screen: pygame.Surface, game: VillageGame, font: pygame.font.Font, small: pygame.font.Font):
    rect = draw_modal_frame(screen, "길드 게시판", font)
    tabs = [(BoardTab.ENTITIES.value, BoardTab.ENTITIES), (BoardTab.CELLS.value, BoardTab.CELLS), (BoardTab.INVENTORY.value, BoardTab.INVENTORY), (BoardTab.EXPLORE.value, BoardTab.EXPLORE)]
    tab_rects = draw_tabs(screen, rect, tabs, game.board_tab, small)

    body = pygame.Rect(rect.x + 16, rect.y + 90, rect.w - 32, rect.h - 110)
    pygame.draw.rect(screen, (14, 14, 18), body)
    pygame.draw.rect(screen, (0, 0, 0), body, 2)

    if game.board_tab == BoardTab.ENTITIES:
        known = game.guild_board_state.get("known_entities", {})
        rows = sorted(known.items(), key=lambda kv: str(kv[0])) if isinstance(known, dict) else []
        draw_text_lines(screen, small, body.x + 12, body.y + 12, [f"등록 자원 수: {len(rows)}", ""])
        y = body.y + 52
        if not rows:
            draw_text_lines(screen, small, body.x + 12, y, ["(등록된 자원이 없습니다.)"])
        else:
            for key, info in rows[:12]:
                if not isinstance(info, dict):
                    continue
                name = str(info.get("name", key))
                x = int(info.get("x", 0))
                yv = int(info.get("y", 0))
                qty = int(info.get("qty", 0))
                screen.blit(small.render(f"{name}({key}) @({x},{yv}) 수량:{qty}", True, (230, 230, 230)), (body.x + 12, y))
                y += 20

    elif game.board_tab == BoardTab.CELLS:
        known_cells = game.guild_board_state.get("known_cells", {})
        rows = sorted(known_cells.items(), key=lambda kv: str(kv[0])) if isinstance(known_cells, dict) else []
        draw_text_lines(screen, small, body.x + 12, body.y + 12, [f"탐색 기록 셀: {len(rows)}", ""])
        map_rect = pygame.Rect(body.right - 260, body.y + 12, 248, 248)
        pygame.draw.rect(screen, (20, 20, 25), map_rect)
        pygame.draw.rect(screen, (0, 0, 0), map_rect, 2)

        if rows:
            points: List[Tuple[int, int]] = []
            for key, _ in rows:
                tile = game._tile_from_key(str(key))
                if tile is not None:
                    points.append(tile)

            if points:
                min_x = min(x for x, _ in points)
                max_x = max(x for x, _ in points)
                min_y = min(y for _, y in points)
                max_y = max(y for _, y in points)
                span_x = max(1, max_x - min_x + 1)
                span_y = max(1, max_y - min_y + 1)
                cell_px = int(max(2, min((map_rect.w - 16) / span_x, (map_rect.h - 16) / span_y)))
                origin_x = map_rect.x + (map_rect.w - span_x * cell_px) // 2
                origin_y = map_rect.y + (map_rect.h - span_y * cell_px) // 2

                for tx, ty in points:
                    px = origin_x + (tx - min_x) * cell_px
                    py = origin_y + (ty - min_y) * cell_px
                    pygame.draw.rect(screen, (82, 134, 212), pygame.Rect(px, py, cell_px, cell_px))

                for key, info in rows:
                    tile = game._tile_from_key(str(key))
                    if tile is None or not isinstance(info, dict):
                        continue
                    tx, ty = tile
                    cx = origin_x + (tx - min_x) * cell_px + cell_px // 2
                    cy = origin_y + (ty - min_y) * cell_px + cell_px // 2
                    entities = info.get("entities", [])
                    monsters = info.get("monsters", [])
                    if isinstance(entities, list) and len(entities) > 0:
                        pygame.draw.circle(screen, (60, 220, 110), (cx - 2, cy), max(2, cell_px // 4))
                    if isinstance(monsters, list) and len(monsters) > 0:
                        pygame.draw.circle(screen, (235, 70, 70), (cx + 2, cy), max(2, cell_px // 4))

                latest_tile = game._tile_from_key(str(rows[-1][0]))
                if latest_tile is not None:
                    lx, ly = latest_tile
                    lpx = origin_x + (lx - min_x) * cell_px
                    lpy = origin_y + (ly - min_y) * cell_px
                    pygame.draw.rect(screen, (255, 224, 80), pygame.Rect(lpx, lpy, cell_px, cell_px), 2)
            screen.blit(small.render("파랑=기록 셀 / 초록=자원 / 빨강=몬스터", True, (200, 200, 200)), (map_rect.x + 8, map_rect.bottom - 22))
        else:
            screen.blit(small.render("기록 없음", True, (170, 170, 170)), (map_rect.x + 86, map_rect.y + 112))

        y = body.y + 52
        text_limit_x = map_rect.x - 16
        if not rows:
            draw_text_lines(screen, small, body.x + 12, y, ["(탐색 기록이 없습니다.)"])
        else:
            for tkey, info in rows[-10:]:
                if not isinstance(info, dict):
                    continue
                entities = info.get("entities", [])
                monsters = info.get("monsters", [])
                updated = int(info.get("updated_at", 0))
                line = f"{tkey} | 자원 {len(entities)} | 몬스터 {len(monsters)} | 갱신 {updated}분"
                if body.x + 12 + small.size(line)[0] > text_limit_x:
                    clipped = line
                    while clipped and body.x + 12 + small.size(clipped + "...")[0] > text_limit_x:
                        clipped = clipped[:-1]
                    line = (clipped + "...") if clipped else "..."
                screen.blit(small.render(line, True, (230, 230, 230)), (body.x + 12, y))
                y += 20

    elif game.board_tab == BoardTab.INVENTORY:
        guild = game.bstate.get("모험가 길드")
        inv = guild.inventory if guild is not None else {}
        draw_text_lines(screen, small, body.x + 12, body.y + 12, ["길드 인벤토리", ""])
        y = body.y + 52
        if not isinstance(inv, dict) or not inv:
            draw_text_lines(screen, small, body.x + 12, y, ["(보관된 물품이 없습니다.)"])
        else:
            screen.blit(small.render("아이템            수량", True, (200, 200, 200)), (body.x + 12, y))
            y += 24
            for k, q in sorted(inv.items(), key=lambda kv: str(kv[0])):
                if int(q) <= 0:
                    continue
                disp = game.items[k].display if k in game.items else k
                screen.blit(small.render(f"{disp:12s}   {int(q):>4d}", True, (230, 230, 230)), (body.x + 12, y))
                y += 20
        if guild is not None and str(guild.last_event).strip():
            screen.blit(small.render(f"최근 제출: {guild.last_event}", True, (180, 210, 180)), (body.x + 12, body.bottom - 28))

    else:
        draw_text_lines(screen, small, body.x + 12, body.y + 12, [
            "탐색은 선택한 지속 틱 동안 연속으로 진행됩니다.",
            "아래 버튼으로 탐색 지속 시간(틱)을 선택하세요.",
            "",
        ])
        btn_y = body.y + 90
        btn_w = 160
        btn_h = 42
        gap = 14
        for idx, ticks in enumerate((6, 12, 18)):
            bx = body.x + 12 + idx * (btn_w + gap)
            r = pygame.Rect(bx, btn_y, btn_w, btn_h)
            active = (game.explore_duration_ticks == ticks)
            pygame.draw.rect(screen, (75, 95, 85) if active else (40, 40, 48), r)
            pygame.draw.rect(screen, (0, 0, 0), r, 2)
            label = f"지속 {ticks}틱"
            screen.blit(small.render(label, True, (240, 240, 240)), (r.x + 42, r.y + 12))
            if active:
                screen.blit(small.render("선택됨", True, (210, 255, 210)), (r.x + 52, r.y + 24))

    screen.blit(small.render("I/ESC: 닫기 | 1/2/3/4: 탭 | (탐색 설정 탭) 버튼 클릭으로 틱 선택", True, (200, 200, 200)), (rect.x + 16, rect.bottom - 26))
    return rect, tab_rects


# ============================================================
# Rendering
# ============================================================
def draw_world(screen: pygame.Surface, game: VillageGame, small: pygame.font.Font):
    cam = game.camera
    screen.fill((28, 30, 34))

    # visible tile range
    view_w_world = SCREEN_W / cam.zoom
    view_h_world = SCREEN_H / cam.zoom
    x0 = int(cam.x // BASE_TILE_SIZE)
    y0 = int(cam.y // BASE_TILE_SIZE)
    x1 = int((cam.x + view_w_world) // BASE_TILE_SIZE) + 2
    y1 = int((cam.y + view_h_world) // BASE_TILE_SIZE) + 2
    x0 = max(0, min(GRID_W - 1, x0))
    y0 = max(0, min(GRID_H - 1, y0))
    x1 = max(0, min(GRID_W, x1))
    y1 = max(0, min(GRID_H, y1))

    ts = int(BASE_TILE_SIZE * cam.zoom)

    # background tiles
    for ty in range(y0, y1):
        for tx in range(x0, x1):
            wx = tx * BASE_TILE_SIZE
            wy = ty * BASE_TILE_SIZE
            sx, sy = cam.world_to_screen(wx, wy)
            r = pygame.Rect(sx, sy, ts, ts)
            if game.is_outside_tile(tx, ty):
                pygame.draw.rect(screen, (30, 32, 36), r)
                if ts >= 10:
                    pygame.draw.rect(screen, (18, 18, 20), r, 1)
            else:
                pygame.draw.rect(screen, (40, 44, 50), r)
                if ts >= 10:
                    pygame.draw.rect(screen, (24, 26, 30), r, 1)

    zone_colors = {
        ZoneType.MARKET: (70, 90, 120),
        ZoneType.RESIDENTIAL: (70, 110, 70),
        ZoneType.JOB: (110, 70, 70),
        ZoneType.INTERACTION: (110, 100, 70),
    }
    building_colors = {
        ZoneType.MARKET: (55, 75, 105),
        ZoneType.RESIDENTIAL: (55, 95, 55),
        ZoneType.JOB: (95, 55, 55),
        ZoneType.INTERACTION: (95, 85, 55),
    }

    # zones & buildings
    for z in game.zones:
        rzt = z.rect_tiles
        wx0z, wy0z = rzt.x * BASE_TILE_SIZE, rzt.y * BASE_TILE_SIZE
        ww0z, wh0z = rzt.w * BASE_TILE_SIZE, rzt.h * BASE_TILE_SIZE
        sx0z, sy0z = cam.world_to_screen(wx0z, wy0z)
        swz, shz = int(ww0z * cam.zoom), int(wh0z * cam.zoom)
        zrect = pygame.Rect(sx0z, sy0z, swz, shz)
        pygame.draw.rect(screen, zone_colors[z.zone_type], zrect, 0)
        pygame.draw.rect(screen, (0, 0, 0), zrect, 2)
        if cam.zoom >= 0.9:
            screen.blit(small.render(z.zone_type.value, True, (0, 0, 0)), (zrect.x + 6, zrect.y + 6))

        for b in z.buildings:
            bx, by, bw, bh = b.rect_tiles
            bwx, bwy = bx * BASE_TILE_SIZE, by * BASE_TILE_SIZE
            bww, bwh = bw * BASE_TILE_SIZE, bh * BASE_TILE_SIZE
            bsx, bsy = cam.world_to_screen(bwx, bwy)
            bsw, bsh = int(bww * cam.zoom), int(bwh * cam.zoom)
            brect = pygame.Rect(bsx, bsy, bsw, bsh)
            sel = (game.selection_type == SelectionType.BUILDING and game.selected_building == b.name)
            pygame.draw.rect(screen, building_colors[b.zone], brect, 0)
            pygame.draw.rect(screen, (255, 210, 120) if sel else (0, 0, 0), brect, 3 if sel else 2)
            if cam.zoom >= 1.12:
                screen.blit(small.render(b.name, True, (10, 10, 10)), (brect.x + 3, brect.y + 2))

    # village outline
    vr = game.village_rect_tiles
    wx0 = vr.x * BASE_TILE_SIZE
    wy0 = vr.y * BASE_TILE_SIZE
    ww0 = vr.w * BASE_TILE_SIZE
    wh0 = vr.h * BASE_TILE_SIZE
    sx0, sy0 = cam.world_to_screen(wx0, wy0)
    pygame.draw.rect(screen, (230, 230, 230), pygame.Rect(sx0, sy0, int(ww0 * cam.zoom), int(wh0 * cam.zoom)), max(2, int(3 * cam.zoom)))

    # world entities
    for ent in game.entities:
        ex = int(ent.get("x", 0)) * BASE_TILE_SIZE + BASE_TILE_SIZE // 2
        ey = int(ent.get("y", 0)) * BASE_TILE_SIZE + BASE_TILE_SIZE // 2
        is_workbench = bool(ent.get("is_workbench", False))
        cur_q = int(ent.get("current_quantity", 0))
        max_q = max(1, int(ent.get("max_quantity", 1)))
        sx, sy = cam.world_to_screen(ex, ey)
        if is_workbench:
            rw = max(4, int(10 * cam.zoom))
            rh = max(4, int(8 * cam.zoom))
            rect = pygame.Rect(sx - rw // 2, sy - rh // 2, rw, rh)
            pygame.draw.rect(screen, (180, 140, 80), rect)
            pygame.draw.rect(screen, (0, 0, 0), rect, 1)
            if cam.zoom >= 1.0:
                screen.blit(small.render(f"{ent.get('name', '작업대')} {cur_q}/{max_q}", True, (230, 210, 180)), (sx + 6, sy - 8))
        else:
            color = (110, 180, 90)
            rad = max(2, int(6 * cam.zoom))
            pygame.draw.circle(screen, color, (sx, sy), rad)
            pygame.draw.circle(screen, (0, 0, 0), (sx, sy), rad, 1)
            if cam.zoom >= 1.0:
                label = f"{ent.get('name', '자원')} {cur_q}/{max_q}"
                screen.blit(small.render(label, True, (210, 230, 210)), (sx + 6, sy - 8))

    # NPC
    for i, npc in enumerate(game.npcs):
        sel = (game.selection_type == SelectionType.NPC and game.selected_npc == i)
        hostile = game._is_hostile(npc)
        if sel:
            color = (255, 210, 120)
        elif hostile:
            color = (220, 60, 60)
        else:
            color = (230, 230, 230)
        sx, sy = cam.world_to_screen(npc.x, npc.y)
        rad = max(3, int(9 * cam.zoom))
        pygame.draw.circle(screen, color, (sx, sy), rad)
        pygame.draw.circle(screen, (0, 0, 0), (sx, sy), rad, 2)
        if cam.zoom >= 1.15:
            label = small.render(npc.traits.name, True, (240, 240, 240))
            screen.blit(label, (sx - label.get_width() // 2, sy - rad - 18))


def draw_hud(screen: pygame.Surface, game: VillageGame, font: pygame.font.Font, small: pygame.font.Font):
    panel = pygame.Rect(8, 8, 530, 190)
    pygame.draw.rect(screen, (15, 15, 18), panel)
    pygame.draw.rect(screen, (0, 0, 0), panel, 2)
    screen.blit(font.render(str(game.time), True, (240, 240, 240)), (panel.x + 10, panel.y + 8))

    y = panel.y + 46
    econ_line = "경제: 집계 대기"
    if game.last_economy_snapshot is not None:
        snap = game.last_economy_snapshot
        econ_line = f"경제: 유동자금 {snap.total_money}G | 식량재고 {snap.market_food_stock} | 가공품 {snap.crafted_stock}"

    if game.selection_type == SelectionType.NPC and game.selected_npc is not None:
        npc = game.npcs[game.selected_npc]
        s = npc.status
        loc = "마을 밖" if game.is_outside_tile(*world_px_to_tile(npc.x, npc.y)) else "마을"
        lines = [
            f"선택(NPC): {npc.traits.name} / {npc.traits.job.value} / {loc}",
            f"돈 {s.money} | 행복 {s.happiness} | 허기 {s.hunger} | 피로 {s.fatigue}",
            f"HP {s.hp}/{s.max_hp} | 힘 {s.strength} | 민첩 {s.agility}",
            f"행동 분류/세부: {npc.current_activity} / {npc.current_action_detail}",
            f"현재 행동: {npc.status.current_action}",
            econ_line,
            "I: 모달 | 휠: 줌 | 미니맵 클릭: 이동",
        ]
    elif game.selection_type == SelectionType.BUILDING and game.selected_building is not None:
        b = game.building_by_name[game.selected_building]
        st = game.bstate[game.selected_building]
        lines = [
            f"선택(건물): {b.zone.value} / {b.name}",
            f"작업: {st.task} ({st.task_progress}%)",
            f"최근: {st.last_event if st.last_event else '(없음)'}",
            econ_line,
            "I: 모달 | 휠: 줌 | 미니맵 클릭: 이동",
        ]
    elif game.selection_type == SelectionType.BOARD:
        lines = [
            "선택(게시판): 길드 게시판",
            f"탐색 지속 목표: {game.explore_duration_ticks}틱",
            "I: 게시판 모달 열기",
            econ_line,
        ]
    else:
        lines = [
            "NPC/건물/게시판을 클릭하세요.",
            "I: 선택 대상 모달 열기",
            "WASD/화살표: 카메라 이동 | 휠: 줌",
            econ_line,
        ]
    for ln in lines:
        screen.blit(small.render(ln, True, (230, 230, 230)), (panel.x + 10, y))
        y += 22

    # logs
    screen.blit(small.render("최근 행동 로그:", True, (200, 200, 200)), (panel.x + 10, panel.y + 132))
    yy = panel.y + 152
    for ln in game.logs[-3:]:
        screen.blit(small.render(ln, True, (200, 200, 200)), (panel.x + 10, yy))
        yy += 18


# ============================================================
# Main loop
# ============================================================
def main():
    pygame.init()
    pygame.display.set_caption("판타지 마을 시뮬(구역+건물+미니맵+모달)")
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    clock = pygame.time.Clock()

    font = make_font(18)
    small = make_font(14)

    game = VillageGame(seed=42)
    sim_acc_ms = 0
    minimap_rect = pygame.Rect(0, 0, 0, 0)

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0
        sim_acc_ms += int(dt * 1000)

        # --- input ---
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False

            elif ev.type == pygame.MOUSEWHEEL:
                # zoom at mouse
                mx, my = pygame.mouse.get_pos()
                if ev.y > 0:
                    game.camera.zoom_at(mx, my, game.camera.zoom * ZOOM_STEP)
                elif ev.y < 0:
                    game.camera.zoom_at(mx, my, game.camera.zoom / ZOOM_STEP)

            elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                mx, my = ev.pos
                if game.modal_open:
                    rect = modal_rect()
                    if rect.collidepoint(mx, my):
                        tab_y = rect.y + 48
                        tab_x = rect.x + 16
                        tab_w = 190
                        tab_h = 34
                        gap = 10
                        tab_count = 4 if game.modal_kind == ModalKind.BOARD else 3
                        for idx in range(tab_count):
                            r = pygame.Rect(tab_x + idx * (tab_w + gap), tab_y, tab_w, tab_h)
                            if r.collidepoint(mx, my):
                                if game.modal_kind == ModalKind.BUILDING:
                                    game.building_tab = [BuildingTab.PEOPLE, BuildingTab.STOCK, BuildingTab.TASK][idx]
                                elif game.modal_kind == ModalKind.NPC:
                                    game.npc_tab = [NPCTab.TRAITS, NPCTab.STATUS, NPCTab.INVENTORY][idx]
                                elif game.modal_kind == ModalKind.BOARD:
                                    game.board_tab = [BoardTab.ENTITIES, BoardTab.CELLS, BoardTab.INVENTORY, BoardTab.EXPLORE][idx]
                                break

                        if game.modal_kind == ModalKind.BOARD and game.board_tab == BoardTab.EXPLORE:
                            body = pygame.Rect(rect.x + 16, rect.y + 90, rect.w - 32, rect.h - 110)
                            btn_y = body.y + 90
                            btn_w = 160
                            btn_h = 42
                            gap = 14
                            for idx, ticks in enumerate((6, 12, 18)):
                                bx = body.x + 12 + idx * (btn_w + gap)
                                r = pygame.Rect(bx, btn_y, btn_w, btn_h)
                                if r.collidepoint(mx, my):
                                    game.set_explore_duration_ticks(ticks)
                                    break
                        continue

                if minimap_rect.collidepoint(mx, my):
                    wx, wy = minimap_click_to_world((mx, my), minimap_rect)
                    game.camera.center_on_world(wx, wy)
                else:
                    ni = game.pick_npc_at_screen(mx, my)
                    if ni is not None:
                        game.selection_type = SelectionType.NPC
                        game.selected_npc = ni
                        game.selected_building = None
                        continue
                    if game.pick_guild_board_at_screen(mx, my):
                        game.selection_type = SelectionType.BOARD
                        game.selected_npc = None
                        game.selected_building = None
                        continue
                    bn = game.pick_building_at_screen(mx, my)
                    if bn is not None:
                        game.selection_type = SelectionType.BUILDING
                        game.selected_building = bn
                        game.selected_npc = None
                        continue
                    game.selection_type = SelectionType.NONE
                    game.selected_npc = None
                    game.selected_building = None

            elif ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:
                    game.modal_open = False
                    game.modal_kind = ModalKind.NONE
                elif ev.key == pygame.K_i:
                    # open modal based on current selection
                    if game.selection_type == SelectionType.NPC and game.selected_npc is not None:
                        game.modal_open = not game.modal_open
                        game.modal_kind = ModalKind.NPC if game.modal_open else ModalKind.NONE
                    elif game.selection_type == SelectionType.BUILDING and game.selected_building is not None:
                        game.modal_open = not game.modal_open
                        game.modal_kind = ModalKind.BUILDING if game.modal_open else ModalKind.NONE
                    elif game.selection_type == SelectionType.BOARD:
                        game.modal_open = not game.modal_open
                        game.modal_kind = ModalKind.BOARD if game.modal_open else ModalKind.NONE

                # tab hotkeys
                elif ev.key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4) and game.modal_open:
                    if game.modal_kind == ModalKind.BUILDING:
                        game.building_tab = [BuildingTab.PEOPLE, BuildingTab.STOCK, BuildingTab.TASK][int(ev.unicode) - 1]
                    elif game.modal_kind == ModalKind.NPC:
                        game.npc_tab = [NPCTab.TRAITS, NPCTab.STATUS, NPCTab.INVENTORY][int(ev.unicode) - 1]
                    elif game.modal_kind == ModalKind.BOARD:
                        game.board_tab = [BoardTab.ENTITIES, BoardTab.CELLS, BoardTab.INVENTORY, BoardTab.EXPLORE][int(ev.unicode) - 1]


        # camera movement (disabled while modal open? keep enabled)
        keys = pygame.key.get_pressed()
        dx = dy = 0.0
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            dx -= 1
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            dx += 1
        if keys[pygame.K_w] or keys[pygame.K_UP]:
            dy -= 1
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:
            dy += 1
        if dx != 0 or dy != 0:
            mag = (dx * dx + dy * dy) ** 0.5
            dx /= mag
            dy /= mag
            game.camera.x += dx * CAMERA_SPEED * dt
            game.camera.y += dy * CAMERA_SPEED * dt
            game.camera.clamp_to_world()

        # --- sim ---
        while sim_acc_ms >= SIM_TICK_MS:
            sim_acc_ms -= SIM_TICK_MS
            game.sim_tick()

        game.update_movement(dt)

        # --- render ---
        draw_world(screen, game, small)
        minimap_rect = draw_minimap(screen, game, small)
        draw_hud(screen, game, font, small)

        # modal
        if game.modal_open:
            if game.modal_kind == ModalKind.BUILDING:
                draw_building_modal(screen, game, font, small)
            elif game.modal_kind == ModalKind.NPC:
                draw_npc_modal(screen, game, font, small)
            elif game.modal_kind == ModalKind.BOARD:
                draw_board_modal(screen, game, font, small)

        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
