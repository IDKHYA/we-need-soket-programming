from vending_machine.domain.change import ChangeCalculator


def test_change_calculator_exact_change():
    calc = ChangeCalculator()
    result = calc.calculate(
        amount=760,
        available={1000: 0, 500: 1, 100: 2, 50: 1, 10: 1},
    )
    assert result == {500: 1, 100: 2, 50: 1, 10: 1}
