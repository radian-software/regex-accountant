from dataclasses import dataclass

from regex_accountant.fetcher_api import Transaction


@dataclass
class ExtTransaction(Transaction):
    account: str = ""

    @property
    def summary(self) -> str:
        s = self.description or self.description_short or self.description_details
        if part := (self.client or self.client_short):
            if self.amount > 0:
                s += f" to {part}"
            else:
                s += f" from {part}"
        if part := (
            self.payment_method or self.payment_method_short or self.payment_method_long
        ):
            s += f" via {part}"
        return s
