from config import get_sector_pe_median, parse_api_key_pool


def test_parse_api_key_pool_trims_and_discards_empty_values():
    assert parse_api_key_pool(" key1, ,key2 ,, key3 ") == ["key1", "key2", "key3"]


def test_parse_api_key_pool_handles_missing_value():
    assert parse_api_key_pool(None) == []
    assert parse_api_key_pool("") == []


def test_sector_pe_median_uses_known_sector_or_default():
    assert get_sector_pe_median("Technology") == 32
    assert get_sector_pe_median("Unknown Sector") == 20


def test_groq_model_constants_are_not_part_of_local_only_runtime_contract():
    import config

    assert not hasattr(config, "GROQ_PRIMARY_MODEL")
    assert not hasattr(config, "GROQ_FALLBACK_MODEL")


def test_dotenv_loading_is_enabled():
    import config

    assert config.DOTENV_ENABLED is True
