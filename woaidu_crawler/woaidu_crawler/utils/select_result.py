#!/usr/bin/python
#-*-coding:utf-8-*-

import types
from w3lib.html import remove_entities
from urlparse import urlparse, urljoin

NULL = [None,'null']

list_first_item = lambda x:x[0] if x else None

def strip_null(arg,null=None):
    """
        strip list,set,tuple,dict null item.

        @param:
            arg:the variable to strip null
            null:the null definition,if it is None,then use NULL as the null

        if arg is list,then strip the null item,return the new list
        if arg is tuple,then strip the null item,return the new tuple
        if arg is set,then strip the null item,return the new set
        if arg is dict,then strip the dict item which value is null.return the new dict
    """
    if null is None:
        null = NULL

    if type(arg) is types.ListType:
        return [i for i in arg if i not in null]
    elif type(arg) is types.TupleType:
        return tuple([i for i in arg if i not in null])
    elif type(arg) is type(set()):
        return arg.difference(set(null))
    elif type(arg) is types.DictType:
        return {key:value for key,value in arg.items() if value not in null}

    return arg

def deduplication(arg):
    """
        deduplication the arg.

        @param:
            arg:the variable to deduplication

        if arg is list,then deduplication it and then the new list.
        if arg is tuple,then deduplication it and then the new tuple.
    """
    if type(arg) is types.ListType:
        return list(set(arg))
    elif type(arg) is types.TupleType:
        return tuple(set(arg))

    return arg

def clean_link(link_text):
    """
        Remove leading and trailing whitespace and punctuation
    """

    return link_text.strip("\t\r\n '\"")

clean_url = lambda base_url,u,response_encoding: urljoin(base_url, remove_entities(clean_link(u.decode(response_encoding))))
"""
    remove leading and trailing whitespace and punctuation and entities from the given text.
    then join the base_url and the link that extract
"""
