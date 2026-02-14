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
from typing import Dict, List, Optional, Tuple

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


# ============================================================
# Time
# ============================================================
class TimeSystem:
    HOURS_PER_DAY = 24
    DAYS_PER_MONTH = 30
    MONTHS_PER_YEAR = 12

    def __init__(self):
        self.total_hours = 0

    def advance(self, hours: int = 1) -> None:
        self.total_hours += hours

    @property
    def hour(self) -> int:
        return self.total_hours % self.HOURS_PER_DAY

    @property
    def _total_days(self) -> int:
        return self.total_hours // self.HOURS_PER_DAY

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
        return f"{self.year}년 {self.month}월 {self.day}일 {self.hour:02d}:00"


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

    def _nearest_entity(self, kind: str, tx: int, ty: int) -> Optional[Dict[str, object]]:
        candidates = [e for e in self.entities if str(e.get("type", "")).strip() == kind]
        if kind == "resource":
            candidates = [e for e in candidates if int(e.get("stock", 0)) > 0]
        if not candidates:
            return None
        return min(candidates, key=lambda e: abs(tx - int(e.get("x", 0))) + abs(ty - int(e.get("y", 0))))

    def _gather_from_resource(self, npc: NPC, item_key: str, amount: int) -> Optional[str]:
        tx, ty = world_px_to_tile(npc.x, npc.y)
        node = self._nearest_entity("resource", tx, ty)
        if node is None:
            return None
        stock = int(node.get("stock", 0))
        got = min(max(0, amount), stock)
        if got <= 0:
            return None
        node["stock"] = stock - got
        npc.inventory[item_key] = int(npc.inventory.get(item_key, 0)) + got
        return f"{node.get('name', '자원지')}[{int(node.get('x', 0))},{int(node.get('y', 0))}] {item_key}+{got}"

    def _use_workbench(self, npc: NPC, station_keyword: str, src_item: str, dst_item: str, cost: int, out: int) -> Optional[str]:
        tx, ty = world_px_to_tile(npc.x, npc.y)
        bench = self._nearest_entity("workbench", tx, ty)
        if bench is None:
            return None
        bench_name = str(bench.get("name", "작업대"))
        if station_keyword not in bench_name:
            return None
        have = int(npc.inventory.get(src_item, 0))
        if have < cost:
            return f"{bench_name} 재료부족({src_item})"
        npc.inventory[src_item] = have - cost
        if npc.inventory[src_item] <= 0:
            npc.inventory.pop(src_item, None)
        npc.inventory[dst_item] = int(npc.inventory.get(dst_item, 0)) + out
        return f"{bench_name}[{int(bench.get('x', 0))},{int(bench.get('y', 0))}] {src_item}-{cost}->{dst_item}+{out}"

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
                target_building=None,
                location_building=home if not hostile else None,
                inventory={},
                target_outside_tile=None,
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

    def npc_passive_1h(self, npc: NPC) -> None:
        s = npc.status
        s.hunger += int(self.sim_settings.get("hunger_gain_per_hour", 5.0))
        s.fatigue += int(self.sim_settings.get("fatigue_gain_per_hour", 4.0))
        if s.hunger >= 80:
            s.happiness -= 3
        if s.fatigue >= 80:
            s.happiness -= 3
        self._status_clamp(npc)

    def _scheduled_destination(self, npc: NPC) -> Optional[Tuple[str, Optional[Building], Optional[Tuple[int, int]]]]:
        activity = self.planner.activity_for_hour(self.time.hour)
        if activity == ScheduledActivity.MEAL:
            npc.status.current_action = "식사"
            return ("eat", self.building_by_name.get("식당"), None)
        if activity == ScheduledActivity.SLEEP:
            npc.status.current_action = "취침"
            return ("rest", npc.home_building, None)
        return None

    def _workplace_for_job(self, job: JobType) -> Optional[Building]:
        if job == JobType.ADVENTURER:
            return None
        if job == JobType.FARMER:
            return self.building_by_name["농장"]
        if job == JobType.FISHER:
            return self.building_by_name["낚시터"]
        if job == JobType.BLACKSMITH:
            return self.building_by_name["대장간"]
        if job == JobType.PHARMACIST:
            return self.building_by_name["약국"]
        return None

    def _profit_place_for_job(self, job: JobType) -> Building:
        if job == JobType.ADVENTURER:
            return self.building_by_name["모험가 길드"]
        if job in (JobType.FARMER, JobType.FISHER):
            return self.building_by_name["잡화점"]
        if job == JobType.BLACKSMITH:
            return self.building_by_name["대장간"]
        if job == JobType.PHARMACIST:
            return self.building_by_name["약국"]
        return self.building_by_name["잡화점"]

    def _set_target_building(self, npc: NPC, b: Building) -> None:
        npc.target_building = b
        npc.target_outside_tile = None
        npc.path = manhattan_path(world_px_to_tile(npc.x, npc.y), b.random_tile_inside(self.rng))

    def _set_target_outside(self, npc: NPC, tile: Tuple[int, int]) -> None:
        npc.target_building = None
        npc.target_outside_tile = tile
        npc.path = manhattan_path(world_px_to_tile(npc.x, npc.y), tile)


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
            npc.target_building = None
            npc.target_outside_tile = None
            npc.status.current_action = "사망"
            return

        if self._is_hostile(npc):
            npc.status.current_action = "배회"
            self._set_target_outside(npc, self.random_outside_tile())
            return

        override = self._scheduled_destination(npc)
        if override is not None:
            _, b, out_tile = override
            if b is not None:
                self._set_target_building(npc, b)
                return
            if out_tile is not None:
                self._set_target_outside(npc, out_tile)
                return

        job = npc.traits.job
        activity = self.planner.activity_for_hour(self.time.hour)
        if activity == ScheduledActivity.WORK:
            if job == JobType.ADVENTURER:
                hostile = self._nearest_hostile(npc)
                if hostile is not None:
                    self._set_target_outside(npc, world_px_to_tile(hostile.x, hostile.y))
                else:
                    self._set_target_outside(npc, self.random_outside_tile())
            else:
                wp = self._workplace_for_job(job)
                self._set_target_building(npc, wp if wp is not None else npc.home_building)
            return

        self._set_target_building(npc, npc.home_building)

    def _required_tool_keys(self, action: Dict[str, object]) -> List[str]:
        raw = action.get("required_tools", []) if isinstance(action.get("required_tools", []), list) else []
        keys: List[str] = []
        for t in raw:
            txt = str(t).strip()
            if not txt:
                continue
            if txt in self.items:
                keys.append(txt)
                continue
            if txt in self.item_display_to_key:
                keys.append(self.item_display_to_key[txt])
        return keys

    def _do_eat_at_restaurant(self, npc: NPC) -> str:
        s = npc.status
        st = self.bstate["식당"]
        fee = 12
        if s.money < fee:
            s.happiness -= 3
            s.hunger += 3
            self._status_clamp(npc)
            st.last_event = f"{npc.traits.name} 돈 부족"
            return f"{npc.traits.name}: 식당(돈없음)"
        s.money -= fee
        before = s.hunger
        s.hunger -= int(self.sim_settings.get("meal_hunger_restore", 38.0))
        s.happiness += 3
        s.fatigue += 1
        self._status_clamp(npc)
        # 재고 소모
        for k in ["bread", "meat", "fish"]:
            if st.inventory.get(k, 0) > 0 and self.rng.random() < 0.6:
                st.inventory[k] -= 1
                if st.inventory[k] <= 0:
                    del st.inventory[k]
                break
        st.task = "조리/서빙"
        st.task_progress = (st.task_progress + 15) % 101
        st.last_event = f"{npc.traits.name} 식사"
        npc.status.current_action = "식사"
        return f"{npc.traits.name}: 식사 허기 {before}->{s.hunger}"

    def _do_rest_at_home(self, npc: NPC) -> str:
        s = npc.status
        before = s.fatigue
        s.fatigue -= int(self.sim_settings.get("rest_fatigue_restore", 28.0))
        s.hunger += 6
        s.happiness += 2
        self._status_clamp(npc)
        st = self.bstate[npc.home_building.name]
        st.last_event = f"{npc.traits.name} 휴식"
        npc.status.current_action = "취침"
        return f"{npc.traits.name}: 휴식 피로 {before}->{s.fatigue}"

    def _primary_action(self, npc: NPC) -> str:
        job_name = npc.traits.job.value
        actions = self.job_work_actions.get(job_name, [])
        if not actions:
            return f"{npc.traits.name}: 작업(정의 없음)"

        s = npc.status
        if s.active_work_action and s.action_hours_left > 0 and s.active_work_action in actions:
            action_name = s.active_work_action
        else:
            action_name = self.rng.choice(actions)
        action = self.action_defs.get(action_name, {})
        if not isinstance(action, dict):
            return f"{npc.traits.name}: 작업 정의 오류({action_name})"

        duration = max(1, int(action.get("duration_hours", 1)))
        if s.active_work_action != action_name or s.action_hours_left <= 0:
            s.active_work_action = action_name
            s.action_total_hours = duration
            s.action_hours_left = duration

        tool_keys = self._required_tool_keys(action)
        missing = [k for k in tool_keys if int(npc.inventory.get(k, 0)) <= 0]
        if missing:
            s.current_action = f"{action_name}(도구없음)"
            s.active_work_action = ""
            s.action_hours_left = 0
            s.action_total_hours = 0
            display_missing = [self.items[k].display if k in self.items else k for k in missing]
            return f"{npc.traits.name}: {action_name} 실패(필요 도구 없음: {', '.join(display_missing)})"

        outputs = action.get("outputs", {}) if isinstance(action.get("outputs", {}), dict) else {}

        s.fatigue += int(action.get("fatigue", 12))
        s.hunger += int(action.get("hunger", 8))
        s.happiness -= 1
        self._status_clamp(npc)

        s.current_action = action_name
        s.action_hours_left = max(0, s.action_hours_left - 1)
        if s.action_hours_left > 0:
            done = s.action_total_hours - s.action_hours_left
            return f"{npc.traits.name}: {action_name} 진행중({done}/{s.action_total_hours}h)"

        gained_parts: List[str] = []
        valid_items = set(self.items.keys())
        for item, spec in outputs.items():
            if str(item) not in valid_items:
                continue
            qty = 0
            if isinstance(spec, int):
                qty = max(0, int(spec))
            elif isinstance(spec, dict):
                lo = int(spec.get("min", 0))
                hi = int(spec.get("max", lo))
                if hi < lo:
                    lo, hi = hi, lo
                qty = self.rng.randint(max(0, lo), max(0, hi))
            if qty <= 0:
                continue
            npc.inventory[str(item)] = int(npc.inventory.get(str(item), 0)) + qty
            gained_parts.append(f"{item}+{qty}")

        s.active_work_action = ""
        s.action_hours_left = 0
        s.action_total_hours = 0

        worksite = self._workplace_for_job(npc.traits.job)
        if worksite is not None and worksite.name in self.bstate:
            bst = self.bstate[worksite.name]
            bst.task = action_name
            bst.task_progress = (bst.task_progress + self.rng.randint(15, 35)) % 101
            bst.last_event = f"{npc.traits.name} {action_name}"

        tools = [self.items[k].display if k in self.items else k for k in tool_keys]
        tool_text = f" 도구:{', '.join(tools)}" if tools else ""
        gained_text = ", ".join(gained_parts) if gained_parts else "획득 없음"
        npc.status.current_action = action_name
        return f"{npc.traits.name}: {action_name}({gained_text}){tool_text}"

    def _profit_action(self, npc: NPC) -> str:
        job = npc.traits.job
        s = npc.status

        if job == JobType.ADVENTURER:
            guild = self.bstate["모험가 길드"]
            moved = 0
            earned = 0
            price = {"meat": 10, "wood": 8, "ore": 12, "potion": 16}
            for k in ["meat", "wood", "ore", "potion"]:
                q = int(npc.inventory.get(k, 0))
                if q <= 0:
                    continue
                take = min(q, 2)
                npc.inventory[k] = q - take
                if npc.inventory[k] <= 0:
                    npc.inventory.pop(k, None)
                guild.inventory[k] = int(guild.inventory.get(k, 0)) + take
                moved += take
                earned += price.get(k, 5) * take
            if moved == 0:
                s.happiness -= 1
                self._status_clamp(npc)
                guild.last_event = f"{npc.traits.name} 납품(없음)"
                return f"{npc.traits.name}: 길드 납품(없음)"
            s.money += earned
            s.happiness += 2
            self._status_clamp(npc)
            guild.task_progress = (guild.task_progress + 12) % 101
            guild.last_event = f"{npc.traits.name} 납품({moved}) +{earned}G"
            return f"{npc.traits.name}: 길드 납품({moved}) +{earned}G"

        if job in (JobType.FARMER, JobType.FISHER):
            shop = self.bstate["잡화점"]
            item = "bread" if job == JobType.FARMER else "fish"
            unit = 6 if job == JobType.FARMER else 7
            q = int(npc.inventory.get(item, 0))
            if q <= 0:
                s.happiness -= 1
                self._status_clamp(npc)
                shop.last_event = f"{npc.traits.name} 판매(없음)"
                return f"{npc.traits.name}: 잡화점 판매(없음)"
            sell = min(q, 3)
            npc.inventory[item] = q - sell
            if npc.inventory[item] <= 0:
                npc.inventory.pop(item, None)
            shop.inventory[item] = int(shop.inventory.get(item, 0)) + sell
            gained = unit * sell
            s.money += gained
            s.happiness += 1
            self._status_clamp(npc)
            shop.task_progress = (shop.task_progress + 10) % 101
            shop.last_event = f"{npc.traits.name} 판매({item} {sell}) +{gained}G"
            return f"{npc.traits.name}: 잡화점 판매(+{gained}G)"

        if job == JobType.BLACKSMITH:
            smith = self.bstate["대장간"]
            item = "ore"
            unit = 12
            q = int(npc.inventory.get(item, 0))
            if q <= 0:
                s.happiness -= 1
                self._status_clamp(npc)
                smith.last_event = f"{npc.traits.name} 판매(없음)"
                return f"{npc.traits.name}: 대장간 판매(없음)"
            sell = min(q, 2)
            npc.inventory[item] = q - sell
            if npc.inventory[item] <= 0:
                npc.inventory.pop(item, None)
            smith.inventory[item] = int(smith.inventory.get(item, 0)) + sell
            gained = unit * sell
            s.money += gained
            s.happiness += 1
            self._status_clamp(npc)
            smith.task_progress = (smith.task_progress + 10) % 101
            smith.last_event = f"{npc.traits.name} 판매({sell}) +{gained}G"
            return f"{npc.traits.name}: 대장간 판매(+{gained}G)"

        if job == JobType.PHARMACIST:
            pharm = self.bstate["약국"]
            item = "potion"
            unit = 18
            q = int(npc.inventory.get(item, 0))
            if q <= 0:
                s.happiness -= 1
                self._status_clamp(npc)
                pharm.last_event = f"{npc.traits.name} 판매(없음)"
                return f"{npc.traits.name}: 약국 판매(없음)"
            sell = min(q, 2)
            npc.inventory[item] = q - sell
            if npc.inventory[item] <= 0:
                npc.inventory.pop(item, None)
            pharm.inventory[item] = int(pharm.inventory.get(item, 0)) + sell
            gained = unit * sell
            s.money += gained
            s.happiness += 1
            self._status_clamp(npc)
            pharm.task_progress = (pharm.task_progress + 10) % 101
            pharm.last_event = f"{npc.traits.name} 판매({sell}) +{gained}G"
            return f"{npc.traits.name}: 약국 판매(+{gained}G)"

        return f"{npc.traits.name}: 수익창출(대기)"

    # -----------------------------
    # Tick + movement
    # -----------------------------
    def sim_tick_1hour(self) -> None:
        self.time.advance(1)
        for npc in self.npcs:
            if npc.status.hp > 0:
                self.npc_passive_1h(npc)

        self.logs.extend(resolve_combat_round(self.npcs, self.combat_settings, self.rng))
        eco_logs: List[str] = []
        self.last_economy_snapshot = self.economy.run_hour(self.npcs, self.bstate, eco_logs)
        self.logs.extend(eco_logs[-4:])

        for npc in self.npcs:
            if npc.status.hp <= 0:
                continue
            tx, ty = world_px_to_tile(npc.x, npc.y)
            npc.location_building = self.find_building_by_tile(tx, ty)

            if len(npc.path) == 0:
                override = self._scheduled_destination(npc)
                if override is not None:
                    kind, b, _ = override
                    if kind == "eat" and b is not None and b.name == "식당":
                        self.logs.append(self._do_eat_at_restaurant(npc))
                        self._plan_next_target(npc)
                        continue
                    if kind == "rest" and b is not None and b.zone == ZoneType.RESIDENTIAL:
                        self.logs.append(self._do_rest_at_home(npc))
                        self._plan_next_target(npc)
                        continue

                if self._is_hostile(npc) and npc.target_outside_tile is not None:
                    if (tx, ty) == npc.target_outside_tile:
                        self.logs.append(f"{npc.traits.name}: 적대 배회")
                        self._plan_next_target(npc)
                        continue

                # adventurer outside arrival
                if npc.traits.job == JobType.ADVENTURER and self.planner.activity_for_hour(self.time.hour) == ScheduledActivity.WORK and npc.target_outside_tile is not None:
                    if (tx, ty) == npc.target_outside_tile or (abs(tx - npc.target_outside_tile[0]) + abs(ty - npc.target_outside_tile[1]) <= 1):
                        self.logs.append(self._primary_action(npc))
                        self._plan_next_target(npc)
                        continue

                if npc.target_building is not None and npc.location_building is not None and npc.location_building == npc.target_building:
                    if self.planner.activity_for_hour(self.time.hour) == ScheduledActivity.WORK:
                        self.logs.append(self._primary_action(npc))
                    self._plan_next_target(npc)
                else:
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
                continue
            step = float(self.sim_settings.get("npc_speed", 220.0)) * dt
            if step >= dist:
                npc.x, npc.y = float(gx), float(gy)
                npc.path.pop(0)
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
        if npc.target_building is not None:
            tgt = f"{npc.target_building.zone.value}/{npc.target_building.name}"
        elif npc.target_outside_tile is not None:
            tgt = f"{RegionType.OUTSIDE.value} 타일 {npc.target_outside_tile}"
        lines = [
            "스테이터스",
            "",
            f"현재 위치: {loc}",
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

    # world entities (workbench/resource)
    for ent in game.entities:
        ex = int(ent.get("x", 0)) * BASE_TILE_SIZE + BASE_TILE_SIZE // 2
        ey = int(ent.get("y", 0)) * BASE_TILE_SIZE + BASE_TILE_SIZE // 2
        et = str(ent.get("type", ""))
        sx, sy = cam.world_to_screen(ex, ey)
        if et == "resource":
            color = (110, 180, 90)
            rad = max(2, int(6 * cam.zoom))
            pygame.draw.circle(screen, color, (sx, sy), rad)
            pygame.draw.circle(screen, (0, 0, 0), (sx, sy), rad, 1)
            if cam.zoom >= 1.0:
                label = f"{ent.get('name', '자원')}({int(ent.get('stock', 0))})"
                screen.blit(small.render(label, True, (210, 230, 210)), (sx + 6, sy - 8))
        elif et == "workbench":
            rw = max(4, int(10 * cam.zoom))
            rh = max(4, int(8 * cam.zoom))
            rect = pygame.Rect(sx - rw // 2, sy - rh // 2, rw, rh)
            pygame.draw.rect(screen, (180, 140, 80), rect)
            pygame.draw.rect(screen, (0, 0, 0), rect, 1)
            if cam.zoom >= 1.0:
                screen.blit(small.render(str(ent.get("name", "작업대")), True, (230, 210, 180)), (sx + 6, sy - 8))

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
    else:
        lines = [
            "NPC 또는 건물을 클릭하세요.",
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
                        for idx in range(3):
                            r = pygame.Rect(tab_x + idx * (tab_w + gap), tab_y, tab_w, tab_h)
                            if r.collidepoint(mx, my):
                                if game.modal_kind == ModalKind.BUILDING:
                                    game.building_tab = [BuildingTab.PEOPLE, BuildingTab.STOCK, BuildingTab.TASK][idx]
                                elif game.modal_kind == ModalKind.NPC:
                                    game.npc_tab = [NPCTab.TRAITS, NPCTab.STATUS, NPCTab.INVENTORY][idx]
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

                # tab hotkeys
                elif ev.key in (pygame.K_1, pygame.K_2, pygame.K_3) and game.modal_open:
                    if game.modal_kind == ModalKind.BUILDING:
                        game.building_tab = [BuildingTab.PEOPLE, BuildingTab.STOCK, BuildingTab.TASK][int(ev.unicode) - 1]
                    elif game.modal_kind == ModalKind.NPC:
                        game.npc_tab = [NPCTab.TRAITS, NPCTab.STATUS, NPCTab.INVENTORY][int(ev.unicode) - 1]


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
            game.sim_tick_1hour()

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

        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
