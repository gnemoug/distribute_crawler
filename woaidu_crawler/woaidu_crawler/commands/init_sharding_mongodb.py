#!/usr/bin/python
#-*-coding:utf-8-*-

"""
    This file is for initiate mongodb situation
    
    When you want to save book file in gridfs,then you need a sharding cluster,that the database design is:
    database:books_mongo
    collections:
        book_detail
        book_file
    fields:
        book_detail:
            book_name:string
            alias_name:vector
            author:vector
            book_description:string
            book_covor_image_url:string
            book_covor_image_path:string
            book_download:vector
            book_file_id:gridfs id
            book_file_url:string
            original_url:string
            update_time:datetime
        book_file:
            book_file.chunks:
                _id
                files_id
                n
                data
            book_file.files:
                _id
                length
                chunkSize
                uploadDate
                md5
                filename
                contentType
                aliases
                metadata
    index:
        book_name
        alias_name
        author
    sharding key:
        update_time+book_name

    So what this do is to delete books_mongo if it has existed,and initiate the sharding cluster.
    
    NOTE:
    For killall mongo procs after terminate the file process,you need use CTRL+C.
    Before you run this file,you need type this in a shell:sudo killall mongod.
    For check the info about all mongos,use the command:netstat -lntp|grep mongo
    
    ABOUT:
    This code mostly comes from:
        https://github.com/gnemoug/mongo-snippets/blob/master/sharding/simple-setup.py
"""

import os
import sys
import shutil
import pymongo
import types
#The atexit module defines a single function to register cleanup functions. 
import atexit

from socket import error, socket, AF_INET, SOCK_STREAM
from pymongo import ASCENDING, DESCENDING
from pymongo import MongoClient
from select import select
from subprocess import Popen, PIPE, STDOUT
from threading import Thread
from time import sleep

try:
    # new pymongo
    from bson.son import SON
except ImportError:
    # old pymongo
    from pymongo.son import SON#the Serialized Ocument Notation

# BEGIN CONFIGURATION

# some settings can also be set on command line. start with --help to see options

ShardMONGODB_DB = "books_mongo"
GridFs_Collection = "book_file"

BASE_DATA_PATH='/data/db/books/sharding/' #warning: gets wiped every time you run this
MONGO_PATH=os.getenv( "MONGO_HOME" , os.path.expanduser('~/10gen/mongo/') )
N_SHARDS=3
N_CONFIG=1 # must be either 1 or 3
N_MONGOS=1
CHUNK_SIZE=64 # in MB (make small to test splitting)
MONGOS_PORT=27017 if N_MONGOS == 1 else 10000 # start at 10001 when multi
USE_SSL=False # set to True if running with SSL enabled

CONFIG_ARGS=[]
MONGOS_ARGS=[]
MONGOD_ARGS=[]

# Note this reports a lot of false positives.
USE_VALGRIND=False
VALGRIND_ARGS=["valgrind", "--log-file=/tmp/mongos-%p.valgrind", "--leak-check=yes", 
               ("--suppressions="+MONGO_PATH+"valgrind.suppressions"), "--"]

# see http://pueblo.sourceforge.net/doc/manual/ansi_color_codes.html
CONFIG_COLOR=31 #red
MONGOS_COLOR=32 #green
MONGOD_COLOR=36 #cyan
BOLD=True
conn = None

INDEX = {\
            #collection
            'book_detail':\
                {\
                    #Unique indexes on sharded collections have to start with the shard key.
                    #You can have only one unique key in sharding configuration. 
                    (('book_name',ASCENDING),('author',ASCENDING)):{'name':'book_name_author'},
                    'book_name':{'name':'book_name'},
                    'author':{'name':'author'},
                    'alias_name':{'name':'alias_name'},
                }\
        }

# defaults -- can change on command line
COLLECTION_KEYS = {'book_detail':'update_time,book_name'}

def AFTER_SETUP():
    """
        make index and shard keys.
    """
    
    # feel free to change any of this
    # admin and conn are both defined globaly
    admin.command('enablesharding', ShardMONGODB_DB)

    for (collection, keystr) in COLLECTION_KEYS.iteritems():
        key=SON((k,1) for k in keystr.split(','))
        admin.command('shardcollection', ShardMONGODB_DB+'.'+collection, key=key)

    admin.command('shardcollection', ShardMONGODB_DB+'.'+GridFs_Collection+'.files', key={'_id':1})
    admin.command('shardcollection', ShardMONGODB_DB+'.'+GridFs_Collection+'.chunks', key={'files_id':1})
    
    for k,v in INDEX.items():
        for key,kwargs in v.items():
            conn[ShardMONGODB_DB][k].ensure_index(list(key) if type(key)==types.TupleType else key,**kwargs)

# END CONFIGURATION

for x in sys.argv[1:]:
    opt = x.split("=", 1)
    if opt[0] != '--help' and len(opt) != 2:
        raise Exception("bad arg: " + x )
    
    if opt[0].startswith('--'):
        opt[0] = opt[0][2:].lower()
        if opt[0] == 'help':
            print sys.argv[0], '[--help] [--chunksize=200] [--port=27017] [--path=/where/is/mongod] [collection=key]'
            sys.exit()
        elif opt[0] == 'chunksize':
            CHUNK_SIZE = int(opt[1])
        elif opt[0] == 'port':
            MONGOS_PORT = int(opt[1])
        elif opt[0] == 'path':
            MONGO_PATH = opt[1]
        elif opt[0] == 'usevalgrind': #intentionally not in --help
            #use for memory leak check.
            USE_VALGRIND = int(opt[1])
        else:
            raise( Exception("unknown option: " + opt[0] ) )
    else:
        COLLECTION_KEYS[opt[0]] = opt[1]

if MONGO_PATH[-1] != '/':
    MONGO_PATH = MONGO_PATH+'/'

print( "MONGO_PATH: " + MONGO_PATH )

if not USE_VALGRIND:
    VALGRIND_ARGS = []

# fixed "colors"
RESET = 0
INVERSE = 7

if os.path.exists(BASE_DATA_PATH):
    print( "removing tree: %s" % BASE_DATA_PATH )
    shutil.rmtree(BASE_DATA_PATH)

mongod = MONGO_PATH + 'mongod'
mongos = MONGO_PATH + 'mongos'

devnull = open('/dev/null', 'w+')

fds = {}
procs = []

def killAllSubs():
    for proc in procs:
        try:
            proc.terminate()
        except OSError:
            pass #already dead
atexit.register(killAllSubs)

def mkcolor(colorcode): 
    base = '\x1b[%sm'
    if BOLD:
        return (base*2) % (1, colorcode)
    else:
        return base % colorcode

def ascolor(color, text):
    return mkcolor(color) + text + mkcolor(RESET)

def waitfor(proc, port):
    trys = 0
    while proc.poll() is None and trys < 40: # ~10 seconds
        trys += 1
        s = socket(AF_INET, SOCK_STREAM)
        try:
            try:
                s.connect(('localhost', port))
                return
            except (IOError, error):
                sleep(5)
                #XXX:
                #When I use the sharding/simple-setup.py file,it always say:failed to start.But when I change the sleep time from 0.25 to 5,It works!
        finally:
            s.close()

    #extra prints to make line stand out
    print
    print proc.prefix, ascolor(INVERSE, 'failed to start')
    print
    
    sleep(1)
    killAllSubs()
    sys.exit(1)


def printer():
    while not fds: sleep(0.01) # wait until there is at least one fd to watch

    while fds:
        (files, _ , errors) = select(fds.keys(), [], fds.keys(), 1)
        for file in set(files + errors):
            # try to print related lines together
            while select([file], [], [], 0)[0]:
                line = file.readline().rstrip()
                if line:
                    print fds[file].prefix, line
                else:
                    if fds[file].poll() is not None:
                        print fds[file].prefix, ascolor(INVERSE, 'EXITED'), fds[file].returncode
                        del fds[file]
                        break
                break

printer_thread = Thread(target=printer)
printer_thread.start()


configs = []
for i in range(1, N_CONFIG+1):
    path = BASE_DATA_PATH +'config_' + str(i)
    os.makedirs(path)
    #print mongod,' --port ',str(20000+i),' --configsvr',' --dbpath ',path
    config = Popen([mongod, '--port', str(20000 + i), '--configsvr', '--dbpath', path] + CONFIG_ARGS, 
                   stdin=devnull, stdout=PIPE, stderr=STDOUT)
    config.prefix = ascolor(CONFIG_COLOR, 'C' + str(i)) + ':'
    fds[config.stdout] = config
    procs.append(config)
    waitfor(config, 20000 + i)
    configs.append('localhost:' + str(20000 + i))


for i in range(1, N_SHARDS+1):
    path = BASE_DATA_PATH +'shard_' + str(i)
    os.makedirs(path)
    shard = Popen([mongod, '--port', str(30000 + i), '--shardsvr', '--dbpath', path] + MONGOD_ARGS,
                  stdin=devnull, stdout=PIPE, stderr=STDOUT)
    shard.prefix = ascolor(MONGOD_COLOR, 'M' + str(i)) + ':'
    fds[shard.stdout] = shard
    procs.append(shard)
    waitfor(shard, 30000 + i)


#this must be done before starting mongos
for config_str in configs:
    host, port = config_str.split(':')
    config = MongoClient(host, int(port), ssl=USE_SSL).config
    config.settings.save({'_id':'chunksize', 'value':CHUNK_SIZE}, safe=True)
del config #don't leave around connection directly to config server

if N_MONGOS == 1:
    MONGOS_PORT -= 1 # added back in loop

for i in range(1, N_MONGOS+1):
    router = Popen(VALGRIND_ARGS + [mongos, '--port', str(MONGOS_PORT+i), '--configdb' , ','.join(configs)] + MONGOS_ARGS,
                   stdin=devnull, stdout=PIPE, stderr=STDOUT)
    router.prefix = ascolor(MONGOS_COLOR, 'S' + str(i)) + ':'
    fds[router.stdout] = router
    procs.append(router)

    waitfor(router, MONGOS_PORT + i)

conn = MongoClient('localhost', MONGOS_PORT + 1, ssl=USE_SSL)
admin = conn.admin

for i in range(1, N_SHARDS+1):
    admin.command('addshard', 'localhost:3000'+str(i), allowLocal=True)

AFTER_SETUP()

# just to be safe
sleep(2)

print '*** READY ***'
print 
print 

try:
    printer_thread.join()
except KeyboardInterrupt:
    pass
