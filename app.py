from flask import Flask, Response, request, render_template, jsonify, json
import pymongo
import re
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

        # check for .json ending
        if len(self.key) > 0 :
            temp = self.key[-1].split(".")
            if len(temp) >= 2:
                self.key[-1] = temp[0]
        else:
            temp = self.collection.split(".")
            if len(temp) >= 2:
                self.collection[-1] = temp[0]

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
        return str(json_data) + "Not a valid json"

    # check if it is a list and then add id to the data
    if type(dict_data) is list:
        dict_data = list(map(lambda x, y: {"_id": str(x), "data": y}, range(len(dict_data)), dict_data))
    else:
        raise NotImplementedError

    keys = request_info.key

    # check the length of keys
    num_key = len(keys)

    if num_key == 0: # no sub key, just insert into the collection
        data_collect.drop()
        data_collect.insert_many(dict_data)
    elif num_key == 1:
        data = {"$set": {'data': dict_data}}
        data_collect.update_one({'_id': keys[0]}, data, upsert=True)
    else:
        # nested document
        raise NotImplementedError


    # return data that is insert into the database
    return jsonify(dict_data)


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
            cursor = data_collect.find({}, {'data':1, '_id':0})
        elif num_key == 1:
            cursor = data_collect.find({'_id': keys[0]}, {'data': 1, '_id': 0})
        else:
            # nested document
            raise NotImplementedError

    else:
        if num_key > 0:
            raise NotImplementedError
        else:

            # if there exist operators
            match = {}
            operators = request_info.operators
            pipeline = []
            if 'orderBy' in operators:
                target_var = 'data.' + operators['orderBy']
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
                            sort = {'$sort':{target_var:1}}
                            pipeline.append(sort)
                            pipeline.append(limit)
                        elif operation == 'limitToLast':
                            limit = {'$limit': int(operators[operation])}
                            sort = {'$sort':{target_var:-1}}
                            pipeline.append(sort)
                            pipeline.append(limit)
                        else:
                            sort = ''
                if pipeline == []:
                    return "Error: Operation not found"
                cursor = data_collect.aggregate(pipeline)

        """
        Implement this
        """
        data = "Need to implement methods for operators"

    data = []

    for document in cursor:
        # loop over keys to get only the stored value
        temp = document['data']
        data.append(temp)

    if len(data) == 0:
        data.append("Error: data not found")
    return str(data)


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

    if num_key == 1:
        data = {"$set": {"data": dict_data}}
        # check if the key exists
        cursor = data_collect.find({keys[0]: {"$exists": True}})

        if len(list(cursor)) > 0: # already exists
            N = 8
            # using random.choices()
            # generating random strings
            res = ''.join(random.choices(string.ascii_letters, k=N))

            data_collect.insert_one({keys[0] + '_' + res: dict_data})
            msg = str({"name": keys[0]+'_'+res})
        else:
            data_collect.insert_one({keys[0]: dict_data})
            msg = ''

    else:

        joined_key = '.'.join(keys)
        cursor = data_collect.find({joined_key: {"$exists": True}})
        if len(list(cursor)) > 0:  # already exists:
            N = 8
            # using random.choices()
            # generating random strings
            res = ''.join(random.choices(string.ascii_letters, k=N))

            data = {"$set": {joined_key + '_' +res: dict_data}}
            data_collect.update_one({keys[0]: {"$exists": True}}, data, upsert=True)
            msg = str({"name": keys[-1] + '_' + res})
        else:
            data = {"$set": {joined_key: dict_data}}
            data_collect.update_one({keys[0]: {"$exists": True}}, data, upsert=True)
            msg = ''

    return msg


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
        raise NotImplementedError

    return ""


@app.route('/<path:myPath>', methods=['PATCH'])
def catach_all_patch(myPath):
    request_info = RequestInfo()

    db = MongoDB(request_info.root_database)
    collection = db[request_info.collection]
    json_data = request_info['data']

    return "PATCH"


if __name__ == '__main__':
    app.run(debug=True)
