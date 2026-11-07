import os
import requests
from flask import Flask, jsonify, render_template

app = Flask(__name__)

API_URL = "https://www.dhlottery.co.kr/common.do"
TIMEOUT = 12
_cache = None

def get_draw(number):
    response = requests.get(
        API_URL,
        params={"method": "getLottoNumber", "drwNo": number},
        timeout=TIMEOUT,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    response.raise_for_status()
    data = response.json()
    if data.get("returnValue") != "success":
        return None
    numbers = [data.get(f"drwtNo{i}") for i in range(1, 7)]
    if any(not isinstance(n, int) for n in numbers):
        return None
    return {
        "round": data["drwNo"],
        "date": data.get("drwNoDate", ""),
        "numbers": numbers,
        "bonus": data.get("bnusNo"),
    }

def load_draws():
    global _cache
    if _cache is not None:
        return _cache

    # Probe downward from a generous estimate to discover the latest valid round.
    latest = None
    for number in range(1300, 1, -1):
        try:
            latest = get_draw(number)
            if latest:
                break
        except requests.RequestException:
            raise RuntimeError("로또 당첨번호 서버에 연결할 수 없습니다. 잠시 후 다시 시도해 주세요.")

    if not latest:
        raise RuntimeError("최신 회차를 찾지 못했습니다.")

    draws = []
    for number in range(latest["round"], 0, -1):
        try:
            draw = get_draw(number)
            if draw:
                draws.append(draw)
        except requests.RequestException:
            raise RuntimeError("과거 당첨번호를 가져오지 못했습니다. 잠시 후 다시 시도해 주세요.")

    _cache = draws
    return draws

@app.get("/")
def home():
    return render_template("index.html")

@app.get("/api/draws")
def api_draws():
    try:
        draws = load_draws()
        return jsonify({"draws": draws, "latest": draws[0]["round"]})
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 502

@app.get("/health")
def health():
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
