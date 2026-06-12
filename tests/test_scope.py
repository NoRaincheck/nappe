import pytest

from nappe.scope import ScopeData, find_dead_definitions, load_scope, unify_identifiers


class TestScopeStub:
    def test_load_scope_raises(self) -> None:
        with pytest.raises(NotImplementedError):
            load_scope("locals.scm")

    def test_find_dead_definitions_empty(self) -> None:
        scope = ScopeData(bindings={}, references={})
        assert find_dead_definitions(b"code", scope) == []

    def test_unify_identifiers_empty(self) -> None:
        scope = ScopeData(bindings={}, references={})
        assert unify_identifiers(b"code", scope) == {}
