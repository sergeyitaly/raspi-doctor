import os, requests, textwrap, pathlib

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
MODEL = os.getenv("OLLAMA_MODEL", "phi3:mini")

def summarize_text(text: str, prompt: str = None, max_chars=6000):
    # Truncate to keep response fast on small models
    text = text[-max_chars:]
    if not prompt:
        prompt = textwrap.dedent("""
        You are a Raspberry Pi health analyst. From the context below (logs, metrics, errors),
        produce a concise health report with sections:
        - Status Summary (1–3 bullets)
        - Immediate Alerts (if any; concrete, with hints)
        - Performance (CPU, Memory, Disk, Temp)
        - Storage/SD Health (from SMART or symptoms)
        - Services/Network
        - Suggested Actions (prioritized, short commands or checks)

        Be specific but brief. If something is missing, say what else would help diagnose it.
        """).strip()

    full_prompt = f"{prompt}\n\n--- CONTEXT START ---\n{text}\n--- CONTEXT END ---"
    url = f"{OLLAMA_HOST}/api/generate"
    payload = {"model": MODEL, "prompt": full_prompt, "stream": False}
    r = requests.post(url, json=payload, timeout=120)
    r.raise_for_status()
    data = r.json()
    return data.get("response", "").strip()
