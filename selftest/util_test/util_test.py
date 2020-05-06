#!/usr/bin/env python3
import _prep

from osmo_gsm_tester.core.util import hash_obj

print('- expect the same hashes on every test run')
print(hash_obj('abc'))
print(hash_obj(1))
print(hash_obj([1, 2, 3]))
print(hash_obj({ 'k': [ {'a': 1, 'b': 2}, {'a': 3, 'b': 4}, ],
                 'i': [ {'c': 1, 'd': 2}, {'c': 3, 'd': 4}, ] }))
