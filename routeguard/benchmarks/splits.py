"""Seeded, stratified, group-aware train / calibration / test splits.

Translations of one item (same ``parallel_id``) are always assigned to the same
split. Otherwise a learned router could see the English version of a question
during training and the Kazakh version at test time, which would inflate
cross-lingual results.
"""

from __future__ import annotations

import random
from collections import defaultdict
from dataclasses import dataclass

from routeguard.benchmarks.schema import Item
from routeguard.config import SplitConfig
from routeguard.utils.seeding import derive_seed


@dataclass
class Splits:
    train: list[Item]
    calibration: list[Item]
    test: list[Item]

    def check_disjoint(self) -> None:
        ids = [{i.id for i in s} for s in (self.train, self.calibration, self.test)]
        groups = [
            {i.parallel_id or i.id for i in s} for s in (self.train, self.calibration, self.test)
        ]
        for a in range(3):
            for b in range(a + 1, 3):
                if ids[a] & ids[b] or groups[a] & groups[b]:
                    raise AssertionError("Split leakage: overlapping items or parallel groups")


def make_splits(items: list[Item], cfg: SplitConfig, seed: int) -> Splits:
    groups: dict[str, list[Item]] = defaultdict(list)
    for it in items:
        groups[it.parallel_id or it.id].append(it)

    strata: dict[tuple[str, ...], list[str]] = defaultdict(list)
    for gid, members in groups.items():
        first = members[0]
        key = tuple(str(getattr(first, k, None) or first.metadata.get(k)) for k in cfg.stratify_by)
        strata[key].append(gid)

    train: list[Item] = []
    calib: list[Item] = []
    test: list[Item] = []
    for key in sorted(strata):
        gids = sorted(strata[key])
        random.Random(derive_seed("split", seed, *key)).shuffle(gids)
        n = len(gids)
        n_train = round(n * cfg.train)
        n_calib = round(n * cfg.calibration)
        if n >= 3 and cfg.test > 0 and n_train + n_calib >= n:
            n_train = max(0, n - n_calib - 1)  # keep at least one test group per stratum
        for i, gid in enumerate(gids):
            target = train if i < n_train else calib if i < n_train + n_calib else test
            target.extend(groups[gid])
    splits = Splits(train, calib, test)
    splits.check_disjoint()
    return splits
