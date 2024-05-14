import abc
import bdb
import collections
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
import inspect
import logging
import pdb
import time
import traceback
import typing

from selenium import webdriver
from selenium.webdriver.remote.webdriver import WebDriver

from regex_accountant.utils import normalize_date


@dataclass
class Config(abc.ABC):
    pass


@dataclass
class Session(abc.ABC):
    pass


CT = typing.TypeVar("CT", bound=Config)
ST = typing.TypeVar("ST", bound=Session)


class Context(typing.Generic[CT, ST]):
    def __init__(self, config: CT, session: ST | None, debug: bool):
        self.config = config
        self.session = session
        self.debug = debug
        self._browser = None

    @property
    def browser(self) -> WebDriver:
        if not self._browser:
            self._browser = webdriver.Firefox()
        return self._browser

    def close_browser(self) -> None:
        if self._browser:
            self._browser.close()
            self._browser = None


class FlowState(abc.ABC):
    @abc.abstractmethod
    def detect(self, ctx: Context) -> typing.Any:
        pass

    @abc.abstractmethod
    def act(self, ctx: Context) -> None:
        pass


class Flow(abc.ABC):
    def __init__(self):
        self.states = []
        for attr in self.__dir__():
            if not hasattr(self.__class__, attr):
                continue
            state = getattr(self.__class__, attr)
            if inspect.isclass(state) and issubclass(state, FlowState):
                self.states.append(state())  # type: ignore
        if not self.states:
            raise Exception(f"Flow {self.__class__} does not define any states")

    def detect(self, ctx: Context) -> FlowState:
        for state in self.states:
            try:
                if state.detect(ctx):
                    return state
            except Exception:
                pass
        raise Exception(f"Flow {self.__class__} does not define a default state")

    def traverse(
        self,
        ctx: Context,
        destination: typing.Type[FlowState],
    ) -> None:
        state_history = []
        seen_states = collections.Counter()
        try:
            while True:
                state = self.detect(ctx)
                logging.info(
                    f"Traversal for {self.__class__}: State {state.__class__.__name__}"
                )
                if isinstance(state, destination):
                    return
                state_history.append(state.__class__.__name__)
                seen_states[state.__class__.__name__] += 1
                [(_, highest_count)] = seen_states.most_common(1)
                if highest_count >= 3:
                    raise Exception(
                        f"Flow {self.__class__} went into an infinite loop: {state_history}"
                    )
                state.act(ctx)
                time.sleep(3)
        except Exception:
            if ctx.debug:
                traceback.print_exc()
                try:
                    pdb.set_trace()
                except bdb.BdbQuit:
                    pass
            raise


@dataclass
class Transaction:
    date_posted: datetime
    date_cleared: datetime
    currency: str
    amount: Decimal
    source_uid: str
    description: str
    description_short: str = ""
    description_details: str = ""
    client: str = ""
    client_short: str = ""
    payment_method: str = ""
    payment_method_short: str = ""
    payment_method_long: str = ""
    account_id: str = ""

    def __post__init__(self):
        self.date_posted = normalize_date(self.date_posted)
        self.date_cleared = normalize_date(self.date_cleared)


@dataclass
class AccountTransaction(Transaction):
    account: str = ""


class Fetcher(abc.ABC):
    @abc.abstractmethod
    def authenticate(self, ctx: Context) -> Session:
        pass

    @abc.abstractmethod
    def check_auth(self, ctx: Context) -> typing.Any:
        pass

    @abc.abstractmethod
    def get_transactions(
        self, ctx: Context, start_date: datetime, end_date: datetime
    ) -> list[Transaction]:
        pass
