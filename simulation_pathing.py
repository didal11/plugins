#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

from collections import deque
from typing import List, Set, Tuple


def neighbors(
    x: int,
    y: int,
    width_tiles: int,
    height_tiles: int,
    blocked_tiles: Set[Tuple[int, int]],
) -> List[Tuple[int, int]]:
    out: List[Tuple[int, int]] = []
    for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
        if nx < 0 or ny < 0 or nx >= width_tiles or ny >= height_tiles:
            continue
        if (nx, ny) in blocked_tiles:
            continue
        out.append((nx, ny))
    return out


def wavefront_distances(
    targets: List[Tuple[int, int]],
    width_tiles: int,
    height_tiles: int,
    blocked_tiles: Set[Tuple[int, int]],
) -> List[List[int]]:
    inf = 10**9
    distances = [[inf for _ in range(width_tiles)] for _ in range(height_tiles)]
    q: deque[Tuple[int, int]] = deque()

    for tx, ty in targets:
        if tx < 0 or ty < 0 or tx >= width_tiles or ty >= height_tiles:
            continue
        if (tx, ty) in blocked_tiles:
            continue
        if distances[ty][tx] == 0:
            continue
        distances[ty][tx] = 0
        q.append((tx, ty))

    while q:
        x, y = q.popleft()
        next_dist = distances[y][x] + 1
        for nx, ny in neighbors(x, y, width_tiles, height_tiles, blocked_tiles):
            if next_dist >= distances[ny][nx]:
                continue
            distances[ny][nx] = next_dist
            q.append((nx, ny))
    return distances


def find_path_to_nearest_target(
    start: Tuple[int, int],
    targets: List[Tuple[int, int]],
    width_tiles: int,
    height_tiles: int,
    blocked_tiles: Set[Tuple[int, int]],
) -> List[Tuple[int, int]]:
    if not targets or start in targets:
        return []
    distances = wavefront_distances(targets, width_tiles, height_tiles, blocked_tiles)
    sx, sy = start
    if sy < 0 or sx < 0 or sy >= len(distances) or sx >= len(distances[0]):
        return []
    if distances[sy][sx] >= 10**9:
        return []

    path: List[Tuple[int, int]] = []
    cx, cy = sx, sy
    while distances[cy][cx] > 0:
        best_next: Tuple[int, int] | None = None
        best_dist = distances[cy][cx]
        for nx, ny in neighbors(cx, cy, width_tiles, height_tiles, blocked_tiles):
            nb_dist = distances[ny][nx]
            if nb_dist > best_dist:
                continue
            if nb_dist < best_dist or best_next is None or (ny, nx) < (best_next[1], best_next[0]):
                best_dist = nb_dist
                best_next = (nx, ny)
        if best_next is None:
            return []
        path.append(best_next)
        cx, cy = best_next
    return path


def batch_next_steps_by_wavefront(
    starts: List[Tuple[int, int]],
    targets: List[Tuple[int, int]],
    width_tiles: int,
    height_tiles: int,
    blocked_tiles: Set[Tuple[int, int]],
) -> List[Tuple[int, int] | None]:
    if not starts:
        return []

    distances = wavefront_distances(targets, width_tiles, height_tiles, blocked_tiles)
    out: List[Tuple[int, int] | None] = []
    for x, y in starts:
        best_next: Tuple[int, int] | None = None
        best_dist = distances[y][x] if 0 <= x < width_tiles and 0 <= y < height_tiles else 10**9
        for nx, ny in neighbors(x, y, width_tiles, height_tiles, blocked_tiles):
            nb_dist = distances[ny][nx]
            if nb_dist > best_dist:
                continue
            if nb_dist < best_dist or best_next is None or (ny, nx) < (best_next[1], best_next[0]):
                best_dist = nb_dist
                best_next = (nx, ny)
        out.append(best_next)
    return out
