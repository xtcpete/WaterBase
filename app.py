from flask import Flask, Response, request, render_template, jsonify, json
from flask_socketio import SocketIO, emit
import pymongo
import string
import random


# create database
class MongoDB():
    """
    class that used to connect to the mongodb server
    """

    def __init__(self, name):
        # connect to mongodb
        self.myclient = pymongo.MongoClient("mongodb://localhost:27017/")
        # access the db
        self.db = self.myclient[name]


class RequestInfo():
    """
    class that used to store the requested information
    root_database: the database in mongodb
    collection： the collection of the database accessed
    fullpath: the full requested path
    data: josn data from the request
    keys: requested keys
    operators: dictionary that store all operators in the requests
    """

    def __init__(self):
        self.root_database = "root"
        self.paths = request.path.split('/')[1:]
        self.collection = self.paths[0]
        self.fullpath = request.full_path
        self.data = request.get_data().decode('utf-8')
        self.operators = {}
        self.key = self.paths[1:]
        self.json = False

        # check for .json ending
        if len(self.key) > 0:
            temp = self.key[-1].split(".")
            if len(temp) >= 2:
                self.key[-1] = temp[0]
                if temp[1] == 'json':
                    self.json = True
        else:
            temp = self.collection.split(".")
            if len(temp) >= 2:
                self.collection = temp[0]
                if temp[1] == 'json':
                    self.json = True

        # check for operators
        temp = self.fullpath.split("?")
        if len(temp) >= 2 and temp[1] != '':
            operators_str = temp[1]
            operators_list = operators_str.split("&")
            for operators in operators_list:
                key_value = operators.split("=")

                name = key_value[0]
                value = key_value[1]

                self.operators[name] = value


app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app)


@app.route('/')
def index():
    db = MongoDB('root').db
    collections = db.list_collection_names()
    all_data = {}.fromkeys(collections)
    for collection in collections:
        all_data[collection] = [x for x in db.get_collection(collection).find()]
    return render_template("index.html", all_data=all_data)


@app.route('/<path:myPath>', methods=['PUT'])
def catch_all_put(myPath):
    request_info = RequestInfo()
    db = MongoDB(request_info.root_database).db

    # access the collection
    data_collect = db[request_info.collection]

    # obtain the json data
    json_data = request_info.data
    # load it into dictionary, if data sent are not a valid json, store it as string
    try:
        dict_data = json.loads(json_data)
    except:
        return str(json_data) + " Not a valid json"

    # check if it is a list and then add id to the data
    if type(dict_data) is list:
        if len(request_info.key) == 0:
            dict_data = list(map(lambda x, y: {"_id": str(x), "data": y}, range(len(dict_data)), dict_data))
    else:
        if len(request_info.key) == 0:  # create _id for data stored under the first level key
            if len(list(dict_data.values())) == 1 and type(list(dict_data.values())[0]) == dict:
                dict_data = [{"_id": list(dict_data.keys())[0], "data": list(dict_data.values())[0]}]
            else:
                dict_data = [{"_id": '0', "data": dict_data}]

    keys = request_info.key

    # check the length of keys
    num_key = len(keys)

    if num_key == 0:  # no sub key, just insert into the collection
        data_collect.drop()
        data_collect.insert_many(dict_data)
    elif num_key == 1:
        data = {"$set": {'data': dict_data}}
        data_collect.update_one({'_id': keys[0]}, data, upsert=True)
    else:
        # nested document
        joined_key = 'data.' + '.'.join(keys[1:])
        data = {"$set": {joined_key: dict_data}}
        data_collect.update_one({'_id': keys[0]}, data, upsert=True)

    socketio.emit('update', {'collection': request_info.collection, 'keys': keys, "data": dict_data})
    return ''


@app.route('/<path:myPath>', methods=['GET'])
def catch_all_get(myPath):

    request_info = RequestInfo()

    db = MongoDB(request_info.root_database).db

    # access the collection
    data_collect = db[request_info.collection]

    keys = request_info.key

    # check the length of keys
    num_key = len(keys)

    # find the data
    if request_info.operators == {}:
        # check for the number of keys
        if num_key == 0:
            cursor = data_collect.find({}, {'data': 1, '_id': 1})
        elif num_key == 1:
            cursor = data_collect.find({'_id': keys[0]}, {'data': 1, '_id': 1})
        else:
            joined_key = "data." + '.'.join(keys[1:])
            cursor = data_collect.find({'_id': keys[0], joined_key: {"$exists": True}}, {joined_key: 1, '_id': 1})

    else:
        operators = request_info.operators
        match = {}
        if num_key > 0:
            match['_id'] = keys[0]
            pre_target_var = "data." + '.'.join(keys[1:])
        else:
            pre_target_var = 'data.'

        if pre_target_var:
            # if there exist operators

            pipeline = []
            if 'orderBy' in operators:
                target_var = operators['orderBy']
                if '$' not in target_var:
                    target_var = pre_target_var + target_var
                    try:
                        data_collect.create_index(target_var)
                    except:
                        data_collect.drop_index('$value')
                        data_collect.create_index(target_var)

                else:
                    if target_var == '$key':
                        target_var = '_id'
                    elif target_var == '$value':
                        if 'createIndex' in operators:
                            attribute = operators['createIndex']
                            target_var = pre_target_var + attribute
                            try:
                                data_collect.create_index(target_var, name='$value')
                            except:
                                try:
                                    data_collect.drop_index(target_var+'_1')
                                except:
                                    data_collect.drop_index('$value')

                                data_collect.create_index(target_var, name='$value')

                        index_info = data_collect.index_information()
                        if '$value' in index_info:
                            target_var = index_info['$value']['key'][0][0]
                        else:
                            return 'Please create index by adding createIndex=Name of the value to the end of your ' \
                                   'request '

                for operation in operators:
                    if operation != 'orderBy':
                        if operation == 'startAt':
                            match['$gte'] = int(operators[operation])
                            pipeline.append({'$match': {target_var: match}})
                        elif operation == 'endAt':
                            match['$lte'] = int(operators[operation])
                            pipeline.append({'$match': {target_var: match}})
                        elif operation == 'equalTo':
                            match['$eq'] = int(operators[operation])
                            pipeline.append({'$match': {target_var: match}})
                        elif operation == 'limitToFirst':
                            limit = {'$limit': int(operators[operation])}
                            sort = {'$sort': {target_var: 1}}
                            pipeline.append(sort)
                            pipeline.append(limit)
                        elif operation == 'limitToLast':
                            limit = {'$limit': int(operators[operation])}
                            sort = {'$sort': {target_var: -1}}
                            pipeline.append(sort)
                            pipeline.append(limit)
                        else:
                            sort = ''
                    else:
                        sort = {'$sort': {target_var: 1}}
                        if match != {}:
                            pipeline.append({'$match': match})
                        pipeline.append(sort)
                if pipeline == []:
                    return "Error: Operation not found"

                cursor = data_collect.aggregate(pipeline)

    data = []

    for document in cursor:
        # loop over keys to get only the stored value
        temp = document['data']
        if '_id' in document:
            key = document['_id']
            temp = {key: temp}
        if len(keys) > 1:
            i = 1
            while i <= len(keys) - 1:
                temp = temp[keys[i]]
                i += 1
        data.append(temp)

    if len(data) == 0:
        data.append("Error: data not found")
    elif len(data) == 1:
        data = data[0]
    if request_info.json:
        return jsonify(data)
    else:

        return "Error: Add .json to the url"


@app.route('/<path:myPath>', methods=['POST'])
def catch_all_post(myPath):
    """
    NEED UPDATE. BUGs
    """
    request_info = RequestInfo()
    db = MongoDB(request_info.root_database).db
    # access the collection
    data_collect = db[request_info.collection]
    # obtain the json data
    json_data = request_info.data
    # load it into dictionary
    dict_data = json.loads(json_data)
    keys = request_info.key
    # check the length of keys
    num_key = len(keys)
    N = 8
    res = ''.join(random.choices(string.ascii_letters, k=N))
    collection = request_info.collection
    if num_key == 0:
        dict_data = {"_id": res, "data": dict_data}
        data_collect.insert_one(dict_data)
        collection = res

    elif (num_key == 1):
        data = {"$set": {'data.' + res: dict_data}}
        data_collect.update_one({'_id': keys[0]}, data, upsert=True)

    else:
        joined_key = 'data.' + '.'.join(keys[1:] + [res])
        data = {"$set": {joined_key: dict_data}}
        data_collect.update_one({'_id': keys[0]}, data, upsert=True)

    socketio.emit('update', {'collection': collection, 'keys': keys + [res], "data": dict_data})
    return ""


@app.route('/<path:myPath>', methods=['DELETE'])
def catch_all_delete(myPath):
    request_info = RequestInfo()

    db = MongoDB(request_info.root_database).db

    # access the collection
    data_collect = db[request_info.collection]

    keys = request_info.key

    # check the length of keys
    num_key = len(keys)

    if num_key == 0:
        data_collect.drop()
    elif num_key == 1:
        # check if the key exists
        data_collect.delete_one({'_id': keys[0]})
    else:
        # nested document
        joined_key = "data." + '.'.join(keys[1:])
        data = {"$unset": {joined_key: ""}}
        data_collect.update_one({'_id': keys[0]}, data)

    collections = db.list_collection_names()
    all_data = {}.fromkeys(collections)
    for collection in collections:
        all_data[collection] = [x for x in db.get_collection(collection).find()]
    socketio.emit('delete', {'collection': request_info.collection, 'keys': request_info.key, 'data': all_data})
    return ""


@app.route('/<path:myPath>', methods=['PATCH'])
def catach_all_patch(myPath):
    request_info = RequestInfo()
    db = MongoDB(request_info.root_database).db
    # access the collection
    data_collect = db[request_info.collection]
    json_data = request_info.data
    # load it into dictionary, if data sent are not a valid json, store it as string
    try:
        dict_data = json.loads(json_data)
    except:
        return str(json_data) + " Not a valid json"

    # check if it is a list and then add id to the data

    keys = request_info.key

    # check the length of keys
    num_key = len(keys)

    if num_key == 0:  # no sub key, just insert into the collection
        data_collect.drop()
        data_collect.insert_many(dict_data)
    elif num_key == 1:
        data = {"$set": {'data': dict_data}}
        data_collect.update_one({'_id': keys[0]}, data, upsert=True)
    else:
        # nested document
        joined_key = 'data.' + '.'.join(keys[1:])
        data = {"$set": {joined_key: dict_data}}
        data_collect.update_one({'_id': keys[0]}, data, upsert=True)

    socketio.emit('update', {'collection': request_info.collection, 'keys': keys, "data": dict_data})
    return ''


if __name__ == '__main__':
    socketio.run(app, debug=True)
