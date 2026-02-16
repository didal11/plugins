#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Game configuration.

규칙: 이 파일에는 '상수/설정'만 둡니다. (로직 금지)
"""

# --- World ---
BASE_TILE_SIZE = 16
GRID_W, GRID_H = 400, 300

# --- Window ---
SCREEN_W, SCREEN_H = 1280, 720
FPS = 60

# --- Simulation ---
SIM_TICK_MS = 100            # 1시뮬 틱(=1분) 당 현실시간(ms)
SIM_TICK_MINUTES = 1         # 1시뮬 틱의 게임 시간(분)
NPC_SPEED = 220.0          # px/s
CAMERA_SPEED = 1100.0      # px/s (카메라 이동)

# --- Zoom ---
ZOOM_MIN = 0.40
ZOOM_MAX = 3.00
ZOOM_STEP = 1.12

# --- Minimap ---
MINIMAP_W, MINIMAP_H = 260, 190
MINIMAP_PAD = 10

# --- Modals ---
MODAL_W, MODAL_H = 820, 500
