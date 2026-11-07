
import os
import time
import requests
from flask import Flask, jsonify, render_template

app = Flask(__name__)

BASE_URL = "https://www.dhlottery.co.kr/lt645"
LATEST_URL = f"{BASE_URL}/selectPstLt645Info.do"
BATCH_URL = f"{BASE_URL}/selectPstLt645InfoNew.do"

START_ROUND = 836
TIMEOUT = 20

_cache = None

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://www.dhlottery.co.kr/lt645/result",
})


def get_api_list(url, params=None):
    response = session.get(url, params=params, timeout=TIMEOUT)
    response.raise_for_status()

    if "application/json" not in response.headers.get("Content-Type", ""):
        raise RuntimeError("동행복권 서버가 JSON이 아닌 응답을 보냈습니다.")

    payload = response.json()
    data = payload.get("data", {})
    items = data.get("list", [])

    if not isinstance(items, list):
        raise RuntimeError("당첨번호 데이터 형식이 예상과 다릅니다.")

    return items


def normalize_draw(item):
    round_no = int(item["ltEpsd"])

    raw_date = str(item.get("ltRflYmd", ""))
    if len(raw_date) == 8 and raw_date.isdigit():
        draw_date = (
            f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:8]}"
        )
    else:
        draw_date = raw_date

    numbers = [
        int(item[f"tm{i}WnNo"])
        for i in range(1, 7)
    ]

    bonus = int(item["bnsWnNo"])

    if len(set(numbers)) != 6:
        raise RuntimeError(f"{round_no}회 당첨번호가 올바르지 않습니다.")

    return {
        "round": round_no,
        "date": draw_date,
        "numbers": numbers,
        "bonus": bonus,
    }


def get_latest_round():
    items = get_api_list(LATEST_URL)

    if not items:
        raise RuntimeError("최신 회차 정보를 찾을 수 없습니다.")

    return max(int(item["ltEpsd"]) for item in items)


def load_draws():
    global _cache

    if _cache is not None:
        return _cache

    latest = get_latest_round()

    if latest < START_ROUND:
        raise RuntimeError("최신 회차가 분석 시작 회차보다 작습니다.")

    draws_by_round = {}

    # 한 번에 약 10개 회차씩 조회합니다.
    # 841회 중심 조회는 836~845회 범위를 포함합니다.
    center = START_ROUND + 5

    while center <= latest + 5:
        items = get_api_list(
            BATCH_URL,
            params={
                "srchDir": "center",
                "srchLtEpsd": center,
            },
        )

        for item in items:
            try:
                draw = normalize_draw(item)
                round_no = draw["round"]

                if START_ROUND <= round_no <= latest:
                    draws_by_round[round_no] = draw

            except (KeyError, TypeError, ValueError):
                continue

        center += 5
        time.sleep(0.25)

    # 데이터가 빠진 회차가 있는지 확인합니다.
    missing = [
        number
        for number in range(START_ROUND, latest + 1)
        if number not in draws_by_round
    ]

    if missing:
        raise RuntimeError(
            f"당첨번호 일부를 가져오지 못했습니다. "
            f"누락 회차 예시: {missing[:10]}"
        )

    _cache = [
        draws_by_round[number]
        for number in range(latest, START_ROUND - 1, -1)
    ]

    return _cache


@app.get("/")
def home():
    return render_template("index.html")


@app.get("/api/draws")
def api_draws():
    try:
        draws = load_draws()

        return jsonify({
            "draws": draws,
            "latest": draws[0]["round"],
            "start": START_ROUND,
            "count": len(draws),
        })

    except Exception as exc:
        app.logger.exception("당첨번호 데이터 조회 실패")

        return jsonify({
            "error": str(exc)
        }), 502


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8000"))
    )
