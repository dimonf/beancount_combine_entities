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
                               'our_tag'         = "oi-master",\
                               'filter_flag'     = "x", \
                               'filter_amount'   = 'dt', \
                               'invert_amount'   = True, \
                               'our_account'     = 'Assets:Agent', \
                               'super_meta'      = 's_meta', \
                               }"
"""

__version__ = "0.2"
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

    config['filter_flag'] = config.get('filter_flag', filter_flag)
    config['super_meta'] = config.get('super_meta', super_meta)
    config['invert_amount'] = config.get('invert_amount', invert_amount)
    new_t_entries = [] #all Transactions
    new_n_entries = [] #all non-Transactions
    our_files = {} #file path(s) for files, where use of our_tag was detected
    errors = []

    for entry in entries:
        if isinstance(entry, data.Transaction):
            if config['our_tag'] in entry.tags:
                new_t_entries.append(entry)
                our_files[entry.meta['filename']] = True
            else:
                #here go only "foreign" entries
                entry, replaced = replace_entry(entry, config)
                #print(replaced)
                if replaced:
                    new_t_entries.append(entry)
        else:
            new_n_entries.append(entry)

    #remove entries of all types other than Transaction from "foreign" files
    for entry in new_n_entries:
        if entry.meta['filename'] in our_files:
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
            message = """please write proper _meta for posting:
            {}:{}""".format(meta_new['filename'],meta_new['lineno'])
            print(message)
            #raise KeyError(message)
            continue

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
    return entry, len(new_postings)

def test_amount(amount, config):
    if config['filter_amount'] == filter_positive  and \
       amount.number > ZERO:
        return True
    elif config['filter_amount'] == filter_negative and \
       amount.number < ZERO:
        return True
    else:
        return False

