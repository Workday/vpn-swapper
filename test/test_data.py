import json
from os.path import join, dirname


def read_json(file_name):
    with open(join(dirname(__file__),
                   'fixtures',
                   file_name), 'r') as fle:
        return json.load(fle)

def instances():
    return read_json('instances.json')
