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


   include "agent_records.bean"
   plugin "combine_entities" "{'filter_account' = 'Liabilities:Principal', \
                               'filter_tag'      = "principal", \
                               'filter_flag'     = "x", \
                               'filter_amount'   = 'dt', \
                               'invert_amount'   = True, \
                               'our_account'     = 'Assets:Agent', \
                               'super_meta'      = 's_meta', \
                               }"
"""

__version__ = "0.1"
__copyright__ = "Copyright (C) Dmitri Kourbatsky"
__license__ = "MIT License"
__plugins__ = ('combine_entities',)

import re

from beancount.core import data
from beancount.parser import options
from beancount.core.amount import Amount
from beancount.core.number import ZERO

_DEBUG = False

filter_positive = "dt"
filter_negative = "ct"
filter_flag     = "x"
invert_amount   = True
super_meta      = "s_meta"


def combine_entities(entries, options_map, config_str):
    config = eval(config_str, {}, {})
    if not isinstance(config, dict):
        raise RuntimeError("Invalid plugin configuration: args must be a single dictionary")
    #print(config) #DELME

    config['filter_flag'] = config['filter_flag'] or filter_flag
    config['super_meta'] = config['super_meta'] or super_meta
    config['invert_amount'] = config['invert_amount'] or invert_amount
    new_t_entries = [] #all Transactions
    new_n_entries = [] #all non-Transactions
    affected_accounts = {}
    errors = []

    for entry in entries:
        if isinstance(entry, data.Transaction):
            if config['filter_tag'] in entry.tags:
                entry = replace_entry(entry, config)
                new_t_entries.append(entry)
            else:
                #all Transaction entries that do not match
                for posting in entry.postings:
                    affected_accounts[posting.account] = True
                continue
        else:
            new_n_entries.append(entry)
    #remove "balance" entries for accounts that were affected by dropped transactions
    for entry in new_n_entries:
        if isinstance(entry, data.Balance):
            if not entry.account in affected_accounts:
                new_t_entries.append(entry)
        else:
            new_t_entries.append(entry)

    return new_t_entries, errors

def replace_entry(entry, config):
    """for every posting of interest modify account/position and create 
       balancing entry
    """

    new_postings = []
    for posting in entry.postings:
        if posting.account != config['filter_account'] or \
            not test_amount(posting.units, config):
                continue

        meta_new = posting.meta.copy()
        #super_meta = "account; sub: Sales expenses; com: Reimburseable; ..."
        try:
            super_meta = meta_new.pop(config['super_meta']).split(';')
        except KeyError:
            print(meta_new)
            raise KeyError("""please write proper _meta for posting:
            {}:{}""".format(meta_new['filename'],meta_new['lineno']))

        new_posting = posting._replace(account = config['our_account'],
                                       meta = meta_new,
                                       units = -posting.units)
        new_postings.append(new_posting)
        #balancing posting
        n_account = super_meta.pop(0).strip()
        n_meta = {v[0]:f'"{v[1]}"' for v in [s.split(':') for s in super_meta]}
        #Posting(account, units, cost, price, flag, meta)
        bal_posting = data.Posting(
            account = n_account,
            units   = posting.units,
            cost    = None,
            price   = None,
            flag    = None,
            meta    = n_meta
        )
        new_postings.append(bal_posting)
    if new_postings:
        entry = entry._replace(postings = new_postings)
    return entry

def test_amount(amount, config):
    if config['filter_amount'] == filter_positive  and \
       amount.number > ZERO:
        return True
    elif config['filter_amount'] == filter_negative and \
       amount.number < ZERO:
        return True
    else:
        return False

