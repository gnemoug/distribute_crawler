#!/usr/bin/python
#-*-coding:utf-8-*-

"""
    This file is for initiate mongodb situation
    
    When you want to save book file in file system,then you don't need sharding cluster,that the database design is:
    database:books_fs
    collections:book_detail
    fields:
        book_detail:
            book_name
            alias_name:vector
            author:vector
            book_description:string
            book_covor_image_path:string
            book_covor_image_url:string
            book_download:vector
            book_file_url:string
            book_file:string
            original_url:string
            update_time:datetime
    index:
        book_name
        alias_name
        author

    So what this do is to delete books_fs is it has existed,and create index for it.
"""

import types
from pymongo.connection import MongoClient
from pymongo import ASCENDING, DESCENDING

DATABASE_NAME = "books_fs"
client = None
DATABASE_HOST = "localhost"
DATABASE_PORT = 27017
INDEX = {\
            #collection
            'book_detail':\
                {\
                    (('book_name',ASCENDING),('author',ASCENDING)):{'name':'book_name_author','unique':True},
                    'book_name':{'name':'book_name'},
                    'author':{'name':'author'},
                    'alias_name':{'name':'alias_name'},
                }\
        }

def drop_database(name_or_database):
    if name_or_database and client:
        client.drop_database(name_or_database)

def create_index():
    """
        create index for books_fs.book_detail
    """
    for k,v in INDEX.items():
        for key,kwargs in v.items():
            client[DATABASE_NAME][k].ensure_index(list(key) if type(key)==types.TupleType else key,**kwargs)

if __name__ == "__main__":
    client = MongoClient(DATABASE_HOST,DATABASE_PORT) 
    drop_database(DATABASE_NAME)
    create_index() 
