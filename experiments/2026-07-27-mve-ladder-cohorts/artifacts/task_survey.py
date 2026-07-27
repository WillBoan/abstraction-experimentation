"""Shape survey: the 2026-07-25 screen leads, plus every two-halves-shaped task in arc1-train."""
from arc_lab.core.dataset import load_dataset

LEADS = ["28bf18c6","5614dbcf","7468f01a","9565186b","9f236235","a740d043","d9fac9be","f25fbde4"]
corpus = load_dataset("arc1-train")
tasks = {e.task.task_id: e.task for e in corpus.entries}

def shapes(t):
    return [(ex.input.shape, ex.output.shape) for ex in t.train]

def halves_shaped(t):
    """input is h x 2w and output h x w (or the vertical form) on EVERY train pair."""
    h = all(i.shape[0] == o.shape[0] and i.shape[1] == 2 * o.shape[1] for i, o in
            [(ex.input, ex.output) for ex in t.train])
    v = all(i.shape[1] == o.shape[1] and i.shape[0] == 2 * o.shape[0] for i, o in
            [(ex.input, ex.output) for ex in t.train])
    return "h" if h else ("v" if v else None)

print("== screen leads")
for tid in LEADS:
    t = tasks.get(tid)
    print(f"{tid}: {shapes(t) if t else 'MISSING'}")

print("\n== two-halves-shaped family (exact 2x, no separator)")
for tid, t in sorted(tasks.items()):
    k = halves_shaped(t)
    if k:
        pal_in = sorted({int(v) for ex in t.train for v in ex.input.array.ravel()})
        pal_out = sorted({int(v) for ex in t.train for v in ex.output.array.ravel()})
        novel = set(pal_out) - set(pal_in)
        print(f"{tid} [{k}] in={pal_in} out={pal_out} novel_out_colour={sorted(novel) or 'none'} n_train={len(t.train)}")
