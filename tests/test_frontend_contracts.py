"""Frontend/API contract checks for plain JavaScript controllers."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_game_page_submits_guess_with_backend_game_id_contract():
    game_js = (ROOT / "frontend/js/game.js").read_text()

    assert "api.submitGuess(state.game.game_id, state.currentGuess)" in game_js
    assert "api.submitGuess(state.game.id, state.currentGuess)" not in game_js


def test_welcome_page_sends_selected_word_length():
    welcome_html = (ROOT / "frontend/index.html").read_text()
    welcome_js = (ROOT / "frontend/js/welcome.js").read_text()

    assert 'id="length-picker"' in welcome_html
    assert 'data-value="10"' in welcome_html
    assert "session_word_length: state.wordLength" in welcome_js
    assert "gameRequest.word_length = Number(state.wordLength)" in welcome_js
