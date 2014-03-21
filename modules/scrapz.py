# -*- coding: utf-8 -*-
"""
Created on Wed Jun 13 12:48:39 2012

@author: sean.mackedie
"""

def multisplit(string, *seps):
    split_string = [string]
    for sep in seps:
        string, split_string = split_string, []
        for seq in string:
            split_string += seq.split(sep)
    return split_string