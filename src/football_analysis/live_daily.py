"""Live daily pipeline: API-Football -> model -> Supabase -> optional DeepSeek -> Telegram.

All credentials are read from environment variables. Never print or persist secrets.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

API_BASE = "https://v3.football.api-sports.io"
SUPABASE_TABLES = ("matches", "predictions", "coupons", "coupon_selections", "pipeline_runs")


def request_json(url: str, *, headers: dict[str, str] | None = None, payload: dict[str, Any] | None = None, timeout: int = 25) -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers or {}, method="GET" if data is None else "POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"HTTP request failed for {urllib.parse.urlsplit(url).hostname}: {exc}") from exc
    if not isinstance(body, dict):
        raise RuntimeError("Unexpected API response")
    return body


def api_get(path: str, params: dict[str, str]) -> dict[str, Any]:
    key = os.environ.get("API_FOOTBALL_KEY", "").strip()
    if not key:
        raise RuntimeError("Missing API_FOOTBALL_KEY")
    query = urllib.parse.urlencode(params)
    body = request_json(f"{API_BASE}/{path}?{query}", headers={"x-apisports-key": key, "Accept": "application/json"})
    if body.get("errors"):
        raise RuntimeError(f"API-Football returned errors: {body['errors']}")
    return body


def supabase_request(table: str, *, method: str = "GET", params: str = "", payload: Any = None, prefer: str = "return=representation") -> Any:
    base = os.environ.get("SUPABASE_URL", "").strip().rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not base or not key:
        raise RuntimeError("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY")
    url = f"{base}/rest/v1/{table}" + (f"?{params}" if params else "")
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"apikey": key, "Authorization": f"Bearer {key}", "Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    if prefer:
        headers["Prefer"] = prefer
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=25) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else None
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Supabase {method} {table} failed: {exc}") from exc


def telegram_send(text: str) -> dict[str, Any]:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        raise RuntimeError("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    result = request_json(url, headers={"Content-Type": "application/json"}, payload={
        "chat_id": chat_id, "text": text, "disable_web_page_preview": True
    })
    if not result.get("ok") or not isinstance(result.get("result"), dict):
        raise RuntimeError(f"Telegram rejected sendMessage: {result.get('description', 'unknown error')}")
    return result["result"]


def deepseek_note(coupon: list[dict[str, Any]]) -> str:
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not key or not coupon:
        return ""
    prompt = "Écris une note française très courte et prudente sur cette sélection sportive. Ne change pas les pronostics, n'invente aucun fait, ne promets aucun gain. Données JSON : " + json.dumps(coupon, ensure_ascii=False)
    result = request_json("https://api.deepseek.com/chat/completions", headers={
        "Authorization": f"Bearer {key}", "Content-Type": "application/json"
    }, payload={
        "model": "deepseek-chat", "messages": [
            {"role": "system", "content": "Tu es un assistant de rédaction. Pas de garantie de résultat, pas d'invention."},
            {"role": "user", "content": prompt}
        ], "temperature": 0.2, "max_tokens": 120
    })
    try:
        return str(result["choices"][0]["message"]["content"]).strip()[:700]
    except (KeyError, IndexError, TypeError):
        return ""


def poisson_probs(home_xg: float, away_xg: float, max_goals: int = 8) -> dict[str, float]:
    import math
    def dist(lam: float) -> list[float]:
        return [math.exp(-lam) * lam**i / math.factorial(i) for i in range(max_goals + 1)]
    h, a = dist(home_xg), dist(away_xg)
    home = draw = away = 0.0
    for i, pi in enumerate(h):
        for j, pj in enumerate(a):
            p = pi * pj
            if i > j: home += p
            elif i == j: draw += p
            else: away += p
    total = home + draw + away
    return {"1": home / total, "X": draw / total, "2": away / total}


def run() -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    date = os.environ.get("MATCH_DATE", now.date().isoformat())
    run_key = f"api-football:{date}"
    existing = supabase_request("pipeline_runs", params=f"run_key=eq.{urllib.parse.quote(run_key)}&select=id,status", prefer="")
    if existing and existing[0].get("status") == "succeeded":
        print(f"Already completed: {run_key}")
        return {"status": "skipped", "reason": "already_succeeded"}
    run_rows = supabase_request("pipeline_runs", method="POST", payload={"run_key": run_key, "status": "running", "metadata": {"date": date, "market_weight": 0.0}}, prefer="return=representation")
    run_id = run_rows[0]["id"]
    try:
        response = api_get("fixtures", {"date": date, "timezone": "UTC"})
        fixtures = response.get("response", [])
        if not fixtures:
            message = f"⚽ Analyse Football Codex — {date}\nAucun match trouvé par API-Football. Aucun coupon publié."
            sent = telegram_send(message)
            supabase_request("pipeline_runs", method="PATCH", params=f"id=eq.{run_id}", payload={"status": "succeeded", "finished_at": datetime.now(timezone.utc).isoformat(), "fixtures_seen": 0, "predictions_created": 0, "metadata": {"telegram_message_id": sent.get("message_id"), "reason": "no_fixtures"}}, prefer="return=minimal")
            print(f"Telegram confirmed: message_id={sent.get('message_id')}; no fixtures")
            return {"status": "succeeded", "message_id": sent.get("message_id"), "fixtures": 0}

        prepared: list[dict[str, Any]] = []
        for item in fixtures:
            fixture = item.get("fixture", {})
            teams = item.get("teams", {})
            league = item.get("league", {})
            fid = fixture.get("id")
            kickoff = fixture.get("date")
            home = (teams.get("home") or {}).get("name")
            away = (teams.get("away") or {}).get("name")
            if not fid or not kickoff or not home or not away or kickoff <= now.isoformat():
                continue
            # API-Football prediction endpoint provides model probabilities where available.
            pred_resp = api_get("predictions", {"fixture": str(fid)})
            pred_rows = pred_resp.get("response", [])
            prediction = (pred_rows[0].get("predictions") or {}) if pred_rows else {}
            percent = prediction.get("percent") or {}
            probs = {}
            for label, raw in (("1", percent.get("home")), ("X", percent.get("draw")), ("2", percent.get("away"))):
                try:
                    probs[label] = float(str(raw).replace("%", "").strip()) / 100
                except (ValueError, TypeError):
                    pass
            if len(probs) != 3 or sum(probs.values()) <= 0:
                continue
            total = sum(probs.values())
            probs = {k: v / total for k, v in probs.items()}
            pick = max(probs, key=probs.get)
            prepared.append({"provider_match_id": str(fid), "league_id": str(league.get("id") or ""), "league_name": str(league.get("name") or ""), "season": league.get("season"), "home_team": home, "away_team": away, "kickoff_at": kickoff, "status": "scheduled", "raw_payload": item, "pick": pick, "probabilities": probs, "confidence": probs[pick]})
        prepared.sort(key=lambda x: (-x["confidence"], x["kickoff_at"]))
        selected = prepared[:5]
        if not selected:
            message = f"⚽ Analyse Football Codex — {date}\n{len(fixtures)} fixture(s) consulté(s), mais aucune prédiction API-Football exploitable. Aucun coupon publié."
            sent = telegram_send(message)
            supabase_request("pipeline_runs", method="PATCH", params=f"id=eq.{run_id}", payload={"status": "succeeded", "finished_at": datetime.now(timezone.utc).isoformat(), "fixtures_seen": len(fixtures), "predictions_created": 0, "metadata": {"telegram_message_id": sent.get("message_id"), "reason": "no_predictions"}}, prefer="return=minimal")
            print(f"Telegram confirmed: message_id={sent.get('message_id')}; no usable predictions")
            return {"status": "succeeded", "message_id": sent.get("message_id"), "fixtures": len(fixtures), "coupon": 0}

        match_db: dict[str, str] = {}
        prediction_db: dict[str, str] = {}
        for row in prepared:
            match_payload = {k: row[k] for k in ("provider_match_id", "league_id", "league_name", "season", "home_team", "away_team", "kickoff_at", "status", "raw_payload")}
            stored = supabase_request("matches", method="POST", params="on_conflict=provider,provider_match_id", payload={"provider": "api-football", **match_payload}, prefer="resolution=merge-duplicates,return=representation")
            if not stored:
                stored = supabase_request("matches", params=f"provider=eq.api-football&provider_match_id=eq.{row['provider_match_id']}&select=id", prefer="")
            if not stored:
                raise RuntimeError(f"Could not persist match {row['provider_match_id']}")
            mid = stored[0]["id"]
            match_db[row["provider_match_id"]] = mid
            probs = row["probabilities"]
            pred = supabase_request("predictions", method="POST", payload={"match_id": mid, "model_name": "api-football-predictions", "model_version": "v3", "probability_home": probs["1"], "probability_draw": probs["X"], "probability_away": probs["2"], "market_weight": 0.0, "explanation": {"provider": "api-football", "pick": row["pick"], "market_weight_disabled": True}}, prefer="return=representation")
            prediction_db[row["provider_match_id"]] = pred[0]["id"]

        coupon_rows = supabase_request("coupons", method="POST", params="on_conflict=coupon_date,title", payload={"coupon_date": date, "status": "draft", "title": "Daily API-Football 1X2", "selection_count": len(selected), "metadata": {"source": "API-Football", "market_weight": 0.0}}, prefer="resolution=merge-duplicates,return=representation")
        if not coupon_rows:
            coupon_rows = supabase_request("coupons", params=f"coupon_date=eq.{date}&title=eq.Daily%20API-Football%201X2&select=id", prefer="")
        coupon_id = coupon_rows[0]["id"]
        selections = []
        lines = [f"⚽ ANALYSE FOOTBALL CODEX — {date}", "Source: API-Football | Poids marché: 0 (désactivé)", ""]
        for i, row in enumerate(selected, 1):
            pred_id = prediction_db[row["provider_match_id"]]
            selections.append({"coupon_id": coupon_id, "match_id": match_db[row["provider_match_id"]], "prediction_id": pred_id, "market": "1X2", "selection": row["pick"], "probability": row["confidence"]})
            lines.append(f"{i}. {row['home_team']} – {row['away_team']} | {row['pick']} | {row['confidence']:.0%}")
        supabase_request("coupon_selections", method="POST", payload=selections, prefer="return=minimal")
        note = deepseek_note([{"home": x["home_team"], "away": x["away_team"], "pick": x["pick"], "probability": round(x["confidence"], 3)} for x in selected])
        if note:
            lines.extend(["", "Note IA (sans garantie):", note])
        lines.extend(["", "⚠️ Pronostics probabilistes, résultats incertains. Pas de garantie de gain."])
        sent = telegram_send("\n".join(lines))
        supabase_request("coupons", method="PATCH", params=f"id=eq.{coupon_id}", payload={"status": "published", "published_at": datetime.now(timezone.utc).isoformat(), "telegram_message_id": str(sent.get("message_id")), "metadata": {"source": "API-Football", "market_weight": 0.0, "telegram_chat_id": os.environ.get("TELEGRAM_CHAT_ID", "")}}, prefer="return=minimal")
        supabase_request("pipeline_runs", method="PATCH", params=f"id=eq.{run_id}", payload={"status": "succeeded", "finished_at": datetime.now(timezone.utc).isoformat(), "fixtures_seen": len(fixtures), "predictions_created": len(prepared), "coupon_id": coupon_id, "metadata": {"telegram_message_id": sent.get("message_id"), "selected": len(selected)}}, prefer="return=minimal")
        print(f"TELEGRAM_DELIVERY_CONFIRMED message_id={sent.get('message_id')} chat_id={sent.get('chat', {}).get('id')} coupon_id={coupon_id} selections={len(selected)}")
        return {"status": "succeeded", "message_id": sent.get("message_id"), "coupon_id": coupon_id, "selections": len(selected)}
    except Exception as exc:
        try:
            supabase_request("pipeline_runs", method="PATCH", params=f"id=eq.{run_id}", payload={"status": "failed", "finished_at": datetime.now(timezone.utc).isoformat(), "error_message": str(exc)[:1500]}, prefer="return=minimal")
        except Exception:
            pass
        raise


if __name__ == "__main__":
    try:
        result = run()
        print(json.dumps(result, ensure_ascii=False))
    except Exception as error:
        print(f"PIPELINE_FAILED: {error}", file=sys.stderr)
        raise SystemExit(1)
