import abc
import collections
from dataclasses import dataclass
import inspect
import logging
import time
import typing

import requests
from selenium import webdriver


@dataclass
class Config(abc.ABC):
    pass


@dataclass
class Session(abc.ABC):
    pass


CT = typing.TypeVar("CT", bound=Config)
ST = typing.TypeVar("ST", bound=Session)


class Context(typing.Generic[CT, ST]):
    def __init__(self, config: CT, session: ST):
        self.config = config
        self.session = session
        self._browser = None

    @property
    def browser(self):
        if not self._browser:
            self._browser = webdriver.Firefox()
        return self._browser

    def close_browser(self):
        if self._browser:
            self._browser.close()
            self._browser = None


class FlowState(abc.ABC):
    @abc.abstractmethod
    def detect(self, ctx: Context):
        pass

    @abc.abstractmethod
    def act(self, ctx: Context):
        pass


class Flow(abc.ABC):
    def __init__(self):
        self.states = []
        for attr in dir(self.__class__):
            state = getattr(self.__class__, attr)
            if inspect.isclass(state) and issubclass(state, FlowState):
                self.states.append(state())  # type: ignore
        if not self.states:
            raise Exception(f"Flow {self.__class__} does not define any states")

    def detect(self, ctx: Context):
        for state in self.states:
            try:
                if state.detect(ctx):
                    return state
            except Exception:
                pass
        raise Exception(f"Flow {self.__class__} does not define a default state")

    def traverse(
        self,
        destination: typing.Type[FlowState],
        ctx: Context,
    ):
        state_history = []
        seen_states = collections.Counter()
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


class Fetcher(abc.ABC):
    @abc.abstractmethod
    def authenticate(self, ctx: Context) -> Session:
        pass

    @abc.abstractmethod
    def check_auth(self, ctx: Context):
        pass
