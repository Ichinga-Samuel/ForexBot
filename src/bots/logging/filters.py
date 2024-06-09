import logging


def exact_filter(level):
    level = getattr(logging, level)

    def exact(record):
        return record.levelno == level

    return exact


def less_than_filter(level):
    level = getattr(logging, level)

    def less_than(record):
        return record.levelno <= level

    return less_than


def greater_than_filter(level):
    level = getattr(logging, level)

    def greater_than(record):
        return record.levelno >= level

    return greater_than
