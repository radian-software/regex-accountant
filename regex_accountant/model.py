from dataclasses import dataclass
from datetime import datetime
import logging
from typing import Tuple


import regex_accountant.fetcher_api as api
from regex_accountant.utils import asdate


@dataclass
class StagedTransactions:
    account: str
    start_date: datetime
    end_date: datetime
    txns: list[api.Transaction]


@dataclass
class TransactionSet:
    txns: list[api.Transaction]
    start_date: datetime
    end_date: datetime

    def _find_shared_slice(
        self, txns: list[api.Transaction], shared_ids: set[str]
    ) -> Tuple[int, int]:
        min_idx = len(txns)
        max_idx = -1
        for idx, txn in enumerate(txns):
            if txn.source_uid in shared_ids:
                min_idx = min(min_idx, idx)
                max_idx = max(max_idx, idx)
        assert min_idx < len(txns) and max_idx + 1 > -1
        return min_idx, max_idx + 1

    def import_transactions(
        self, txns: list[api.Transaction], start_date: datetime, end_date: datetime
    ) -> None:
        if not txns:
            logging.info(f"No transactions to import")
            return
        assert start_date < end_date
        if end_date < self.start_date:
            raise RuntimeError(
                f"need to first import transactions from {asdate(end_date)} to {asdate(self.start_date)}"
            )
        if start_date > self.end_date:
            raise RuntimeError(
                f"need to first import transactions from {asdate(self.end_date)} to {asdate(start_date)}"
            )
        self.start_date = min(self.start_date, start_date)
        self.end_date = max(self.end_date, end_date)
        known_ids = {txn.source_uid for txn in self.txns}
        new_ids = {txn.source_uid for txn in txns}
        shared_ids = known_ids & new_ids
        orig_txns = {txn.source_uid: txn for txn in self.txns}
        if not shared_ids:
            if start_date >= self.end_date:
                self.txns = self.txns + txns
            elif end_date <= self.start_date:
                self.txns = txns + self.txns
            else:
                raise RuntimeError
        else:
            replacement_start, replacement_end = self._find_shared_slice(
                self.txns, shared_ids
            )
            self.txns = (
                self.txns[:replacement_start] + txns + self.txns[replacement_end:]
            )
        final_ids = {txn.source_uid for txn in self.txns}
        retained_ids = known_ids & final_ids
        changed_ids = {
            txn.source_uid: txn
            for txn in self.txns
            if txn.source_uid in retained_ids and txn != orig_txns[txn.source_uid]
        }
        logging.info(
            f"Transaction import added {len(final_ids - known_ids)}, removed {len(known_ids - final_ids)}, updated {len(changed_ids)}, kept {len(retained_ids) - len(changed_ids)}"
        )


class TransactionStore:
    accts: dict[str, TransactionSet] = {}

    def import_transactions(self, staged: StagedTransactions):
        if ts := self.accts.get(staged.account):
            ts.import_transactions(staged.txns, staged.start_date, staged.end_date)
        else:
            self.accts[staged.account] = TransactionSet(
                txns=staged.txns, start_date=staged.start_date, end_date=staged.end_date
            )
            logging.info(f"Transaction import added {len(staged.txns)} for new account")
