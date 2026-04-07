class DomainError(Exception):
    """Base domain error."""


class ProductNotFoundError(DomainError):
    def __init__(self, product_id: str):
        super().__init__(f"상품을 찾을 수 없습니다: {product_id}")


class OutOfStockError(DomainError):
    def __init__(self, product_name: str):
        super().__init__(f"재고가 부족합니다: {product_name}")


class InsufficientBalanceError(DomainError):
    def __init__(self, required: int, current: int):
        super().__init__(f"잔액이 부족합니다. 필요 금액={required}, 현재 금액={current}")


class ChangeUnavailableError(DomainError):
    def __init__(self, amount: int):
        super().__init__(f"정확한 거스름돈을 만들 수 없습니다. 금액={amount}")


class InvalidDenominationError(DomainError):
    def __init__(self, denomination: int):
        super().__init__(f"허용되지 않는 화폐 단위입니다: {denomination}")
