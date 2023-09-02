import dataclass_wizard as dw

# https://github.com/rnag/dataclass-wizard/issues/92
def asdict(obj):
    dw.DumpMeta(key_transform="SNAKE").bind_to(obj.__class__)
    d = dw.asdict(obj)
    return d


def prune_empty(obj):
    if isinstance(obj, dict):
        for k, v in list(obj.items()):
            if not v:
                obj.pop(k)
                continue
            obj[k] = prune_empty(obj[k])
        return obj
    if isinstance(obj, list):
        return [prune_empty(elt) for elt in obj]
    return obj
