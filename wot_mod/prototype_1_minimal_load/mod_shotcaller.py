"""Minimal Shot-caller load test for World of Tanks."""


TAG = '[shotcaller]'


def _log(message):
    print(TAG + ' ' + message)


def init():
    _log('loaded')


def fini():
    _log('unloaded')
