# SPDX-License-Identifier: MIT
# Route Strategy – determines the order in which targets are attempted.

import logging
import random
from typing import List

from proxy_app.schemas_virtual import RouteTarget, VirtualModelConfig

logger = logging.getLogger("proxy_app.virtual_models")


def resolve_targets(config: VirtualModelConfig) -> List[RouteTarget]:
    """
    Given a VirtualModelConfig, return an ordered list of targets to try.

    The order depends on ``config.strategy``:

    * **sequential** – use the order defined in config (stable).
    * **primary_backup** – first target is always tried first; remaining are
      shuffled so backup load is distributed.
    * **weighted_random** – targets are shuffled with probability proportional
      to their weight.
    * **balanced** – alias of weighted_random for equal-load semantics (uses
      weight when provided, equal chance when weights are equal).

    Only *enabled* targets are returned.  If ``max_target_attempts`` is set,
    the list is truncated to that length.
    """
    targets = config.enabled_targets
    if not targets:
        return []

    strategy = config.strategy

    if strategy == "sequential":
        ordered = list(targets)

    elif strategy == "primary_backup":
        if len(targets) <= 1:
            ordered = list(targets)
        else:
            primary = targets[0]
            backups = list(targets[1:])
            random.shuffle(backups)
            ordered = [primary] + backups

    elif strategy in {"weighted_random", "balanced"}:
        # Weighted shuffle: repeatedly pick from remaining pool proportional to weight
        pool = list(targets)
        ordered = []
        while pool:
            total = sum(t.weight for t in pool)
            r = random.uniform(0, total)
            cumulative = 0.0
            for i, t in enumerate(pool):
                cumulative += t.weight
                if cumulative >= r:
                    ordered.append(pool.pop(i))
                    break

    else:
        # Fallback – should not happen due to schema validation
        logger.warning(
            f"Unknown strategy '{strategy}', falling back to sequential"
        )
        ordered = list(targets)

    # Optionally truncate
    if config.max_target_attempts is not None:
        ordered = ordered[: config.max_target_attempts]

    return ordered
