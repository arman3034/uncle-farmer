# pyright: reportPrivateUsage=false
# White-box tests: they check this module's internal helpers (leading-underscore names) directly.
"""The script language: parsing every command, the safe expression evaluator (compile_expr /
evaluate), the AST whitelist, and running blocks against a tiny fake bot."""

from __future__ import annotations

import ast
import threading
import types

import pytest

from unclefarmer.engine import script as S
from unclefarmer.engine.bot import Respawned, Stopped
from typing import Any, NoReturn
from collections.abc import Callable
from conftest import as_bot, returning, stand_in
from unclefarmer.engine.script import Node


# ---------------------------------------------------------------- helpers
class FakeLink:
    def __init__(self, bag: object = None, map_: dict[str, Any] | None = None) -> None:
        self.bag = [{"name": "Milkfish", "count": 3}, {"name": "Small Fish", "count": 1}] if bag is None else bag
        self.map_ = {"id": 5121, "name": "Wolf Prairie"} if map_ is None else map_

    def json(self, line: str) -> Any:
        if line == "mem bag":
            return self.bag
        if line == "mem map":
            return self.map_
        return {}


class FakeBot:
    """Everything the script Runner touches, recording what it is asked to do."""

    def __init__(self, bag: object = None, map_: dict[str, Any] | None = None, kills: int = 0, minutes: float = 0.0,
                 targets: list[Any] | None = None, tally: object = None, mps: tuple[float, float] | None = None) -> None:
        self.a = FakeLink(bag, map_)
        self.kills = kills
        self._minutes = minutes
        self._targets = targets if targets is not None else []
        self.tally = tally
        self.stop_event = threading.Event()
        self.p: dict[str, Any] = {}
        self.logs: list[tuple[str, bool]] = []
        self.calls: list[tuple[Any, ...]] = []      # (what was asked, its arguments...)
        self.watches: list[tuple[Callable[[], object], str]] = []
        self.end_place = None
        self.mps = mps
        self.mev = {"hp": 50, "maxhp": 100, "x": 1, "y": 2, "sheet": {"level": 10, "mp": 20, "maxmp": 40}}

    def me(self) -> dict[str, Any]:
        return self.mev

    def mp_now(self, me: dict[str, Any], now: float) -> tuple[float, float] | None:
        return self.mps

    def minutes(self) -> float:
        return self._minutes

    def snap(self) -> dict[str, Any]:
        return {"self": self.mev}

    def map_id(self) -> int:
        return 5121

    def targets(self, snap: dict[str, Any]) -> list[Any]:
        return self._targets

    def check(self) -> None:
        pass

    def sleep(self, seconds: float) -> None:
        self.calls.append(("sleep", seconds))

    def log(self, line: str, speak: bool=False) -> None:
        self.logs.append((line, speak))

    def travel(self, mid: int, cell: tuple[float, float]) -> None:
        self.calls.append(("travel", mid, cell))

    def go(self, mid: int, cell: tuple[float, float], npc: str | None, talk: bool) -> None:
        self.calls.append(("go", mid, cell, npc, talk))

    def go_dungeon(self, entrance: dict[str, Any], talk: bool) -> None:
        self.calls.append(("go_dungeon", entrance, talk))

    def talk(self, npc: str, cell: tuple[float, float] | None=None) -> bool:
        self.calls.append(("talk", npc, cell))
        return True

    def choose(self, pattern: str) -> dict[str, Any] | None:
        self.calls.append(("choose", pattern))
        return {"text": pattern}

    def walk_to(self, cell: tuple[float, float]) -> str:
        self.calls.append(("walk_to", cell))
        return "arrived"

    def key(self, k: str, ms: int) -> None:
        self.calls.append(("key", k, ms))

    def hold(self, k: str) -> None:
        self.calls.append(("hold", k))

    def let_go(self, k: str | None=None) -> None:
        self.calls.append(("let_go", k))

    def potion(self, kind: str) -> tuple[str | None, str | None]:
        self.calls.append(("potion", kind))
        return ("4", "Red Potion")

    def drink(self, kind: str, name: str | None, key: str | None) -> bool:
        self.calls.append(("drink", kind, name, key))
        return True

    def go_home(self, tries: int = 3) -> bool:
        self.calls.append(("go_home",))
        return True

    def farm(self, mid: int, **kw: Any) -> None:
        self.calls.append(("farm", mid, kw))


def kinds(nodes: list[Node]) -> list[str]:
    return [n.kind for n in nodes]


def loglines(bot: FakeBot) -> list[str]:
    return [line for line, _ in bot.logs]


# ---------------------------------------------------------------- _strip_comment / _at / _message_split
def test_strip_comment_drops_a_trailing_comment() -> None:
    assert S._strip_comment("say hi # not this") == "say hi"


def test_strip_comment_keeps_a_hash_inside_quotes() -> None:
    assert S._strip_comment('say "a#b"') == 'say "a#b"'
    assert S._strip_comment("say 'a#b'") == "say 'a#b'"


def test_strip_comment_on_a_whole_line_comment() -> None:
    assert S._strip_comment("# nothing here") == ""
    assert S._strip_comment("   ") == ""


@pytest.mark.parametrize("rest,expected", [("Wolf at 5, 6", ("Wolf", (5, 6))), ("Wolf at 5 6", ("Wolf", (5, 6))),
                                           ("Wolf at 5|6", ("Wolf", (5, 6))), ("Wolf", ("Wolf", None)),
                                           ("Wolf at 5x6", ("Wolf at 5x6", None))])
def test_at(rest: str, expected: tuple[str, tuple[int, int]] | tuple[str, None]) -> None:
    assert S._at(rest, 1) == expected


def test_message_split_splits_on_the_first_colon() -> None:
    assert S._message_split("kills >= 5 : done") == ("kills >= 5 ", ":", " done")
    assert S._message_split("a : b : c") == ("a ", ":", " b : c")


def test_message_split_ignores_a_colon_in_quotes() -> None:
    assert S._message_split('clock == "23:00"') == ('clock == "23:00"', "", "")
    assert S._message_split("kills >= 5") == ("kills >= 5", "", "")


# ---------------------------------------------------------------- compile_expr: allowed
@pytest.mark.parametrize("text", ["1 + 2 * 3", "hp > 50 and mp < 10", "not (kills > 1 or map == 5)",
                                  'bag("Milkfish") >= 2', "round(x)", "min(1, 2)", "max(1, 2)", "abs(-3)",
                                  "int(3.9)", "random(1, 6)", "-hp", "+hp", "1.5 % 2", "7 // 2", "1 < x < 10",
                                  "true and not false", "True", "False", "5"])
def test_compile_expr_accepts_safe_expressions(text: str) -> None:
    assert S.compile_expr(text, 1) is not None


# ---------------------------------------------------------------- compile_expr: rejected
@pytest.mark.parametrize("text", ["", "   "])
def test_compile_expr_needs_an_expression(text: str) -> None:
    with pytest.raises(S.ScriptError) as e:
        S.compile_expr(text, 4)
    assert e.value.line == 4


def test_compile_expr_reports_a_syntax_error() -> None:
    with pytest.raises(S.ScriptError):
        S.compile_expr("1 +", 2)


@pytest.mark.parametrize("text", ["__import__('os')", "os.system('x')", "open('f')", "print(1)"])
def test_compile_expr_rejects_unknown_calls(text: str) -> None:
    with pytest.raises(S.ScriptError, match="unknown function"):
        S.compile_expr(text, 1)


@pytest.mark.parametrize("text", ["hp.real", "x[0]", "lambda: 1", "[1, 2]", "(1, 2)", "{1: 2}",
                                  "1 if x else 2", "f'{x}'", "[x for x in y]"])
def test_compile_expr_rejects_other_syntax(text: str) -> None:
    with pytest.raises(S.ScriptError, match="not allowed"):
        S.compile_expr(text, 1)


@pytest.mark.parametrize("text", ["x := 1", "*x", "x = 1"])
def test_compile_expr_rejects_broken_syntax(text: str) -> None:
    with pytest.raises(S.ScriptError, match="can't read this expression"):
        S.compile_expr(text, 1)


# ---------------------------------------------------------------- evaluate
def lowest(a: float, b: float) -> float:
    """random(a, b) that always answers a."""
    return a


def ev(text: str, names: dict[str, Any] | None = None, funcs: dict[str, Callable[..., Any]] | None = None) -> Any:
    names = names if names is not None else {"hp": 50, "mp": 10, "x": 3}
    funcs = funcs if funcs is not None else {"bag": returning(2), "min": min, "max": max, "abs": abs,
                                             "round": round, "int": int, "random": lowest}
    return S.evaluate(S.compile_expr(text, 1), names, funcs)


def test_evaluate_arithmetic_and_precedence() -> None:
    assert ev("1 + 2 * 3") == 7
    assert ev("(1 + 2) * 3") == 9
    assert ev("7 // 2") == 3
    assert ev("7 % 3") == 1


def test_evaluate_booleans_and_names() -> None:
    assert ev("hp > 40 and mp < 20") is True
    assert ev("hp > 100 or mp < 20") is True
    assert ev("not (hp > 100)") is True
    assert ev("true and not false") is True
    assert ev("True") is True
    assert ev("False") is False


def test_evaluate_unary_and_compare_chain() -> None:
    assert ev("-x") == -3
    assert ev("+x") == 3
    assert ev("1 < x < 5") is True
    assert ev("1 < x < 2") is False
    assert ev("x == 3 != 4") is True


def test_evaluate_calls_a_function() -> None:
    assert ev('bag("Milkfish")') == 2
    assert ev("min(3, 1)") == 1


def test_evaluate_an_unknown_name_raises_keyerror() -> None:
    with pytest.raises(KeyError):
        ev("nope")


def test_evaluate_refuses_to_multiply_text() -> None:
    with pytest.raises(ValueError):
        ev("'a' * 3")
    with pytest.raises(ValueError):
        ev("3 * 'a'")


def test_evaluate_an_unsupported_node_raises() -> None:
    node = ast.parse("[1]", mode="eval").body
    with pytest.raises(ValueError):
        S.evaluate(node, {}, {})


# ---------------------------------------------------------------- _Lazy
def test_lazy_works_out_the_value_on_demand() -> None:
    lz = S._Lazy(lambda: 5)
    assert lz.get() == 5
    assert lz < 6 and lz <= 5 and lz > 4 and lz >= 5 and lz == 5 and lz != 6
    assert (lz + 1) == 6 and (1 + lz) == 6 and (lz - 1) == 4 and (1 - lz) == -4
    assert int(lz) == 5 and str(lz) == "5" and bool(lz) is True


def test_lazy_zero_is_falsy() -> None:
    assert bool(S._Lazy(lambda: 0)) is False


# ---------------------------------------------------------------- parse: good
def test_parse_simple_commands() -> None:
    main, subs, on_stop = S.parse("wait 2\nsay hi\n")
    assert kinds(main) == ["wait", "say"]
    assert subs == {} and on_stop == []
    assert main[0].opts["secs"] == 2.0


def test_parse_ignores_comments_and_blank_lines() -> None:
    main, _, _ = S.parse("# leading\n\n   \nwait 1 # trailing\n")
    assert kinds(main) == ["wait"]


def test_parse_repeat_with_a_count() -> None:
    main, _, _ = S.parse("repeat 3\nwait 1\nend")
    assert main[0].kind == "repeat"
    assert main[0].opts["times"] == 3
    assert kinds(main[0].body) == ["wait"]


def test_parse_repeat_forever() -> None:
    main, _, _ = S.parse("repeat\nwait 1\nend")
    assert main[0].opts["times"] is None


def test_parse_while() -> None:
    main, _, _ = S.parse("while kills < 5\nsay x\nend")
    assert main[0].kind == "while"
    assert main[0].expr is not None
    assert kinds(main[0].body) == ["say"]


def test_parse_if_elif_else() -> None:
    main, _, _ = S.parse("if kills > 5\nsay a\nelif kills > 2\nsay b\nelse\nsay c\nend")
    node = main[0]
    assert node.kind == "if"
    assert len(node.branches) == 3
    assert node.branches[0][0] is not None and kinds(node.branches[0][1]) == ["say"]
    assert node.branches[1][0] is not None and kinds(node.branches[1][1]) == ["say"]
    assert node.branches[2][0] is None


def test_parse_if_without_else() -> None:
    main, _, _ = S.parse("if kills > 5\nsay a\nend")
    assert len(main[0].branches) == 1


def test_parse_nested_blocks() -> None:
    main, _, _ = S.parse("repeat 2\nwhile kills < 1\nbreak\nend\nend")
    assert main[0].kind == "repeat"
    assert main[0].body[0].kind == "while"
    assert main[0].body[0].body[0].kind == "break"


def test_parse_sub_and_call() -> None:
    main, subs, _ = S.parse("sub greet\nsay hi\nend\ncall greet")
    assert list(subs) == ["greet"]
    assert kinds(subs["greet"]) == ["say"]
    assert main[0].kind == "call"


def test_parse_call_to_an_unknown_sub_in_on_stop() -> None:
    with pytest.raises(S.ScriptError, match="no sub named"):
        S.parse("on_stop\ncall nope\nend")


def test_parse_on_stop() -> None:
    main, _, on_stop = S.parse("on_stop\nsay bye\nend\nwait 1")
    assert kinds(on_stop) == ["say"]
    assert kinds(main) == ["wait"]


def test_parse_two_on_stop_blocks_extend() -> None:
    _, _, on_stop = S.parse("on_stop\nsay a\nend\non_stop\nsay b\nend")
    assert [n.args for n in on_stop] == ["a", "b"]


def test_parse_break_inside_an_if_inside_a_loop_is_allowed() -> None:
    main, _, _ = S.parse("repeat 2\nif kills > 0\nbreak\nend\nend")
    assert kinds(main[0].body[0].body) == ["break"]


# ---------------------------------------------------------------- parse: bad
def test_parse_unknown_command() -> None:
    with pytest.raises(S.ScriptError, match="unknown command"):
        S.parse("frobnicate 1")


def test_parse_end_without_a_block() -> None:
    with pytest.raises(S.ScriptError, match="without a block"):
        S.parse("end")


def test_parse_elif_outside_an_if() -> None:
    with pytest.raises(S.ScriptError, match="outside an if"):
        S.parse("elif kills > 1\nend")


def test_parse_nothing_after_else() -> None:
    with pytest.raises(S.ScriptError, match="nothing can follow 'else'"):
        S.parse("if kills > 1\nelse\nsay a\nelif kills > 2\nend")


def test_parse_sub_inside_a_block() -> None:
    with pytest.raises(S.ScriptError, match="top level"):
        S.parse("repeat 2\nsub x\nend\nend")


def test_parse_sub_needs_a_name() -> None:
    with pytest.raises(S.ScriptError, match="a sub needs a name"):
        S.parse("sub\nsay a\nend")


def test_parse_unclosed_block() -> None:
    with pytest.raises(S.ScriptError, match="has no 'end'"):
        S.parse("repeat 3\nwait 1")


def test_parse_break_outside_a_loop() -> None:
    with pytest.raises(S.ScriptError, match="outside a repeat or while"):
        S.parse("break")


def test_parse_call_to_an_unknown_sub() -> None:
    with pytest.raises(S.ScriptError, match="no sub named"):
        S.parse("call nope")


def test_parse_repeat_needs_a_number() -> None:
    with pytest.raises(S.ScriptError, match="must be a number"):
        S.parse("repeat lots\nend")


@pytest.mark.parametrize("text", ["set 1x = 2", "set x 2", "set x =", "set hp = 2"])
def test_parse_bad_set(text: str) -> None:
    with pytest.raises(S.ScriptError):
        S.parse(text)


def test_parse_set_reserved_variable_message() -> None:
    with pytest.raises(S.ScriptError, match="can't be set"):
        S.parse("set hp = 2")


def test_parse_unbalanced_quotes() -> None:
    with pytest.raises(S.ScriptError, match="unbalanced quotes"):
        S.parse('talk "Bob')


# ---------------------------------------------------------------- parse: commands' options
def test_parse_travel_and_cell() -> None:
    main, _, _ = S.parse("travel 5121 at 5,6")
    assert main[0].opts["map"] == 5121 and main[0].opts["cell"] == (5, 6)


def test_parse_travel_unknown_map() -> None:
    with pytest.raises(S.ScriptError, match="unknown map"):
        S.parse("travel Nowhereland")


def test_parse_go_map_and_npc() -> None:
    main, _, _ = S.parse("go 5121 to Bob")
    assert main[0].opts["map"] == 5121 and main[0].opts["npc"] == "Bob"
    main, _, _ = S.parse("go 5121")
    assert main[0].opts["map"] == 5121 and main[0].opts["npc"] is None


def test_parse_go_dungeon_unknown() -> None:
    with pytest.raises(S.ScriptError, match="no known entrance"):
        S.parse("go dungeon No Such Dungeon")


def test_parse_follow_and_errors() -> None:
    main, _, _ = S.parse("follow Bob")
    assert main[0].opts["player"] == "Bob"
    with pytest.raises(S.ScriptError, match="whom"):
        S.parse("follow")


def test_parse_come_with_map() -> None:
    main, _, _ = S.parse("come Bob 5121")
    assert main[0].opts["player"] == "Bob" and main[0].opts["map"] == 5121


def test_parse_talk() -> None:
    main, _, _ = S.parse("talk Bob at 1,2")
    assert main[0].opts["npc"] == "Bob" and main[0].opts["cell"] == (1, 2)
    with pytest.raises(S.ScriptError, match="talk to whom"):
        S.parse("talk")


def test_parse_survey_scopes() -> None:
    assert S.parse("survey")[0][0].opts["scope"] == "cities"
    assert S.parse("survey all")[0][0].opts["scope"] == "all"
    assert S.parse("survey here")[0][0].opts["scope"] == "here"
    assert S.parse("survey 5121")[0][0].opts["scope"] == [5121]
    with pytest.raises(S.ScriptError, match="survey"):
        S.parse("survey nowhere")


@pytest.mark.parametrize("text", ["gem_maker", "gem_maker check", "enhance", "enhance check"])
def test_parse_gem_maker_and_enhance(text: str) -> None:
    main, _, _ = S.parse(text)
    assert main[0].opts["check"] == text.endswith("check")


def test_parse_gem_maker_rejects_other_words() -> None:
    with pytest.raises(S.ScriptError, match="write it as"):
        S.parse("gem_maker now")


def test_parse_visit() -> None:
    assert S.parse("visit storehouse")[0][0].opts["what"] == "storehouse"
    with pytest.raises(S.ScriptError, match="visit what"):
        S.parse("visit")


def test_parse_buy_and_withdraw() -> None:
    main, _, _ = S.parse("buy 5 Milkfish")
    assert main[0].opts == {"count": 5, "item": "Milkfish"}
    main, _, _ = S.parse('withdraw 2 "Large Red Potion"')
    assert main[0].opts == {"count": 2, "item": "Large Red Potion"}
    with pytest.raises(S.ScriptError, match="write it as"):
        S.parse("buy Milkfish")


def test_parse_sell_and_deposit() -> None:
    main, _, _ = S.parse("sell Milkfish")
    assert main[0].opts == {"item": "Milkfish", "count": None}
    main, _, _ = S.parse("sell Milkfish 20")
    assert main[0].opts == {"item": "Milkfish", "count": 20}
    with pytest.raises(S.ScriptError, match="write it as"):
        S.parse("sell")


def test_parse_choose_text_and_pattern() -> None:
    assert S.parse("choose Tulip City")[0][0].opts["pattern"] == "Tulip\\ City"
    assert S.parse("choose /Tulip/")[0][0].opts["pattern"] == "Tulip"
    with pytest.raises(S.ScriptError, match="choose what"):
        S.parse("choose")
    with pytest.raises(S.ScriptError, match="bad pattern"):
        S.parse("choose /[/")


def test_parse_walk() -> None:
    assert S.parse("walk 5 6")[0][0].opts["cell"] == (5, 6)
    assert S.parse("walk 5,6")[0][0].opts["cell"] == (5, 6)
    with pytest.raises(S.ScriptError, match="walk x y"):
        S.parse("walk 5")


def test_parse_key_and_hold() -> None:
    main, _, _ = S.parse("key a")
    assert main[0].opts == {"key": "a", "ms": 60}
    main, _, _ = S.parse("key A 100")
    assert main[0].opts == {"key": "a", "ms": 100}
    with pytest.raises(S.ScriptError, match="which key"):
        S.parse("key")
    main, _, _ = S.parse("hold w 2")
    assert main[0].opts == {"key": "w", "secs": 2.0}
    with pytest.raises(S.ScriptError, match="hold key seconds"):
        S.parse("hold w")


def test_parse_wait() -> None:
    assert S.parse("wait 2.5")[0][0].opts["secs"] == 2.5
    with pytest.raises(S.ScriptError, match="must be a number"):
        S.parse("wait soon")


# ---------------------------------------------------------------- parse: farm
def test_parse_farm_no_options() -> None:
    assert S.parse("farm")[0][0].opts == {}


def test_parse_farm_numbers_and_map() -> None:
    opts = S.parse("farm map=5121 minutes=5 kills=10")[0][0].opts
    assert opts["map"] == 5121 and opts["minutes"] == 5.0 and opts["kills"] == 10.0


def test_parse_farm_area_is_normalised() -> None:
    assert S.parse("farm area=5,4,1,2")[0][0].opts["area"] == [1, 2, 5, 4]
    with pytest.raises(S.ScriptError, match="four numbers"):
        S.parse("farm area=1,2,3")


def test_parse_farm_bad_option() -> None:
    with pytest.raises(S.ScriptError, match="doesn't know"):
        S.parse("farm bogus=1")


def test_parse_farm_bad_patrol_and_elites() -> None:
    with pytest.raises(S.ScriptError, match="patrol is"):
        S.parse("farm patrol=sprint")
    with pytest.raises(S.ScriptError, match="elites is"):
        S.parse("farm elites=maybe")
    assert S.parse("farm patrol=short elites=avoid")[0][0].opts["patrol"] == "short"


def test_parse_farm_bad_name_pattern() -> None:
    with pytest.raises(S.ScriptError, match="valid name pattern"):
        S.parse("farm only=[a-z")


def test_parse_farm_unknown_map() -> None:
    with pytest.raises(S.ScriptError, match="unknown map"):
        S.parse("farm map=nowhere minutes=1")


def test_parse_farm_until_takes_the_rest_of_the_line() -> None:
    opts = S.parse("farm minutes=5 until=kills >= 100")[0][0].opts
    assert opts["minutes"] == 5.0 and opts["until"] is not None
    with pytest.raises(S.ScriptError, match="until= needs a condition"):
        S.parse("farm until=")


# ---------------------------------------------------------------- parse: say / end_at
def test_parse_say_splits_out_expressions() -> None:
    parts = S.parse("say hello {kills} world")[0][0].opts["parts"]
    assert len(parts) == 3 and parts[0] == "hello " and parts[2] == " world"
    assert not isinstance(parts[1], str)


@pytest.mark.parametrize("word", ["start", "safe", "hearthstone", "here"])
def test_parse_end_at_words(word: str) -> None:
    assert S.parse("end_at " + word)[0][0].opts["end"] == (word,)


def test_parse_end_at_map_and_cell() -> None:
    assert S.parse("end_at 5121 at 1,2")[0][0].opts["end"] == ("place", 5121, (1, 2))


def test_parse_end_at_bad() -> None:
    with pytest.raises(S.ScriptError, match="end_at takes"):
        S.parse("end_at nowhereland")


# ---------------------------------------------------------------- check()
@pytest.mark.parametrize("text", ["wait 1", "repeat 3\nwait 1\nend", "sub a\nsay b\nend\ncall a",
                                  "on_stop\nstop\nend", "if kills > 1\nsay a\nelse\nsay b\nend",
                                  "repeat 2\nif kills > 1\nbreak\nend\nend"])
def test_check_accepts_good_scripts(text: str) -> None:
    assert S.check(text) is None


def test_check_reports_bad_scripts() -> None:
    msg = S.check("frobnicate")
    assert msg and "unknown command" in msg and "line 1" in msg


def test_login_is_a_first_line_directive() -> None:
    assert S.login_target('login "Hero - S1"\nfarm minutes=1') == "Hero - S1"
    assert S.check('farm minutes=1\nlogin "Hero - S1"') == "line 2: login must be the first command in a script"
    assert S.check('sub again\nlogin Hero\nend') == "line 2: login must be the first command in a script"


def test_check_reports_the_offending_line() -> None:
    msg = S.check("wait 1\nwait two")
    assert msg and "line 2" in msg


# ---------------------------------------------------------------- Runner: names / value
def test_names_reports_the_world() -> None:
    bot = FakeBot(kills=7, minutes=2.5)
    run = S.Runner(as_bot(bot), "")
    names = run.names()
    assert names["kills"] == 7 and names["minutes"] == 2.5
    assert names["hp"] == 50 and names["maxhp"] == 100 and names["hp_pct"] == 50.0
    assert names["mp"] == 20 and names["maxmp"] == 40 and names["mp_pct"] == 50.0
    assert names["level"] == 10
    assert names["map"] == 5121 and names["map_name"] == "Wolf Prairie"
    assert (names["x"], names["y"]) == (1, 2)
    assert isinstance(names["monsters"], S._Lazy)


def test_names_uses_mp_now_when_the_game_answers() -> None:
    bot = FakeBot(mps=(10, 10))
    names = S.Runner(as_bot(bot), "").names()
    assert names["mp"] == 10 and names["mp_pct"] == 100.0


def test_value_works_out_a_lazy_monsters_count() -> None:
    bot = FakeBot(targets=[1, 2, 3])
    run = S.Runner(as_bot(bot), "")
    assert run.value(S.compile_expr("monsters", 1), 1) == 3


def test_names_reads_the_tally_results() -> None:
    class Tally:
        def result(self) -> dict[str, Any]:
            return {"arnebia": 12, "contribution": 34, "experience": 500, "levels": 2,
                    "picked": {"Green Shard": 3, "Ruby Shard": 2, "Bread": 7}}       # thrown ones still count

    names = S.Runner(as_bot(FakeBot(tally=Tally())), "").names()
    assert names["arnebia_gained"] == 12 and names["contribution_gained"] == 34
    assert names["xp_gained"] == 500 and names["levels_gained"] == 2
    assert names["shards_gained"] == 5


# ---------------------------------------------------------------- Runner: bag()
def test_bag_counts_an_exact_match() -> None:
    run = S.Runner(as_bot(FakeBot()), "")
    assert run.funcs()["bag"]("Milkfish") == 3


def test_bag_falls_back_to_a_substring_match() -> None:
    run = S.Runner(as_bot(FakeBot()), "")
    assert run.funcs()["bag"]("fish") == 4


def test_bag_returns_zero_when_the_read_fails() -> None:
    run = S.Runner(as_bot(FakeBot(bag={"error": "no bag"})), "")
    assert run.funcs()["bag"]("Milkfish") == 0


# ---------------------------------------------------------------- Runner: running blocks
def test_run_set_and_say() -> None:
    bot = FakeBot()
    S.Runner(as_bot(bot), "set n = 2\nsay n is {n + 1}").run()
    assert ("n is 3", True) in bot.logs


def test_run_if_elif_else_picks_the_matching_branch() -> None:
    bot = FakeBot(kills=3)
    S.Runner(as_bot(bot), "if kills > 5\nsay many\nelif kills > 2\nsay some\nelse\nsay few\nend").run()
    assert "some" in loglines(bot) and "many" not in loglines(bot)


def test_run_while_loops_until_false() -> None:
    bot = FakeBot()
    run = S.Runner(as_bot(bot), "set i = 0\nwhile i < 3\nset i = i + 1\nend")
    run.run()
    assert run.vars["i"] == 3
    assert any(c[0] == "sleep" for c in bot.calls)


def test_run_repeat_breaks_out() -> None:
    bot = FakeBot()
    run = S.Runner(as_bot(bot), "set i = 0\nrepeat 5\nset i = i + 1\nif i >= 2\nbreak\nend\nend")
    run.run()
    assert run.vars["i"] == 2


def test_run_calls_a_sub() -> None:
    bot = FakeBot()
    run = S.Runner(as_bot(bot), "sub add\nset n = n + 1\nend\nset n = 0\ncall add\ncall add")
    run.run()
    assert run.vars["n"] == 2


def test_run_on_stop_runs_after_a_normal_end() -> None:
    bot = FakeBot()
    S.Runner(as_bot(bot), "on_stop\nsay bye\nend\nsay hi").run()
    assert "bye" in loglines(bot) and "hi" in loglines(bot)
    assert bot.watches == []


def test_run_stop_ends_the_script_and_still_runs_on_stop() -> None:
    bot = FakeBot()
    S.Runner(as_bot(bot), "on_stop\nsay bye\nend\nstop all done").run()
    assert "all done" in loglines(bot) and "bye" in loglines(bot)


def test_run_stop_when_registers_a_watch() -> None:
    bot = FakeBot(kills=3)
    run = S.Runner(as_bot(bot), "stop_when kills >= 10 : too many\nsay ok")
    run.run()
    assert len(bot.watches) == 1
    cond, message = bot.watches[0]
    assert message == "too many" and cond() is False


def test_run_stop_when_defaults_its_message() -> None:
    bot = FakeBot()
    S.Runner(as_bot(bot), "stop_when kills >= 10").run()
    assert "stop rule" in bot.watches[0][1]


def _raises(exc: BaseException) -> Callable[..., NoReturn]:
    def fail(*_args: object, **_kwargs: object) -> NoReturn:
        raise exc
    return fail


Prepare = Callable[[pytest.MonkeyPatch, "FakeBot", S.Runner], object]   # what a failing command test sets up


def _failing(module: types.ModuleType, name: str, message: str) -> Prepare:
    def prepare(monkeypatch: pytest.MonkeyPatch, _bot: FakeBot, _runner: S.Runner) -> None:
        monkeypatch.setattr(module, name, _raises(Stopped(message)))
    return prepare


DISPATCH_ERRORS: list[tuple[str, str, Prepare, str]] = [
    ("go", "go dungeon active volcano",
     lambda monkeypatch, _bot, _runner: monkeypatch.setattr(S.dungeons, "find", stand_in(S.dungeons.find, lambda name: None)),
     "no known entrance for the dungeon active volcano"),
    ("talk", "talk Bob",
     lambda monkeypatch, bot, _runner: monkeypatch.setattr(bot, "talk", stand_in(bot.talk, lambda npc, cell=None: False)),
     "couldn't talk to Bob"),
    ("follow", "follow Bob", _failing(S.follow, "follow", "lost sight of Bob"), "lost sight of Bob"),
    ("come", "come Bob", _failing(S.follow, "come_to", "lost sight of Bob"), "lost sight of Bob"),
    ("visit", "visit storehouse",
     _failing(S.town, "visit", "I don't know where to find a storehouse"), "I don't know where to find a storehouse"),
    ("buy", "buy 2 Milkfish", _failing(S.town, "buy", "I don't know which shop sells Milkfish"),
     "I don't know which shop sells Milkfish"),
    ("sell", "sell Milkfish", _failing(S.town, "sell", "I don't know who buys Milkfish"),
     "I don't know who buys Milkfish"),
    ("choose", "choose Cake",
     lambda monkeypatch, bot, _runner: monkeypatch.setattr(bot, "choose", stand_in(bot.choose, lambda pattern: None)),
     'no menu entry like "Cake"'),
    ("gem_maker", "gem_maker", lambda _monkeypatch, bot, _runner: setattr(bot, "p", {}),
     "set it up first: Tools, Gem Maker"),
]


@pytest.mark.parametrize("name, text, prepare, message", DISPATCH_ERRORS,
                         ids=[row[0] for row in DISPATCH_ERRORS])
def test_each_script_command_reports_its_failure(monkeypatch: pytest.MonkeyPatch, name: str, text: str, prepare: Prepare, message: str) -> None:
    """Every dispatch branch that can fail tells the player why, instead of silently carrying on."""
    bot = FakeBot()
    runner = S.Runner(as_bot(bot), text)          # parse first: go dungeon needs the real entrance table
    prepare(monkeypatch, bot, runner)
    with pytest.raises(Stopped) as caught:
        runner.run()
    assert str(caught.value) == message


def test_run_commands_reach_the_bot() -> None:
    bot = FakeBot()
    script = "\n".join(["travel 5121 at 5,6", "go 5121 to Bob", "talk Bob", "choose Tulip",
                        "walk 3 4", "key a 100", "hold w 1", "heal", "hearthstone", "end_at start"])
    S.Runner(as_bot(bot), script).run()
    calls = bot.calls
    assert ("travel", 5121, (5, 6)) in calls
    assert ("go", 5121, None, "Bob", False) in calls
    assert ("talk", "Bob", None) in calls
    assert ("choose", "Tulip") in calls
    assert ("walk_to", (3, 4)) in calls
    assert ("key", "a", 100) in calls
    assert ("hold", "w") in calls and ("let_go", "w") in calls
    assert ("potion", "hp") in calls and ("drink", "hp", "Red Potion", "4") in calls
    assert ("go_home",) in calls
    assert bot.end_place == ("start",)


def test_run_farm_passes_its_options() -> None:
    bot = FakeBot()
    S.Runner(as_bot(bot), "farm map=5121 minutes=5 kills=10 area=1,2,3,4").run()
    kind, mid, kw = bot.calls[0]
    assert kind == "farm" and mid == 5121
    assert kw["minutes"] == 5.0 and kw["kills"] == 10.0 and kw["area"] == [1, 2, 3, 4]
    assert kw["until"] is None


def test_run_farm_until_passes_a_callable() -> None:
    bot = FakeBot(kills=4)
    S.Runner(as_bot(bot), "farm until=kills >= 3").run()
    until = bot.calls[0][2]["until"]
    assert until() is True


# ---------------------------------------------------------------- Runner: error paths
def test_value_unknown_name_stops_the_script() -> None:
    with pytest.raises(Stopped, match="has no value yet"):
        S.Runner(as_bot(FakeBot()), "say {nope}").run()


def test_value_division_by_zero_stops_the_script() -> None:
    with pytest.raises(Stopped):
        S.Runner(as_bot(FakeBot()), "say {1 / 0}").run()


def test_value_text_multiplication_stops_the_script() -> None:
    with pytest.raises(Stopped):
        S.Runner(as_bot(FakeBot()), "say {'a' * 3}").run()


def test_runner_leaves_after_three_respawns(monkeypatch: pytest.MonkeyPatch) -> None:
    bot = FakeBot()

    def step(node: Node) -> None:
        raise Respawned

    run = S.Runner(as_bot(bot), "wait 1")
    monkeypatch.setattr(run, "step", step)
    with pytest.raises(Stopped, match="died every time"):
        run.run()


# ---------------------------------------------------------------- resource limits
def test_compile_expr_rejects_too_many_parts() -> None:
    with pytest.raises(S.ScriptError, match="too complex"):
        S.compile_expr(" + ".join(["1"] * 400), 1)


def test_compile_expr_rejects_too_long_text() -> None:
    with pytest.raises(S.ScriptError, match="too long"):
        S.compile_expr("1" + " + 1" * 2000, 1)


def test_compile_expr_rejects_a_huge_integer() -> None:
    with pytest.raises(S.ScriptError, match="too large"):
        S.compile_expr("9" * 2000, 1)


def test_parse_rejects_deeply_nested_blocks() -> None:
    script = "\n".join(["if kills > 1"] * (S.MAX_BLOCK_DEPTH + 5) + ["say x"]
                       + ["end"] * (S.MAX_BLOCK_DEPTH + 5))
    with pytest.raises(S.ScriptError, match="nested too deeply"):
        S.parse(script)


def test_parse_rejects_a_self_calling_sub() -> None:
    with pytest.raises(S.ScriptError, match="recursion"):
        S.parse("sub a\ncall a\nend")


def test_parse_rejects_mutual_recursion() -> None:
    with pytest.raises(S.ScriptError, match="recursion"):
        S.parse("sub a\ncall b\nend\nsub b\ncall a\nend")


def test_parse_rejects_a_too_long_script(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(S, "MAX_SCRIPT", 20)
    with pytest.raises(S.ScriptError, match="too long"):
        S.parse("wait 1\nsay a much longer line than twenty characters")


def test_value_rejects_a_huge_number() -> None:
    run = S.Runner(as_bot(FakeBot()), "")
    run.vars["big"] = 2 ** (S.MAX_INT_BITS + 1)
    with pytest.raises(S.Stopped, match="number grew too large"):
        run.value(S.compile_expr("big", 1), 1)


def test_value_rejects_a_huge_string() -> None:
    run = S.Runner(as_bot(FakeBot()), "")
    run.vars["big"] = "a" * (S.MAX_TEXT + 1)
    with pytest.raises(S.Stopped, match="text grew too large"):
        run.value(S.compile_expr("big", 1), 1)


def test_stop_when_in_a_loop_adds_one_watcher() -> None:
    bot = FakeBot()
    S.Runner(as_bot(bot), "repeat 5\nstop_when kills >= 1\nend").run()
    assert len(bot.watches) == 1


def test_calls_are_bounded_at_run_time() -> None:
    lines: list[str] = []
    for i in range(S.MAX_CALL_DEPTH + 10):
        lines.append("sub s%d" % i)
        lines.append("call s%d" % (i + 1) if i < S.MAX_CALL_DEPTH + 9 else "say end")
        lines.append("end")
    lines.append("call s0")
    with pytest.raises(S.Stopped, match="nested more than"):
        S.Runner(as_bot(FakeBot()), "\n".join(lines)).run()


def test_parse_keep_drop_takes_minutes_only() -> None:
    assert S.parse("keep_drop 60")[0][0].opts["minutes"] == 60
    for bad in ("keep_drop", "keep_drop an hour", "keep_drop 5000"):
        with pytest.raises(S.ScriptError):
            S.parse(bad)
