from pendulum_kit.stock import Spool, StockClient, check_stock


def test_not_running_is_reported():
    assert StockClient("http://127.0.0.1:1", timeout_s=0.5).is_alive() is False


def test_check_stock():
    s = {1: Spool(1, "PLA", "PLA", "000000", 1.24, 50.0)}
    assert check_stock({1: 40.0}, s) == []
    assert check_stock({1: 48.0}, s)      # 10 % margin
    assert check_stock({2: 1.0}, s)       # unknown spool
