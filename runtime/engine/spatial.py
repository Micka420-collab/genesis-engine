"""Uniform spatial hash grid for O(N) average-case neighbour lookups."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

import numpy as np


@dataclass
class SpatialGrid:
    cell_size_m: float
    cells: Dict[Tuple[int, int], List[int]] = field(default_factory=dict)
    n_indexed: int = 0

    def clear(self) -> None:
        self.cells.clear()
        self.n_indexed = 0

    def rebuild(self, pos_xy: np.ndarray, alive: np.ndarray) -> None:
        self.clear()
        if pos_xy.shape[0] == 0:
            return
        cs = self.cell_size_m
        live_idx = np.flatnonzero(alive)
        if live_idx.size == 0:
            return
        gx = np.floor(pos_xy[live_idx, 0] / cs).astype(np.int32)
        gy = np.floor(pos_xy[live_idx, 1] / cs).astype(np.int32)
        for k, row in enumerate(live_idx):
            key = (int(gx[k]), int(gy[k]))
            bucket = self.cells.get(key)
            if bucket is None:
                self.cells[key] = [int(row)]
            else:
                bucket.append(int(row))
        self.n_indexed = int(live_idx.size)

    def query_disk(self, x: float, y: float, r_m: float,
                   exclude_row: int = -1) -> List[int]:
        cs = self.cell_size_m
        r_cells = int(math.ceil(r_m / cs))
        cx = int(math.floor(x / cs))
        cy = int(math.floor(y / cs))
        out: List[int] = []
        for dy in range(-r_cells, r_cells + 1):
            for dx in range(-r_cells, r_cells + 1):
                bucket = self.cells.get((cx + dx, cy + dy))
                if bucket is None:
                    continue
                if exclude_row >= 0:
                    for row in bucket:
                        if row != exclude_row:
                            out.append(row)
                else:
                    out.extend(bucket)
        return out

    def find_target_collisions(self, target_xy: np.ndarray, action: np.ndarray,
                                alive: np.ndarray,
                                resource_actions: Tuple[int, ...]) -> List[Tuple[int, int]]:
        cs = self.cell_size_m
        buckets: Dict[Tuple[int, int], List[int]] = {}
        act_set = set(int(a) for a in resource_actions)
        live = np.flatnonzero(alive)
        if live.size == 0:
            return []
        for row in live:
            row_i = int(row)
            if int(action[row_i]) not in act_set:
                continue
            gx = int(math.floor(target_xy[row_i, 0] / cs))
            gy = int(math.floor(target_xy[row_i, 1] / cs))
            buckets.setdefault((gx, gy), []).append(row_i)
        pairs: List[Tuple[int, int]] = []
        for _key, rows in buckets.items():
            if len(rows) < 2:
                continue
            limit = min(len(rows), 4)
            for i in range(limit):
                for j in range(i + 1, limit):
                    pairs.append((rows[i], rows[j]))
        return pairs
