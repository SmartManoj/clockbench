import json, re, math, ast
from collections import OrderedDict
from statistics import median

# --- Paths ---
ANSWERS_PATH = "input/answers_sample.json"
OUTPUTS_PATH = "output/output_sample.json"
COMBINED_OUT = "grading/grading_sample.json"

# --- Follow grading order ---
ORDER_BY = "answers"
STRICT_SAME_ORDER = False

# --- Load data ---
def load_ordered(path):
    with open(path, "r", encoding = "utf-8") as f:
        return json.load(f, object_pairs_hook = OrderedDict)

gt   = load_ordered(ANSWERS_PATH)
pred = load_ordered(OUTPUTS_PATH)
gt_keys = list(gt.keys())
pred_keys = list(pred.keys())

if STRICT_SAME_ORDER and gt_keys != pred_keys:
    raise ValueError("Ground-truth and outputs have different key order.")

ids = [k for k in (gt_keys if ORDER_BY == "answers" else pred_keys) if (k in gt and k in pred)]

# --- Parsing and comparison helpers ---
def parse_obj(v):
    if isinstance(v, dict):
        return v
    s = str(v).strip()
    if s.startswith("```"):
        s = re.sub(r"^```(?:json|javascript|js)?\s*|\s*```$", "", s, flags = re.I|re.S)
    m = re.search(r"\{.*\}", s, flags=re.S)
    if m:
        s = m.group(0)
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass
    s2 = re.sub(r",(\s*[}\]])", r"\1", s)
    s2 = re.sub(r'(?m)(?<=\{|,)\s*([A-Za-z_]\w*)\s*:', r'"\1":', s2)
    try:
        return json.loads(s2)
    except json.JSONDecodeError:
        pass
    s3 = re.sub(r'\btrue\b', 'True', s2, flags = re.I)
    s3 = re.sub(r'\bfalse\b', 'False', s3, flags = re.I)
    s3 = re.sub(r'\bnull\b', 'None', s3, flags = re.I)
    return ast.literal_eval(s3)

def is_num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)

def as_int_or_none(x):
    if is_num(x):
        return int(x)
    if isinstance(x, str):
        xs = x.strip()
        if re.fullmatch(r"-?\d+", xs):
            return int(xs)
    return None

def match_value(expected, got):
    # Strings case-insensitive comparison
    if isinstance(expected, str):
        return isinstance(got, str) and expected.strip().casefold() == str(got).strip().casefold()

    # Booleans exact comparison
    if isinstance(expected, (bool, type(None))):
        return expected == got

    # Numeric comparison
    if is_num(expected):
        gi = as_int_or_none(got)
        return gi is not None and gi == int(expected)

    # List comparison with inclusive range
    if isinstance(expected, list) and expected:
        if len(expected) == 2 and all(is_num(x) for x in expected):
            gi = as_int_or_none(got)
            if gi is None: return False
            lo, hi = int(expected[0]), int(expected[1])
            return lo <= gi <= hi
        choices = {int(x) for x in expected if is_num(x) or (isinstance(x,str) and re.fullmatch(r"-?\d+", x))}
        gi = as_int_or_none(got)
        return gi is not None and gi in choices

    # Alternatives comparison
    if isinstance(expected, dict) and expected:
        choice_set = set()
        for v in expected.values():
            if is_num(v):
                choice_set.add(int(v))
            elif isinstance(v, str) and re.fullmatch(r"-?\d+", v.strip()):
                choice_set.add(int(v.strip()))
            elif isinstance(v, list) and len(v)==2 and all(is_num(x) for x in v):
                lo, hi = int(v[0]), int(v[1])
                choice_set.update(range(lo, hi+1))
        gi = as_int_or_none(got)
        return gi is not None and (gi in choice_set) if choice_set else (expected == got)

    # Fallback
    return expected == got

# --- Mapping ---
FIELDS_BY_TASK = {
    "answer_time": ["valid", "hours", "minutes", "seconds", "date", "month", "weekday"],
    "answer_shift": ["valid", "hours", "minutes", "seconds"],
    "answer_angle": ["valid", "hours", "minutes", "seconds"],
    "answer_zone": ["valid", "hours", "minutes", "seconds"],
}

def normalize(ans, fields):
    out = {}
    for f in fields:
        out[f] = ans.get(f, None)
    return out

def compare_entry(gt_obj, pred_obj, fields):
    g, p = normalize(gt_obj, fields), normalize(pred_obj, fields)
    details = OrderedDict()
    details["valid"] = (g.get("valid"), p.get("valid"))

    # Validity comparison
    if g.get("valid") is not p.get("valid"):
        return False, {**details, "reason": "validity_mismatch"}

    if g.get("valid") is False:
        return True, details

    all_ok = True
    for f in fields:
        if f == "valid": 
            continue
        ok = match_value(g.get(f), p.get(f))
        details[f] = (g.get(f), p.get(f), ok)
        all_ok = all_ok and ok

    return all_ok, details

# --- Run comparison in preserved order ---
task_keys = ["answer_time", "answer_shift", "answer_angle", "answer_zone"]

combined = OrderedDict()
totals = {k: {"correct": 0, "total": 0} for k in task_keys}
micro_correct = 0
micro_total = 0

print(f"Total clocks: {len(ids)}")

for i, key in enumerate(ids, 1):
    combined[key] = OrderedDict()
    all_ok = True

    for task in task_keys:
        fields = FIELDS_BY_TASK[task]
        g = parse_obj(gt[key][task])
        p = parse_obj(pred[key][task])

        ok, details = compare_entry(g, p, fields)

        combined[key][task] = OrderedDict([
            ("expected", g),
            ("got", p),
            ("correct", ok),
            ("details", details),
        ])

        totals[task]["total"] += 1
        totals[task]["correct"] += int(ok)
        micro_total += len([f for f in fields if f != "valid"]) + 1 
        micro_correct += int(ok)
        all_ok = all_ok and ok

    marks = ", ".join(f"{t}:{'✓' if combined[key][t]['correct'] else '✗'}" for t in task_keys)
    print(f"[{i}/{len(ids)}] {key} -> {marks}", flush=True)

# --- Validity breakdown ---
BASE_TASK = "answer_time" if "answer_time" in task_keys else task_keys[0]

valid_total = sum(1 for k in ids if combined[k][BASE_TASK]["expected"].get("valid") is True)
invalid_total = sum(1 for k in ids if combined[k][BASE_TASK]["expected"].get("valid") is False)
total_correct_base = sum(1 for k in ids if combined[k][BASE_TASK]["correct"])
valid_correct = sum(1 for k in ids if (combined[k][BASE_TASK]["expected"].get("valid") is True and combined[k][BASE_TASK]["correct"]))
invalid_correct = sum(1 for k in ids if (combined[k][BASE_TASK]["expected"].get("valid") is False and combined[k][BASE_TASK]["correct"]))

def pct(n, d):
    return None if d == 0 else round(n / d, 4)

validity_breakdown = OrderedDict([
    ("task", BASE_TASK),
    ("total_items", len(ids)),
    ("total_correct", total_correct_base),
    ("valid", OrderedDict([
        ("correct", valid_correct),
        ("total",   valid_total),
        ("accuracy", pct(valid_correct, valid_total)),
    ])),
    ("invalid", OrderedDict([
        ("correct", invalid_correct),
        ("total",   invalid_total),
        ("accuracy", pct(invalid_correct, invalid_total)),
    ])),
])

# --- Follow-up questions breakdown ---
FOLLOWUPS = [t for t in ("answer_shift", "answer_angle", "answer_zone") if t in task_keys]

valid_time_correct_ids = [
    k for k in ids
    if combined[k]["answer_time"]["correct"]
    and combined[k]["answer_time"]["expected"].get("valid") is True
]
den_vc = len(valid_time_correct_ids)

def frac(n, d): 
    return None if d == 0 else round(n / d, 4)

cond_valid = OrderedDict()
cond_valid["denominator_valid_time_correct"] = den_vc

for t in FOLLOWUPS:
    num = sum(1 for k in valid_time_correct_ids if combined[k][t]["correct"])
    cond_valid[f"{t}_given_valid_time_correct"] = {
        "numerator": num,
        "denominator": den_vc,
        "accuracy": frac(num, den_vc),
    }

# --- Time delta breakdown ---
def midpoint_int(lo, hi): # Get midpoint for ranges
    return int(round((int(lo) + int(hi)) / 2.0))

def scalar_expected(x): # Map false to zero
    if x is False or x is None:
        return 0
    xi = as_int_or_none(x)
    if xi is not None:
        return xi
    if isinstance(x, list) and len(x) == 2 and (as_int_or_none(x[0]) is not None) and (as_int_or_none(x[1]) is not None):
        return midpoint_int(as_int_or_none(x[0]), as_int_or_none(x[1]))
    return None

def scalar_got(x):
    if x is False or x is None:
        return 0
    return as_int_or_none(x)

def period_hours_for_item(key, g_hours): # Use 24h or 12h format for wrap-around
    h = as_int_or_none(g_hours)
    if h is not None and h >= 13:
        return 24
    k = str(key).lower()
    if ("24" in k) and ("hour" in k):
        return 24
    return 12

def to_seconds(h, m, s, period_hours): #Turning time into seconds
    H = period_hours
    hh = (int(h) if h is not None else 0) % H
    mm = int(m) if m is not None else 0
    ss = int(s) if s is not None else 0
    # map onto [0, H*3600)
    return (hh * 3600 + mm * 60 + ss) % (H * 3600)

def to_hm(seconds_or_none): #Converting seconds to hours and minutes format
    if seconds_or_none is None:
        return None
    total = int(round(seconds_or_none))
    h = total // 3600
    m = (total % 3600) // 60
    return {"hours": h, "minutes": m}

deltas_circ = []
excluded_alt = 0
skipped_incomplete = 0

for k in ids:
    g = parse_obj(gt[k]["answer_time"])
    p = parse_obj(pred[k]["answer_time"])

    # Keep only valid times
    if g.get("valid") is not True:
        continue

    # Exclude alternatives
    if any(isinstance(g.get(f), dict) for f in ("hours", "minutes", "seconds")):
        excluded_alt += 1
        continue

    # Determine correctness
    if all(match_value(g.get(f), p.get(f)) for f in ("hours", "minutes", "seconds")):
        continue

    eh, em, es = (scalar_expected(g.get("hours")),
                  scalar_expected(g.get("minutes")),
                  scalar_expected(g.get("seconds")))
    gh, gm, gs = (scalar_got(p.get("hours")),
                  scalar_got(p.get("minutes")),
                  scalar_got(p.get("seconds")))

    if None in (eh, em, es, gh, gm, gs):
        skipped_incomplete += 1
        continue

    period_h = period_hours_for_item(k, g.get("hours"))
    te = to_seconds(eh, em, es, period_h)
    tp = to_seconds(gh, gm, gs, period_h)

    T = period_h * 3600
    diff = abs(tp - te)
    deltas_circ.append(min(diff, T - diff))

avg_delta_circ = round(sum(deltas_circ) / len(deltas_circ), 2) if deltas_circ else None
med_delta_circ = round(median(deltas_circ), 2) if deltas_circ else None
avg_hm = to_hm(avg_delta_circ)
med_hm = to_hm(med_delta_circ)

# --- Invalid predictions breakdown ---
pred_invalid = 0
for k in ids:
    got = combined[k]["answer_time"]["got"]
    v = got.get("valid") if isinstance(got, dict) else None
    if v is False:
        pred_invalid += 1

pct_all = round(100 * pred_invalid / len(ids), 2) if ids else 0.0

# --- Scores ---
per_task_acc = {t: round(totals[t]["correct"] / max(1, totals[t]["total"]), 4) for t in task_keys}

time_correct_ids = [k for k in ids if combined[k]["answer_time"]["correct"]]
den = len(time_correct_ids)

scores = OrderedDict([("per_task_accuracy_abs", per_task_acc)])
scores["answer_time_validity_breakdown"] = validity_breakdown
scores["predicted_invalid"] = {
    "count": pred_invalid,
    "percent_of_all_items": pct_all
}
scores["conditional_accuracy_given_valid_answer_time_correct"] = cond_valid
scores["answer_time_delta_seconds_on_incorrect_valid_circular"] = OrderedDict([
    ("count_items", len(deltas_circ)),
    ("average_delta_seconds", avg_delta_circ),
    ("median_delta_seconds", med_delta_circ),
    ("average_delta_hm", avg_hm),
    ("median_delta_hm", med_hm),
    ("excluded_due_to_alternatives", excluded_alt),
    ("skipped_incomplete_after_normalization", skipped_incomplete),
])

combined["_scores"] = scores

with open(COMBINED_OUT, "w", encoding = "utf-8") as f:
    json.dump(combined, f, ensure_ascii = False, indent = 2)

print("\nFinal scores:")
print(json.dumps(scores, indent = 2))
print(f"\nAll done. Wrote output file: {COMBINED_OUT} successfully.")