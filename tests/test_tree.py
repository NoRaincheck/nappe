from theseus_ship.tree import NodeInfo, ParseResult, TransformCandidate, TransformKind


class TestNodeInfo:
    def test_construction(self) -> None:
        node = NodeInfo(
            kind="function_definition",
            byte_start=0,
            byte_end=14,
            token_count=5,
            has_errors=False,
            child_kinds=("identifier", "block"),
        )
        assert node.kind == "function_definition"
        assert node.byte_start == 0
        assert node.byte_end == 14
        assert node.token_count == 5
        assert node.has_errors is False
        assert node.child_kinds == ("identifier", "block")

    def test_frozen(self) -> None:
        node = NodeInfo("if_statement", 0, 10, 3, False, ("block",))
        try:
            node.kind = "other"  # type: ignore[misc]
            assert False, "Should be frozen"
        except AttributeError:
            pass

    def test_error_node(self) -> None:
        node = NodeInfo("ERROR", 5, 8, 1, True, ())
        assert node.has_errors is True


class TestTransformKind:
    def test_values(self) -> None:
        assert TransformKind.DELETE.value == "delete"
        assert TransformKind.UNWRAP.value == "unwrap"


class TestTransformCandidate:
    def test_delete_candidate(self) -> None:
        target = NodeInfo("pass_statement", 0, 4, 1, False, ())
        candidate = TransformCandidate(target=target, kind=TransformKind.DELETE)
        assert candidate.unwrap_child_index is None

    def test_unwrap_candidate(self) -> None:
        target = NodeInfo("parenthesized_expression", 0, 10, 3, False, ("integer",))
        NodeInfo("integer", 1, 2, 1, False, ())
        candidate = TransformCandidate(
            target=target, kind=TransformKind.UNWRAP, unwrap_child_index=0
        )
        assert candidate.unwrap_child_index == 0


class TestParseResult:
    def test_construction(self) -> None:
        root = NodeInfo("module", 0, 100, 20, False, ("function_definition",))
        nodes = [root]
        result = ParseResult(
            source_bytes=b"source",
            root_node=root,
            all_nodes=nodes,
            error_node_count=0,
        )
        assert result.source_bytes == b"source"
        assert result.error_node_count == 0
        assert len(result.all_nodes) == 1
