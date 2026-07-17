from core.batch_contracts import parse_entry_batch_response


def test_contract_maps_reordered_ids_and_reports_unknown():
    response = '{"entries":[{"id":"2","summary":"second"},{"id":"1","summary":"first"},{"id":"x","summary":"bad"}]}'
    parsed = parse_entry_batch_response(response, {"1", "2"})
    assert list(parsed.valid) == ["2", "1"]
    assert parsed.unknown_ids == {"x"}


def test_contract_rejects_duplicate_and_missing():
    parsed = parse_entry_batch_response(
        '{"entries":[{"id":"1","summary":"a"},{"id":"1","summary":"b"}]}', {"1", "2"}
    )
    assert parsed.invalid_ids == {"1"} and parsed.missing_ids == {"2"}
