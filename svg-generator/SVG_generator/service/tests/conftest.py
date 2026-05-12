import pytest


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers", "integration: реальные LLM-вызовы, запускать только с --integration"
    )
    config.addinivalue_line(
        "markers", "benchmark: тесты качества SVG, запускать только с --benchmark"
    )


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--integration",
        action="store_true",
        default=False,
        help="Запустить интеграционные тесты с реальными LLM-вызовами (тратят токены)",
    )
    parser.addoption(
        "--benchmark",
        action="store_true",
        default=False,
        help="Запустить benchmark-тесты на сохранённых результатах из tests/benchmark/results/",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if not config.getoption("--integration"):
        skip_int = pytest.mark.skip(reason="Требует --integration для реальных LLM-вызовов")
        for item in items:
            if "integration" in item.keywords:
                item.add_marker(skip_int)
    if not config.getoption("--benchmark"):
        skip_bm = pytest.mark.skip(reason="Требует --benchmark для проверки сохранённых результатов")
        for item in items:
            if "benchmark" in item.keywords:
                item.add_marker(skip_bm)
