from pathlib import Path

from bant_agent.scoring import load_config, score_text

ROOT = Path(__file__).resolve().parent.parent
CFG = load_config(ROOT / "config" / "bant.yaml")


def run(name):
    return score_text((ROOT / "samples" / f"{name}.txt").read_text(), CFG)


def test_hot_deal_is_qualified_and_every_dimension_found():
    r = run("hot-deal")
    assert r["grade"] == "Qualified" and r["total"] >= 70
    assert all(v["level"] >= 2 for v in r["dimensions"].values())


def test_cold_deal_unqualified_with_disqualifiers():
    r = run("cold-deal")
    assert r["grade"] == "Unqualified" and r["total"] < 20
    assert r["dimensions"]["budget"]["disqualifiers"]
    assert r["dimensions"]["timeline"]["disqualifiers"]


def test_seller_pitch_is_not_credited_to_customer():
    r = run("cold-deal")  # seller says problem, pricing, hours, live in a week
    assert r["dimensions"]["need"]["points"] == 0


def test_warm_deal_has_gaps_and_questions():
    r = run("warm-deal")
    assert r["grade"] == "Nurture"
    assert [g["dimension"] for g in r["gaps"]] == ["budget"]  # budget only vaguely mentioned
    assert "budget" in r["gaps"][0]["ask"].lower()


def test_led_evidence_scores_lower_than_unprompted():
    led = "Rep (Seller): What is your budget?\nBuyer (Customer): We have budget approved."
    free = "Rep (Seller): Tell me about your team.\nBuyer (Customer): We have budget approved."
    assert score_text(led, CFG)["dimensions"]["budget"]["points"] < score_text(free, CFG)["dimensions"]["budget"]["points"]
    assert score_text(led, CFG)["dimensions"]["budget"]["prompted"] == "led"


def test_unlabelled_speaker_ignored_and_warned():
    r = score_text("Pat: We have budget approved.\nAlex (Seller): Great.", CFG)
    assert r["dimensions"]["budget"]["points"] == 0
    assert any("Unlabelled" in w for w in r["warnings"])


def test_seller_names_flag_labels_speakers():
    r = score_text("Pat: Tell me more.\nQ: I make the final decision.", CFG, seller_names=["Pat"], customer_names=["Q"])
    assert r["dimensions"]["authority"]["level"] == 3


def test_intelligence_extracts_competitor_next_step_objection():
    r = run("hot-deal")
    i = r["intelligence"]
    assert "gong" in i["competitors_mentioned"]
    assert i["next_steps"] and i["objections"]
    assert 0 < i["talk_ratio_seller_pct"] < 100


def test_no_customer_turns_scores_zero():
    r = score_text("Alex (Seller): hello?", CFG)
    assert r["total"] == 0 and r["warnings"]


def test_negation_guard_blocks_not_looking_to_improve():
    r = score_text("Rep (Seller): Hi.\nBuyer (Customer): We are not looking to improve anything.", CFG)
    assert r["dimensions"]["need"]["points"] == 0


def test_lexicon_catches_indirect_phrasing_the_regex_missed():
    r = score_text("Rep (Seller): Tell me more.\nBuyer (Customer): The budget has been sanctioned.", CFG)
    assert r["dimensions"]["budget"]["level"] == 3


def test_wildcard_and_apostrophe_tolerance():
    r = score_text("Rep (Seller): Hi.\nBuyer (Customer): We dont have any budget right now.", CFG)
    assert r["dimensions"]["budget"]["disqualifiers"]


def test_indian_english_sample_scores_high_with_intelligence():
    r = run("indian-english")
    assert r["grade"] == "Qualified"
    d = r["dimensions"]
    assert d["budget"]["level"] >= 2 and d["timeline"]["level"] == 3 and d["authority"]["level"] >= 2
    i = r["intelligence"]
    assert i["momentum"] == "positive"
    assert "integration" in i["objections"]
    assert {"cfo", "head of"} <= set(i["stakeholders_mentioned"])


def test_stall_signals_make_momentum_stalling():
    r = score_text("Rep (Seller): Next steps?\nBuyer (Customer): Just send me an email, I'll get back to you.", CFG)
    assert r["intelligence"]["momentum"] == "stalling"


def test_lexicon_has_no_conflicts_or_bad_phrases():
    from bant_agent.lexicon import check, load_lexicon
    assert check(load_lexicon(ROOT / "config" / "lexicon.yaml")) == []
