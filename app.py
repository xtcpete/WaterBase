from flask import Flask, Response, request, render_template, jsonify, json
import pymongo
import re


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
    operators: dictionary that store all operators in the request.
        Key is the name, Values are lists;
        The first element is the operator, e.g. =， >, >=
        The second element is the value
    """

    def __init__(self):
        self.root_database = "root"
        self.paths = request.path.split('/')[1:]
        self.collection = "database"
        self.fullpath = request.full_path
        self.data = request.get_data().decode('utf-8')
        self.operators = {}
        self.key = self.paths

        # check for .json ending
        temp = self.key[-1].split(".")
        if len(temp) >= 2:
            self.key[-1] = temp[0]

        # check for operators
        temp = self.paths[-1].split("?")
        if len(temp) >= 2:
            operators_str = temp[1]
            operators_list = operators_str.split("&")
            for operators in operators_list:
                operator = re.findall(r'(=|>|<)', operators)
                # check if there are two operator; e.g ">", "="
                if len(operator) == 2:
                    if operator[1] == "=":
                        operator = "".join(operator)
                else:
                    operator = operator[0]

                name_value = operators.split(operator)
                name = name_value[0]
                value = name_value[1]

                self.operators[name] = [operator, value]


app = Flask(__name__)


@app.route('/<path:myPath>', methods=['PUT'])
def catch_all_put(myPath):
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
    else:
        # nested documents
        """
        need to implement this
        """
        return "PUT: Need to implement access to nested document"
    data_collect.update_one({"_id": keys[0]}, data, upsert=True)

    # return data that is insert into the database
    return jsonify(dict_data)


@app.route('/<path:myPath>', methods=['GET'])
def catch_all_get(myPath):
    request_info = RequestInfo()

    db = MongoDB(request_info.root_database).db

    # access the collection
    data_collect = db[request_info.collection]

    # find the data
    if request_info.operators == {}:
        # check for the number of keys
        if len(request_info.key) > 1:
            return "Get: Need to implement method for nested documents"
        else:
            cursor = data_collect.find({"_id": request_info.key[0]}, {"_id": 0})
    else:
        # if there exist operators
        """
        Implement this
        """
        data = "Need to implement methods for operators"

    data = []

    for document in cursor:
        data.append(str(document['data']))

    if len(data) == 0:
        data.append("Error: {key} not found".format(key=request_info.key[0]))

    return jsonify(data[0])


@app.route('/<path:myPath>', methods=['POST'])
def catch_all_post(myPath):
    """
    :param myPath:
    :return:
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
        cursor = data_collect.find({"_id": {"$regex": keys[0]}})
        num_matched = len(list(cursor))
    else:
        # nested documents
        """
        need to implement this
        """
        return "POST: Need to implement access to nested document"

    if num_matched > 0:
        data_collect.insert_one({"_id": keys[0] + '_' + str(num_matched), "data": dict_data})
        msg = "Generated New Key: " + keys[0] + '_' + str(num_matched) + " " + str(dict_data)
    else:
        data_collect.insert_one({"_id": keys[0], "data": dict_data})
        msg = str(dict_data)
    # return data that is insert into the database
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

    if num_key == 1:
        # check if the key exists
        data_collect.delete_one({"_id": keys[0]})
    else:
        # nested documents
        """
        need to implement this
        """
        return "DELETE: Need to implement access to nested document"

    return "DELETED"


@app.route('/<path:myPath>', methods=['PATCH'])
def catach_all_patch(myPath):
    request_info = RequestInfo()

    db = MongoDB(request_info.root_database)
    collection = db[request_info.collection]
    json_data = request_info['data']

    return "PATCH"


if __name__ == '__main__':
    app.run(debug=True)
