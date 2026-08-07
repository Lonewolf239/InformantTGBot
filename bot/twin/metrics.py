import json
import logging

from bot.twin.database import twin_db
from bot.twin.testset import LAST_TEST_RUN_META_KEY

logger = logging.getLogger(__name__)

COMPONENT_WEIGHTS = {
    "feedback": 0.40,
    "test_set": 0.25,
    "data_volume": 0.20,
    "fact_confidence": 0.15,
}

DATA_VOLUME_SATURATION = 150
EVIDENCE_CAP = 5


async def _feedback_component() -> tuple[float, dict] | None:
    stats = await twin_db.get_feedback_stats()
    total_rated = stats["good"] + stats["maybe"] + stats["bad"]
    if total_rated == 0:
        return None
    score = (stats["good"] + stats["maybe"] * 0.5) / total_rated
    return score, {
        "good": stats["good"],
        "maybe": stats["maybe"],
        "bad": stats["bad"],
        "total_rated": total_rated,
    }


async def _test_set_component() -> tuple[float, dict] | None:
    raw = await twin_db.get_meta(LAST_TEST_RUN_META_KEY)
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except Exception:
        return None
    total = data.get("total", 0)
    if not total:
        return None
    score = data.get("passed", 0) / total
    return score, {
        "passed": data.get("passed", 0),
        "total": total,
        "run_at": data.get("run_at"),
    }


async def _data_volume_component() -> tuple[float, dict]:
    from bot.twin.pipeline import get_status

    status = await get_status()
    processed = await twin_db.get_processed_samples_count()
    signal = status["dialogue_examples_count"] + status["knowledge_count"] + processed / 10
    score = min(1.0, signal / DATA_VOLUME_SATURATION)
    return score, {
        "dialogue_examples": status["dialogue_examples_count"],
        "knowledge_count": status["knowledge_count"],
        "processed_samples": processed,
    }


async def _fact_confidence_component() -> tuple[float, dict] | None:
    summary = await twin_db.get_knowledge_summary(limit=1000)
    facts = summary["top_facts"]
    if not facts:
        return None
    avg = sum(min(f["evidence_count"], EVIDENCE_CAP) for f in facts) / len(facts) / EVIDENCE_CAP
    return avg, {"facts_counted": len(facts)}


async def estimate_similarity() -> dict:
    components = {}
    weighted_sum = 0.0
    weight_total = 0.0

    results = {
        "feedback": await _feedback_component(),
        "test_set": await _test_set_component(),
        "fact_confidence": await _fact_confidence_component(),
    }
    for key, result in results.items():
        if result is None:
            continue
        score, details = result
        components[key] = {"score": score, "weight": COMPONENT_WEIGHTS[key], **details}
        weighted_sum += score * COMPONENT_WEIGHTS[key]
        weight_total += COMPONENT_WEIGHTS[key]

    data_score, data_details = await _data_volume_component()
    components["data_volume"] = {
        "score": data_score,
        "weight": COMPONENT_WEIGHTS["data_volume"],
        **data_details,
    }
    weighted_sum += data_score * COMPONENT_WEIGHTS["data_volume"]
    weight_total += COMPONENT_WEIGHTS["data_volume"]

    overall = weighted_sum / weight_total if weight_total > 0 else None

    return {"overall": overall, "components": components}
