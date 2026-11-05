"""Named skill progression trees.

Each tree is just a name plus a root exercise slug - the actual steps
come from following that exercise's own harder_variation chain, the
same links the session page already offers as "harder" swaps, so
there's no separate curated structure to keep in sync with the
exercise library.
"""

from .models import Exercise

SKILL_TREES = [
    ("handstand", "Handstand", "wall-handstand-hold"),
    ("handstand_push_up", "Handstand push-up", "pike-push-up"),
    ("front_lever", "Front lever", "front-lever-tuck"),
    ("muscle_up", "Muscle-up", "scapular-pull-up"),
    ("planche", "Planche", "planche-lean"),
    ("pistol_squat", "Pistol squat", "lunge"),
    ("l_sit", "L-sit", "plank"),
]


def _chain_from_root(root):
    chain = [root]
    current = root
    seen_ids = {root.id}
    while current.harder_variation_id and current.harder_variation_id not in seen_ids:
        current = current.harder_variation
        chain.append(current)
        seen_ids.add(current.id)
    return chain


def skill_trees(achieved_exercise_ids=frozenset()):
    """Every named tree that has a seeded root, each step flagged with
    whether it's in `achieved_exercise_ids` and which step is next.
    """
    roots_by_slug = {
        ex.slug: ex for ex in Exercise.objects.filter(slug__in=[slug for _, _, slug in SKILL_TREES])
    }

    trees = []
    for key, label, root_slug in SKILL_TREES:
        root = roots_by_slug.get(root_slug)
        if not root:
            continue
        chain = _chain_from_root(root)
        steps = [
            {"exercise": exercise, "achieved": exercise.id in achieved_exercise_ids}
            for exercise in chain
        ]
        next_step = next((s["exercise"] for s in steps if not s["achieved"]), None)
        trees.append({"key": key, "label": label, "steps": steps, "next_step": next_step})
    return trees
