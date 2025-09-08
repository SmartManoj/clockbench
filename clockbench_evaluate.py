import json, requests, re, base64
import litellm
import traceback
import os
MODEL = 'vertex_ai/gemini-2.5-pro'
DATASET_PATH = "input/input_sample.json"
OUTPUT_PATH = "output_sample.json"
TIMEOUT = 120

def try_json(s: str):
    s = s.strip()
    try:
        return json.loads(s), s
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", s, flags = re.DOTALL)
        return (json.loads(m.group(0)), s) if m else (None, s)

def post_chat(messages, response_format=''):
    # r = requests.post(API, headers = HEADERS, json = {"model": MODEL, "messages": messages}, timeout = TIMEOUT)
    r = litellm.completion(
        model=MODEL,
        messages=messages,
        seed=42,
        temperature=0,
        # response_format=response_format
        )
    data = r.json()
    content = data["choices"][0]["message"]["content"]
    return content.strip(), data

def convert_images(path: str) -> str: #Images converter
    with open(path, "rb") as f:
        return "data:image/png;base64," + base64.b64encode(f.read()).decode("ascii")

def ask_questions(dataset_item): #Ask model a set of questions
    image_url = dataset_item["image_url"]
    q_time = dataset_item["question_time"].strip()
    q_shift = dataset_item["question_shift"].strip()
    q_angle = dataset_item["question_angle"].strip()
    q_zone = dataset_item["question_zone"].strip()
    img_ref = convert_images(image_url) #Convert images to Base64

    messages = [{"role": "system", "content": "Be precise. When JSON is requested, reply with ONLY that JSON (no preface, no code block)."}]

    # --- Time ---
    messages.append({"role": "user", "content": [
        {"type": "text", "text": q_time},
        {"type": "image_url", "image_url": {"url": img_ref}}
    ]})
    a1_text, j1 = post_chat(messages)
    a1_obj, _ = try_json(a1_text)
    messages.append({"role": "assistant", "content": a1_text})

    # --- Shift ---
    messages.append({"role": "user", "content": q_shift})
    a2_text, _ = post_chat(messages)
    a2_obj, _  = try_json(a2_text)
    messages.append({"role": "assistant", "content": a2_text})

    # --- Angle ---
    messages.append({"role": "user", "content": q_angle})
    a3_text, _ = post_chat(messages)
    a3_obj, _  = try_json(a3_text)
    messages.append({"role": "assistant", "content": a3_text})

    # --- Time zone ---
    messages.append({"role": "user", "content": q_zone})
    a4_text, _ = post_chat(messages)
    a4_obj, _  = try_json(a4_text)

    return {
        "answer_time":  a1_obj if a1_obj is not None else a1_text,
        "answer_shift": a2_obj if a2_obj is not None else a2_text,
        "answer_angle": a3_obj if a3_obj is not None else a3_text,
        "answer_zone":  a4_obj if a4_obj is not None else a4_text,
    }

# --- Load dataset ---
with open(DATASET_PATH, "r", encoding = "utf-8") as f:
    dataset = json.load(f)

# --- Iterate all items ---
results = {}
ids = list(dataset.keys())
print(f"Total clocks: {len(ids)}")

for i, k in enumerate(ids, 1):
    try:
        res = ask_questions(dataset[k])
    except Exception as e:
        traceback.print_exc()
        res = {"error": str(e)}
    results[k] = res
    print(f"[{i}] {k}", flush = True)
    # break

# --- Save output ---
with open(OUTPUT_PATH, "w", encoding = "utf-8") as f:
    json.dump(results, f, ensure_ascii = False, indent = 2)

print(f"\nAll done. Wrote output file: {OUTPUT_PATH} successfully.")
from pymsgbox import alert
alert('Evaluation complete')