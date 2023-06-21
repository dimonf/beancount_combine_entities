"""Combine transactions of two separate entities that have transactions between
   each other. For example, the principal pays money to the agent, which then
   spends funds according to the principal's instructions. If beancount datafiles
   for both companies available, such spendings can be recorder in books of the
   agent only. A third bean file then can be created, where
     - both "importing" and "exporting" files are sourced by "include" directive,
     - plugin directive's config determins selection and transformation of 
       transactions
    In general, all entries of Transaction type are ignored if:
     - they do not have tag 'our_tag', and
     - they do not have postings specified by 'filter_account'
    Postings with account matching 'filter_account', 'filter_amount' are transformed
    (most probably, altering sign of the amount, if 'invert_amount' is True), 
    padded with corresponding posting to balance transaction. This balancing
    posting is constructed, based on two-stage mechanism:
     - 'exporting' posting has a meta with 'super_meta' key, which will be
        left intact and be copied into the merged data set
     - plugin's config shall specify both, this 'super_meta' name, and mapping
       for this super_meta values, between "exporting" entries and "importing"
       dataset. The "importing" side of this mapping is a string of the following
       structure:
         'sm_<from_meta_name>':"<account>;<meta_name:meta_value>', 
        eg:
         'sm_sales': 'Expenses:Agency; sub:sales expenses, com: advance and arrears'
       Value of new meta can be set to '*', in which case the value of 'exporting' 
         meta will be used

    The previous example config will be transformed into a balancing posting for 
    our_account:

      Assets:Agent         -500.00 EUR
         sub: "sales"
      Expenses:Agency 
         sub: "sales expenses"
         com: "advance and arrears"

    This mapping allows for certain level of decoupling between two data files

   include "agent_records.bean"
   include "principal_records.bean"
   plugin "combine_entities" "{
             'filter_account'  : 'Liabilities:Principal', 
             'our_tag'         : "oi-master",
             'filter_flag'     : "x", 
             'filter_amount'   : 'dt',
             'invert_amount'   : True,
             'our_account'     : 'Assets:Agent',
             'super_meta'      : 'sub',
             'sm_sales'        : 'Expenses:Agency;sub:sales expenses;com:advance',
             'sm_cash*'        : 'Liabilities:Intra-group;sub:*',
             }"
    
    Filter by flag is yet to be implemented
"""

__version__ = "0.2"
__copyright__ = "Copyright (C) Dmitri Kourbatsky"
__license__ = "MIT License"
__plugins__ = ('combine_entities',)

import re
from fnmatch import fnmatch

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

    config['filter_flag'] = config.get('filter_flag', filter_flag)
    config['super_meta'] = config.get('super_meta', super_meta)
    config['invert_amount'] = config.get('invert_amount', invert_amount)
    new_t_entries = [] #all Transactions
    new_n_entries = [] #all non-Transactions
    our_files = {} #file path(s) for files, where use of our_tag was detected
    errors = []

    #parse config
    config['meta_map'] = config.get('meta_map', {})
    for k,v in config.items():
        if k.startswith('sm_'):
            acc, *meta = v.split(';')
            config['meta_map'][k[3:]] = {
                'account':acc,
                'meta'   :{a[0]:a[1] for a in (b.split(':') for b in meta)}
            }

    for entry in entries:
        if isinstance(entry, data.Transaction):
            if config['our_tag'] in entry.tags:
                new_t_entries.append(entry)
                our_files[entry.meta['filename']] = True
            else:
                #here go only "foreign" entries
                entry, replaced = replace_entry(entry, config)
                if replaced:
                    new_t_entries.append(entry)
        else:
            new_n_entries.append(entry)

    #drop entries of all types other than Transaction from "foreign" files
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

        #super_meta = "account; sub: Sales expenses; com: Reimburseable; ..."
        try:
            sm_val = posting.meta[config['super_meta']]
        except KeyError:
            message = """key {} is not defined for entry at
            {}:{}""".format(config['super_meta'],
                            posting.meta['filename'],
                            posting.meta['lineno'],
                            )
            print(message)
            continue

        bal_p = None
        try:
            bal_p = config['meta_map'][sm_val]
        except KeyError:
            for k in config['meta_map'].keys():
                if fnmatch(sm_val, k):
                    bal_p = config['meta_map'][k]
                    break
            if not bal_p:
                message = """please write proper config for meta {}:{} at
                {}:{}""".format(config['super_meta'],
                                sm_val,
                                posting.meta['filename'],
                                posting.meta['lineno'],
                                )
                print(message)
                #raise KeyError(message)
                continue

            #replace * with value from "exporting" posting meta
            for k,v in bal_p['meta'].items():
                if v == '*':
                    bal_p['meta'][k] = sm_val

        new_posting = posting._replace(account = config['our_account'],
                                       units = -posting.units)
        new_postings.append(new_posting)
        #balancing posting
        bal_posting = data.Posting(
            account = bal_p['account'],
            units   = posting.units,
            cost    = None,
            price   = None,
            flag    = None,
            meta    = bal_p['meta']
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

