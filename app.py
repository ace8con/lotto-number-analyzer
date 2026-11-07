
import os
import requests
from flask import Flask, jsonify, render_template

app = Flask(__name__)

BASE_URL = "https://www.dhlottery.co.kr/lt645"
START_ROUND = 836
TIMEOUT = 20

_cache = None

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.dhlottery.co.kr/lt645/result",
}


def request_json(url, params=None):
    response = requests.get(
        url,
        params=params,
        headers=HEADERS,
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    return response.json()


def get_items(payload):
    """API 응답에서 data.list를 꺼냅니다."""
    data = payload.get("data", {})

    if isinstance(data, dict):
        items = data.get("list", [])
        if isinstance(items, list):
            return items

    return []


def get_latest_round():
    """최신 회차를 조회합니다."""
    url = f"{BASE_URL}/selectPstLt645Info.do"

    payload = request_json(url)
    items = get_items(payload)

    valid_rounds = []

    for item in items:
        try:
            valid_rounds.append(int(item["ltEpsd"]))
        except (KeyError, TypeError, ValueError):
            continue

    if not valid_rounds:
        raise RuntimeError(
            "최신 회차 정보를 읽지 못했습니다. "
            "동행복권 API 응답을 확인해 주세요."
        )

    return max(valid_rounds)


def get_batch(center):
    """요청 회차를 중심으로 API에서 회차 목록을 가져옵니다."""
    url = f"{BASE_URL}/selectPstLt645InfoNew.do"

    payload = request_json(
        url,
        params={
            "srchDir": "center",
            "srchLtEpsd": center,
        },
    )

    items = get_items(payload)

    if not items:
        raise RuntimeError(
            f"{center}회차 주변 데이터가 비어 있습니다."
        )

    return items


def normalize_draw(item):
    """새 API의 필드명을 프로그램에서 사용하는 형식으로 변환합니다."""
    try:
        round_no = int(item["ltEpsd"])

        numbers = [
            int(item[f"tm{i}WnNo"])
            for i in range(1, 7)
        ]

        bonus = int(item["bnsWnNo"])
        raw_date = str(item.get("ltRflYmd", ""))

    except (KeyError, TypeError, ValueError):
        return None

    if len(numbers) != 6:
        return None

    if any(number < 1 or number > 45 for number in numbers):
        return None

    if len(set(numbers)) != 6:
        return None

    if bonus < 1 or bonus > 45:
        return None

    if len(raw_date) == 8:
        draw_date = (
            f"{raw_date[:4]}-"
            f"{raw_date[4:6]}-"
            f"{raw_date[6:8]}"
        )
    else:
        draw_date = raw_date

    return {
        "round": round_no,
        "date": draw_date,
        "numbers": numbers,
        "bonus": bonus,
    }



def load_draws():
    global _cache

    try:
        # 매번 동행복권에서 최신 회차를 확인합니다.
        latest = get_latest_round()

        # 기존 데이터가 있고 최신 회차도 같다면
        # API에서 과거 데이터를 다시 가져오지 않습니다.
        if _cache is not None:
            cached_latest = max(
                draw["round"] for draw in _cache
            )

            if latest <= cached_latest:
                return _cache

        # 기존 데이터가 있으면 이어서 업데이트합니다.
        if _cache is not None:
            cached_latest = max(
                draw["round"] for draw in _cache
            )

            draw_map = {
                draw["round"]: draw
                for draw in _cache
            }

            # 새 회차 주변을 조회합니다.
            centers = list(
                range(cached_latest + 5, latest + 1, 10)
            )

            # 최신 회차는 반드시 직접 조회합니다.
            if latest not in centers:
                centers.append(latest)

        else:
            # 최초 실행: 836회부터 전체 데이터를 수집합니다.
            draw_map = {}

            centers = list(
                range(841, latest + 1, 10)
            )

            if latest not in centers:
                centers.append(latest)

        # 지정한 회차 주변의 데이터를 수집합니다.
        for center in centers:
            items = get_batch(center)

            for item in items:
                draw = normalize_draw(item)

                if draw is None:
                    continue

                round_no = draw["round"]

                if START_ROUND <= round_no <= latest:
                    draw_map[round_no] = draw

        # 필요한 회차가 모두 있는지 확인합니다.
        missing = [
            round_no
            for round_no in range(START_ROUND, latest + 1)
            if round_no not in draw_map
        ]

        # 새 회차를 가져오지 못했다면 전체 데이터를 다시 조회합니다.
        if missing:
            app.logger.warning(
                "일부 회차 누락. 전체 데이터를 다시 수집합니다: %s",
                missing[:10],
            )

            draw_map = {}

            centers = list(
                range(841, latest + 1, 10)
            )

            if latest not in centers:
                centers.append(latest)

            for center in centers:
                items = get_batch(center)

                for item in items:
                    draw = normalize_draw(item)

                    if draw is None:
                        continue

                    round_no = draw["round"]

                    if START_ROUND <= round_no <= latest:
                        draw_map[round_no] = draw

            # 전체 재수집 후에도 누락이 있으면 오류를 표시합니다.
            missing = [
                round_no
                for round_no in range(START_ROUND, latest + 1)
                if round_no not in draw_map
            ]

            if missing:
                raise RuntimeError(
                    "당첨번호 일부를 가져오지 못했습니다. "
                    f"누락 회차 예시: {missing[:10]}"
                )

        # 최신 회차부터 내림차순으로 정렬합니다.
        draws = sorted(
            draw_map.values(),
            key=lambda draw: draw["round"],
            reverse=True,
        )

        # 정상적으로 수집된 데이터만 캐시에 저장합니다.
        _cache = draws

        return draws

    except requests.RequestException as exc:
        app.logger.exception("동행복권 API 연결 오류")

        raise RuntimeError(
            "동행복권 API에 연결하지 못했습니다. "
            "잠시 후 다시 시도해 주세요."
        ) from exc



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

    except RuntimeError as exc:
        app.logger.exception("당첨번호 데이터 조회 실패")

        return jsonify({
            "error": str(exc),
        }), 502


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8000")),
    )
