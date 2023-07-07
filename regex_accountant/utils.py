import dataclass_wizard as dw

# https://github.com/rnag/dataclass-wizard/issues/92
def asdict(obj):
    dw.DumpMeta(key_transform="SNAKE").bind_to(obj.__class__)
    return dw.asdict(obj)
