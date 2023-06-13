"""Combine transactions of two separate entities that have transactions between
   each other. For example, the principal pays money to the agent, which, in turn,
   spends funds according to the principal's instructions. To avoid recording 
   such a spending in books of both companies, an accountant can combine records 
   of both companies with "include" directive, and then, use this plugin to
   transform transactions of interest in books of agent for needs of the principal 
   Special meta value with key '_meta' has this format:
     "<account>;<meta_n>"
    e.g:
     "Expenses:Agency; sub:sales expenses; com: advance and arrears"
    which will be transformed into a balancing posting for our_account:

      Assets:Agent         -500.00 EUR
      Expenses:Agency 
         sub: "sales expenses"
         com: "advance and arrears"
    Side effect of this plugin is implied filter of transactions by filter_tag


   include "agent_records.bean"
   plugin "combine_entities" "{'filter_account' = 'Liabilities:Principal', \
                               'filter_tag'      = "principal", \
                               'filter_flag'     = "x", \
                               'filter_amount'   = 'dt', \
                               'invert_amount'   = True, \
                               'our_account'     = 'Assets:Agent', \
                               'super_meta'      = '_meta', \
                               }"
"""

__version__ = "0.1"
__copyright__ = "Copyright (C) Dmitri Kourbatsky"
__license__ = "MIT License"
__plugins__ = ('filter_by_tag',)

import re

from beancount.core import data
from beancount.parser import options

_DEBUG = False

filter_positive = "dt"
filter_negative = "ct"
filter_flag     = "x"
invert_amount   = True
super_meta      = "_meta"

def combine_entities(entries, options_map, config_str):
    conf = eval(config_str, {}, {})
    if not isinstance(conf, dict):
        raise RuntimeError("Invalid plugin configuration: args must be a single dictionary")

    config['filter_flag'] = config['filter_flag'] or filter_flag
    config['super_meta'] = config['super_meta'] or super_meta
    config['invert_amount'] = config['invert_amount'] or invert_amount
    new_entries = []
    errors = []
    for entry in entries:
        if isinstance(entry, Transaction):
            if not conf['select_tag'] in entry.tags:
                continue
            entry = replace_entry(entry, config)
        new_entries.append(entry)

    return new_entries, errors

def replace_entry(entry, config):
    """for every posting of interest modify account/position and create 
       balancing entry
    """

    new_postings = []
    for posting in entry.postings:
        if posting.account != config['filter_account'] or \
            posting.flag != config['filter_flag'] or \
            not test_amount(posting.units, config):
                continue

        meta_new = posting.meta.copy()
        #super_meta = "account; sub: Sales expenses; com: Reimburseable; ..."
        super_meta = meta_new.pop(config['super_meta']).split(';')

        new_posting = posting._replace(account = config['our_account'],
                                       meta = meta_new,
                                       units = -posting.units)
        new_postings.append(new_posting)
        #balancing posting
        n_account = super_meta.pop(0).strip()
        n_meta = {v[0]:f'"{v[1]}"' for v in [s.split(':') for s in super_meta]}
        bal_posting = data.create_simple_posting(
                            entry = None,
                            account = n_account,
                            number = None,
                            currency = '')
        bal_posting.meta=n_meta
        new_postings.append(bal_posting)
    if new_postings:
        entry = entry._replace(postings = new_postings)
    return entry

def test_amount(amount, config):
    if config['filter_amount'] == filter_positive  and \
       amount > 0:
        return True
    elif config['filter_amount'] == filter_negative and \
       amount < 0:
        return True
    else:
        return False

