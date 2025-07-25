
from dataclasses import dataclass
import uuid

@dataclass(frozen=True)
class EmployeeId:
    """Типобезопасный ID сотрудника."""
    value: uuid.UUID

    @staticmethod
    def new_id() -> "EmployeeId":
        return EmployeeId(value=uuid.uuid4())

@dataclass(frozen=True)
class PayrollId:
    """Типобезопасный ID расчетного листа."""
    value: uuid.UUID

    @staticmethod
    def new_id() -> "PayrollId":
        return PayrollId(value=uuid.uuid4())
