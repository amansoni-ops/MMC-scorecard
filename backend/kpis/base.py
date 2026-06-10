from abc import ABC, abstractmethod

class BaseKPI(ABC):
    @abstractmethod
    def fetch(self, month: int, year: int) -> list[dict]:
        """Fetch raw rows for month/year. Each row must have AdminID, EmployeeName."""
        pass

    @abstractmethod
    def aggregate(self, rows: list[dict]) -> dict:
        """
        Aggregate rows for ONE employee.
        Returns:
            numerator     : int
            denominator   : int
            success_ratio : float | None  (0-100)
            orders        : list[dict]    (drill-down detail)
        """
        pass
