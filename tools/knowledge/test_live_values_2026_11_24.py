"""Lab 24 Nov 2026: live values and device states are never answered from documents."""
import pytest

import agent


@pytest.mark.parametrize("q", ["What is the status of BIN_NODE_1?", "What is the latest temperature?", "What is the humidity?",
                               "Which cameras are connected?", "Which ESP32 nodes are online?",
                               "Which PC agents are outdated?", "What is the current camera FPS?"])
def test_live_value_questions_are_guarded(q):
    assert agent.status_guard(q)


@pytest.mark.parametrize("q", ["What does ENV_LAB01 measure?", "How is the humidity measured?",
                               "What is the state of the art in re-identification?", "Which cameras does the lab use?",
                               "What is the status rule for a stale robot?", "How are boards connected to the portal?"])
def test_design_questions_still_reach_the_documents(q):
    assert not agent.status_guard(q)
