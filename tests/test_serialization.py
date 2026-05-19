"""
Edge-case tests for `pymol_plugin.serialize.serialize` and the wire-level
size cap enforced in `pymol_plugin.framing.send_message`.

We don't import optional deps (numpy, chempy) here. Instead, the numpy and
ChemPy branches are exercised by monkeypatching the `_maybe_*` helpers to
return stubs.
"""

from __future__ import annotations
import json
import socket
import struct
from types import SimpleNamespace
from typing import Any, cast

import pytest
from pymol_plugin import framing
from pymol_plugin import serialize as serialize_mod
from pymol_plugin.serialize import serialize


class TestPrimitives:
    @pytest.mark.parametrize(
        "value",
        [None, True, False, 0, 1, -1, 1.5, -3.14, "", "hello", "über"],
    )
    def test_passthrough(self, value: Any) -> None:
        assert serialize(value) == value
        assert isinstance(serialize(value), type(value))

    @pytest.mark.parametrize("v", [float("nan"), float("inf"), float("-inf")])
    def test_non_finite_floats_coerced_to_none(self, v: float) -> None:
        assert serialize(v) is None

    def test_non_finite_inside_list_coerced(self) -> None:
        assert serialize([1.0, float("nan"), 3.0]) == [1.0, None, 3.0]

    def test_non_finite_inside_dict_coerced(self) -> None:
        assert serialize({"a": float("inf"), "b": 2.0}) == {"a": None, "b": 2.0}

    def test_non_finite_inside_nested_structure_coerced(self) -> None:
        value = {"row": [(1.0, float("nan")), (float("-inf"), 4.0)]}
        assert serialize(value) == {"row": [[1.0, None], [None, 4.0]]}

    def test_serialized_payload_is_strict_json(self) -> None:
        """The whole point of the coercion: the resulting payload must round-trip
        through a strict JSON parser without emitting non-standard tokens."""
        out = serialize({"vals": [1.0, float("nan"), float("inf")]})
        body = json.dumps(out, allow_nan=False)
        assert json.loads(body) == {"vals": [1.0, None, None]}


class TestContainers:
    def test_list_recurses(self) -> None:
        assert serialize([1, "x", [2, 3]]) == [1, "x", [2, 3]]

    def test_tuple_becomes_list(self) -> None:
        assert serialize((1, 2, 3)) == [1, 2, 3]

    def test_dict_recurses_and_stringifies_keys(self) -> None:
        result = serialize({1: "a", "b": [2]})
        assert result == {"1": "a", "b": [2]}

    def test_nested_mixed_containers(self) -> None:
        value = {"a": [(1, 2), {"k": (3, 4)}], "b": [[5]]}
        assert serialize(value) == {"a": [[1, 2], {"k": [3, 4]}], "b": [[5]]}

    def test_empty_containers(self) -> None:
        assert serialize([]) == []
        assert serialize({}) == {}
        assert serialize(()) == []


class TestReprFallback:
    def test_unknown_object_uses_repr(self) -> None:
        class Widget:
            def __repr__(self) -> str:
                return "Widget(x=1)"

        result = serialize(Widget())
        assert result == {"_kind": "repr", "value": "Widget(x=1)"}

    def test_repr_truncates_at_2000_chars(self) -> None:
        class Big:
            def __repr__(self) -> str:
                return "x" * 5000

        result = serialize(Big())
        assert result["_kind"] == "repr"
        assert len(result["value"]) == 2000
        assert result["value"] == "x" * 2000

    def test_bytes_falls_to_repr(self) -> None:
        result = serialize(b"abc\xff")
        assert result["_kind"] == "repr"
        assert "abc" in result["value"]

    def test_bytearray_falls_to_repr(self) -> None:
        result = serialize(bytearray(b"hello"))
        assert result["_kind"] == "repr"


class TestNumpyBranch:
    def test_ndarray_serialized_as_envelope(self, monkeypatch: pytest.MonkeyPatch) -> None:
        class FakeArray:
            def __init__(self) -> None:
                self.shape = (2, 3)
                self.dtype = "float64"

            def tolist(self) -> list[list[float]]:
                return [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]

        fake_np = SimpleNamespace(ndarray=FakeArray)
        monkeypatch.setattr(serialize_mod, "_maybe_numpy", lambda: fake_np)

        result = serialize(FakeArray())
        assert result == {
            "_kind": "ndarray",
            "shape": [2, 3],
            "dtype": "float64",
            "data": [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]],
        }

    def test_non_ndarray_skips_numpy_branch(self, monkeypatch: pytest.MonkeyPatch) -> None:
        class FakeNdarray:
            pass

        fake_np = SimpleNamespace(ndarray=FakeNdarray)
        monkeypatch.setattr(serialize_mod, "_maybe_numpy", lambda: fake_np)

        assert serialize([1, 2, 3]) == [1, 2, 3]

    def test_ndarray_data_has_nan_coerced(self, monkeypatch: pytest.MonkeyPatch) -> None:
        class FakeArray:
            def __init__(self) -> None:
                self.shape = (3,)
                self.dtype = "float64"

            def tolist(self) -> list[float]:
                return [1.0, float("nan"), float("inf")]

        fake_np = SimpleNamespace(ndarray=FakeArray)
        monkeypatch.setattr(serialize_mod, "_maybe_numpy", lambda: fake_np)

        result = serialize(FakeArray())
        assert result["data"] == [1.0, None, None]


class TestChempyBranch:
    def test_indexed_model_serialized_with_atoms(self, monkeypatch: pytest.MonkeyPatch) -> None:
        class FakeIndexed:
            pass

        atom1 = SimpleNamespace(
            name="CA",
            resn="ALA",
            resi="1",
            chain="A",
            b=20.0,
            q=1.0,
            elem="C",
            coord=(1.0, 2.0, 3.0),
        )
        atom2 = SimpleNamespace(name="N", resn="ALA", resi="1", chain="A", coord=[4.0, 5.0, 6.0])
        model = FakeIndexed()
        model.atom = [atom1, atom2]  # type: ignore

        monkeypatch.setattr(serialize_mod, "_maybe_chempy_indexed", lambda: FakeIndexed)

        result = serialize(model)
        assert result["_kind"] == "model"
        assert result["n_atoms"] == 2
        atoms = result["atoms"]
        assert atoms[0]["name"] == "CA"
        assert atoms[0]["coord"] == [1.0, 2.0, 3.0]
        assert atoms[1]["coord"] == [4.0, 5.0, 6.0]
        assert "b" not in atoms[1]

    def test_atom_nan_b_factor_and_coord_coerced(self, monkeypatch: pytest.MonkeyPatch) -> None:
        class FakeIndexed:
            pass

        atom = SimpleNamespace(name="CA", b=float("nan"), coord=(1.0, float("inf"), 3.0))
        model = FakeIndexed()
        model.atom = [atom]  # type: ignore[attr-defined]

        monkeypatch.setattr(serialize_mod, "_maybe_chempy_indexed", lambda: FakeIndexed)

        result = serialize(model)
        assert result["atoms"][0]["b"] is None
        assert result["atoms"][0]["coord"] == [1.0, None, 3.0]

    def test_atom_with_no_recognized_fields_returns_empty_dict(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        class FakeIndexed:
            pass

        bare = SimpleNamespace()
        model = FakeIndexed()
        model.atom = [bare]  # type: ignore

        monkeypatch.setattr(serialize_mod, "_maybe_chempy_indexed", lambda: FakeIndexed)

        result = serialize(model)
        assert result["atoms"] == [{}]
        assert result["n_atoms"] == 1


class TestSendMessageSizeCap:
    """The 4 MB cap is enforced in framing.send_message; oversize payloads are
    replaced on the wire with a ResponseTooLarge error envelope."""

    def test_oversize_payload_is_replaced(self) -> None:
        oversized = {"ok": True, "value": "x" * (framing.MAX_MESSAGE_BYTES + 100), "stdout": ""}
        sock = _RecordingSocket()
        framing.send_message(cast(socket.socket, sock), oversized)
        body = _extract_body(sock.written)
        decoded = json.loads(body)
        assert decoded["ok"] is False
        assert decoded["error"]["type"] == "ResponseTooLarge"

    def test_at_limit_payload_passes_through(self) -> None:
        body_size = 1000
        payload = {"ok": True, "value": "y" * body_size, "stdout": ""}
        sock = _RecordingSocket()
        framing.send_message(cast(socket.socket, sock), payload)
        body = _extract_body(sock.written)
        decoded = json.loads(body)
        assert decoded["ok"] is True
        assert decoded["value"] == "y" * body_size

    def test_default_str_handler_used_for_unserializable(self) -> None:
        class Custom:
            def __repr__(self) -> str:
                return "<Custom>"

        sock = _RecordingSocket()
        payload = {"ok": True, "value": Custom(), "stdout": ""}
        framing.send_message(cast(socket.socket, sock), payload)
        body = _extract_body(sock.written)
        decoded = json.loads(body)
        assert decoded["value"] == "<Custom>"


class _RecordingSocket:
    def __init__(self) -> None:
        self.written = bytearray()

    def sendall(self, data: bytes) -> None:
        self.written.extend(data)


def _extract_body(written: bytearray) -> bytes:
    (length,) = struct.unpack(">I", bytes(written[:4]))
    return bytes(written[4 : 4 + length])
