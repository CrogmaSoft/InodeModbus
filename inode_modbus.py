import copy
import json
import time
import queue
import asyncio
import pymongo

from bson import json_util
from mqtt_client import mqtt_client
from modbus_operator import modbus_operator

CONFIG = None
CONFIG_PATH = "CONFIG.json"
CONFIG_READY = False
FORCED_CONFIG_UPDATE = False

AUTOQUERY_ENABLED = False
AUTOQUERY_RESTART = False

MAX_COUNTDOWN = 15

async def inodemodbus_queue():
    try:
        print(f'\nINODE MODBUS - {CONFIG["operator_id"]}\n')

        plc.connect()         
        mqtt_modbus_client.run()

        # TODO: Reload subscription on config change
        mqtt_topic = CONFIG["modbus_config"]["mqtt_config"]["mqtt_topic"]
        mqtt_modbus_client.sub(mqtt_topic)

        print("\nMQTT | Listening for queries at: " + mqtt_topic)

        await check_modbus_connection(0, True)

        base_countdown = MAX_COUNTDOWN * 60 * 100 # TODO: This should be retrieved from CONFIG o maybe removed?
        countdown = base_countdown

        while True:
            if not mqtt_queue.empty():
                msg = mqtt_queue.get_nowait()
                ret = compute(msg[1])
                mqtt_modbus_client.pub(mqtt_topic + "/response", ret)
                countdown = base_countdown
            
            if countdown == 0:
                print(f"No messages received after {MAX_COUNTDOWN} minutes")
                print(f"MQTT Queue empty: {mqtt_queue.empty()}")
                print(f"MQTT Queue full: {mqtt_queue.full()}")
                print(f"MQTT Client status: {mqtt_client.get_state()}")
                countdown = base_countdown

            countdown -= 1

            await asyncio.sleep(0.001) #TODO: Setup with proc_delay property from CONFIG
        
    except Exception as e:
        print(f"Error at inodemodbus_queue() | {str(e)}")


async def check_modbus_connection(seconds, check_only = False):
    keep_reg = CONFIG["modbus_config"]["keep_reg"]
    modbus_addr = CONFIG["modbus_config"]["modbus_addr"]
    mqtt_topic = CONFIG["modbus_config"]["mqtt_config"]["mqtt_topic"]

    if not check_only:
        while True:
            try:
                if keep_reg != -1:
                    ec = plc.read_bit(keep_reg, modbus_addr)
                    if ec == "No Connection":
                        mqtt_modbus_client.pub(mqtt_topic + "/ERROR ", ec)
            except Exception as error:
                print(f"Error at inodemodbus_queue() | {str(error)}")
                mqtt_modbus_client.pub(mqtt_topic + "/ERROR ", error)              
            await asyncio.sleep(seconds)
    else:
        if keep_reg != -1:
            ec = plc.read_bit(keep_reg, modbus_addr)
            if ec == "No Connection":
                mqtt_modbus_client.pub(mqtt_topic + "/ERROR ", ec)


async def generate_autoquery(config_interval):
    while True:
        try:
            if CONFIG_READY:
                mqtt_topic = CONFIG["modbus_config"]["mqtt_config"]["mqtt_topic"]            
                registers = CONFIG["modbus_config"]["autoquery_config"]["registers"]
                modbus_query = json.dumps(
                    {
                        "order": 9009001,
                        "read_registers": {
                            "types_lists": registers,
                            "addr": 1,
                            "_type": "multiType",
                            "_timer": 0.5,
                            "_regLen": CONFIG["modbus_config"]["_regLen"],
                        },
                    }
                )
                ret = compute(modbus_query)
                mqtt_modbus_client.pub(mqtt_topic + "/response", ret)
            else:
                print("Waiting for CONFIG...")
        except Exception as e:
            print("Error at generate_autoquery()")
            print(str(e))
        await asyncio.sleep(config_interval)


async def autoquery_manager(seconds):
    global AUTOQUERY_RESTART

    if CONFIG_READY and AUTOQUERY_ENABLED == True:
        autoquery_task = asyncio.create_task(
            generate_autoquery(
                CONFIG["modbus_config"]["autoquery_config"]["intervalms"] / 1000
            )
        )
   
    while True:
        if CONFIG_READY:
            if AUTOQUERY_RESTART == True and AUTOQUERY_ENABLED == True:
                print("Canceling autoquery_task")
                AUTOQUERY_RESTART = False
                autoquery_task.cancel()
                print("(Re)Starting autoquery_task")
                autoquery_task = asyncio.create_task(
                    generate_autoquery(
                        CONFIG["modbus_config"]["autoquery_config"]["intervalms"] / 1000
                    )
                )
            await asyncio.sleep(seconds)


def update_modbus_config():
    global CONFIG
    global CONFIG_READY
    global AUTOQUERY_RESTART
    global AUTOQUERY_ENABLED

    try:
        with open(CONFIG_PATH, "r") as f:
            actual_config = json.load(f)

        if actual_config["operator_id"] == None:
            raise Exception("In CONFIG.json: operator_id can't be null")

        mongo_client = pymongo.MongoClient(actual_config["mongo_config"]["conn_str"])
        operator_id = actual_config["operator_id"]
        result = mongo_client["inode_modbus_config"]["config"].find(
            filter={"operator_id": operator_id}
        )
        config_list = list(result)

        if config_list.__len__() == 0:
            raise Exception(
                f'Could not retrieve any config for this operator_id: {actual_config["operator_id"]}'
            )
        modbus_config = json.loads(json_util.dumps((config_list)))[0]["modbus_config"]

        new_config = copy.deepcopy(actual_config)
        new_config["modbus_config"] = modbus_config

        with open(CONFIG_PATH, "w") as f:
            json.dump(new_config, f, indent=4)

        CONFIG = new_config

        if CONFIG["modbus_config"] == None:
            raise Exception(
                "In CONFIG.json: modbus_config could not be loaded from MongoDB"
            )

        CONFIG_READY = True
        AUTOQUERY_ENABLED = new_config["modbus_config"]["autoquery_config"]["enabled"]

        previ = actual_config["modbus_config"]["autoquery_config"]["intervalms"]
        newi = new_config["modbus_config"]["autoquery_config"]["intervalms"]

        if AUTOQUERY_ENABLED == True and previ != newi:
            AUTOQUERY_RESTART = True
    except Exception as e:
        print(str(e))


async def check_config_updates(seconds):
    global FORCED_CONFIG_UPDATE
    while True:
        if FORCED_CONFIG_UPDATE == True:
            FORCED_CONFIG_UPDATE = False
        else:
            update_modbus_config()
        await asyncio.sleep(seconds)


async def tasks_manager():
    tasks = []
    tasks.append(asyncio.create_task(check_config_updates(10)))
    tasks.append(asyncio.create_task(autoquery_manager(1)))
    tasks.append(asyncio.create_task(inodemodbus_queue()))
    tasks.append(asyncio.create_task(check_modbus_connection(60)))
    for task in tasks:
        await task


def getDecoderType(dataType):
    if dataType == "input" or dataType == "discrete_input":
        return dataType
    if dataType == "holdingstring":
        return "string"
    elif dataType == "holdingbits":
        return "bits"
    elif dataType == "holdingint8":
        return "8_int"
    elif dataType == "holdinguint8":
        return "8_uint"
    elif dataType == "holdingint16":
        return "16_int"
    elif dataType == "holdingint32":
        return "32_int"
    elif dataType == "holdinguint16":
        return "16_uint"
    elif dataType == "holdinguint32":
        return "32_uint"
    elif dataType == "holdingf16":
        return "16_float"
    elif dataType == "holdingf32":
        return "32_float"
    else:
        return "none"


def compute(msg):
    try:
        _msg = json.loads(msg)
    except Exception as e:
        print(f"Invalid JSON Format - {str(e)}")

    reg_shift = CONFIG["modbus_config"]["reg_shift"]

    global FORCED_CONFIG_UPDATE
    if "force_update" in _msg:
        if FORCED_CONFIG_UPDATE == False and _msg["force_update"] == True:
            FORCED_CONFIG_UPDATE = True
            update_modbus_config()
    else:
        order = _msg["order"]
        if "read_bit" in _msg:
            if "_count" in _msg["read_bit"]:
                _bobina = _msg["read_bit"]["bobina"]
                _count = _msg["read_bit"]["_count"]
                _addr = _msg["read_bit"]["addr"]
                try:
                    ret = plc.read_bit(_bobina, _addr, _count=_count)
                except Exception as e:
                    ret = e
            else:
                _bobina = _msg["read_bit"]["bobina"]
                _addr = _msg["read_bit"]["addr"]
                try:
                    ret = plc.read_bit(_bobina, _addr)
                except Exception as e:
                    ret = e

            return json.dumps({"order": order, "result": {str(_bobina): ret}})

        elif "read_bits" in _msg:
            _reg_list = _msg["read_bits"]["lista"]
            _addr = _msg["read_bits"]["addr"]
            if "timer" in _msg["read_bits"]:
                _timer = _msg["read_bits"]["timer"]
                try:
                    env = {}
                    ret = plc.read_bits(_reg_list, _addr, timer=_timer)

                    for z, n in enumerate(_reg_list):
                        env[str(n)] = ret[z]
                except Exception as e:
                    env = e
            else:
                try:
                    env = {}
                    ret = plc.read_bits(_reg_list, _addr)
                    for z, n in enumerate(_reg_list):
                        env[str(n)] = ret[z]
                except Exception as e:
                    env = e

            return json.dumps({"order": order, "result": env})

        elif "write_bit" in _msg:
            _bobina = _msg["write_bit"]["bobina"]
            _addr = _msg["write_bit"]["addr"]
            _valor = _msg["write_bit"]["valor"]
            try:
                ret = plc.write_bit(_bobina, _addr, _valor)
            except Exception as e:
                ret = e
            return json.dumps(
                "order_result",
                json.dumps({"order": order, "result": {str(_bobina): ret}}),
            )

        elif "read_register" in _msg:
            _register = _msg["read_register"]["register"] + reg_shift
            _addr = _msg["read_register"]["addr"]
            if "_count" and "_type" in _msg["read_register"]:
                _count = _msg["read_register"]["_count"]
                _type = _msg["read_register"]["_type"]
                try:
                    ret = plc.read_register(
                        _register, _addr, _count=_count, _type=_type
                    )
                except Exception as e:
                    ret = e
            elif (
                "_count" in _msg["read_register"]
                and not "_type" in _msg["read_register"]
            ):
                _count = _msg["read_register"]["_count"]
                try:
                    ret = plc.read_register(_register, _addr, _count=_count)
                except Exception as e:
                    ret = e
            elif (
                "_type" in _msg["read_register"]
                and not "_count" in _msg["read_register"]
            ):
                _type = _msg["read_register"]["_type"]
                try:
                    ret = plc.read_register(_register, _addr, _type=_type)
                except Exception as e:
                    ret = e
            else:
                try:
                    ret = plc.read_register(_register, _addr)
                except Exception as e:
                    ret = e
            return json.dumps({"order": order, "result": {str(_register): ret}})

        elif "read_registers" in _msg:
            _addr = _msg["read_registers"]["addr"]

            if "types_lists" in _msg["read_registers"]:
                _reg_list = _msg["read_registers"]["types_lists"]
            else:
                _reg_list = _msg["read_registers"]["lista"]

            if "_type" and "_timer" in _msg["read_registers"]:
                _type = _msg["read_registers"]["_type"]
                _timer = _msg["read_registers"]["_timer"]
                try:
                    env = {}
                    if _type == "multiType":
                        readList = []

                        for attribute, value in _reg_list.items():
                            dataType = attribute
                            readList = value

                            if reg_shift != 0:
                                readList = [reg + reg_shift for reg in readList]

                            decoderType = getDecoderType(dataType)

                            if decoderType == "bits":
                                if "_regLen" in _msg["read_registers"]:
                                    for readbit in readList:
                                        ret = plc.read_bit(
                                            int(readbit),
                                            _addr,
                                            _count=_msg["read_registers"]["_regLen"],
                                        )
                                        if "_readBit" in _msg["read_registers"]:
                                            env[str(readbit)] = ret[
                                                _msg["read_registers"]["_readBit"] - 1
                                            ]
                                        else:
                                            env[str(readbit)] = ret
                                else:
                                    ret = plc.read_bit(readList, _addr)
                            else:
                                try:
                                    ret = plc.read_registers(
                                        readList, _addr, _type=dataType, _timer=_timer
                                    )
                                except Exception as e:
                                    print(str(e))

                            if decoderType != "bits":
                                for z, n in enumerate(readList):
                                    if ret[z] != 0 and (decoderType == "32_float" or decoderType == "32_int" or decoderType == "32_uint"):
                                        decoded = plc.decoder(decoderType, ret[z])
                                        env[str(n)] = decoded
                                    else:
                                        env[str(n)] = ret[z]

                    else:
                        ret = plc.read_registers(
                            _reg_list, _addr, _type=_type, _timer=_timer
                        )
                        for z, n in enumerate(_reg_list):
                            if _type == "holdingstring":
                                decoded = plc.decoder("string", ret[z])
                                env[str(n)] = decoded
                            if _type == "holdingbits":
                                decoded = plc.decoder("bits", ret[z])
                                env[str(n)] = decoded
                            if _type == "holdingint8":
                                decoded = plc.decoder("8_int", ret[z])
                                env[str(n)] = decoded
                            if _type == "holdinguint8":
                                decoded = plc.decoder("8_uint", ret[z])
                                env[str(n)] = decoded
                            if _type == "holdingint16":
                                decoded = plc.decoder("16_int", ret[z])
                                env[str(n)] = decoded
                            if _type == "holdingint32":
                                decoded = plc.decoder("32_int", ret[z])
                                env[str(n)] = decoded
                            if _type == "holdinguint16":
                                decoded = plc.decoder("16_uint", ret[z])
                                env[str(n)] = decoded
                            if _type == "holdinguint32":
                                decoded = plc.decoder("32_uint", ret[z])
                                env[str(n)] = decoded
                            if _type == "holdingf16":
                                decoded = plc.decoder("16_float", ret[z])
                                env[str(n)] = decoded
                            elif _type == "holdingf32":
                                decoded = plc.decoder("32_float", ret[z])
                                env[str(n)] = decoded
                            else:
                                env[str(n)] = ret[z]
                except Exception as e:
                    env = {f"error_{_type}": str(e)}
                    print(env)
            elif (
                "_type" in _msg["read_registers"]
                and not "_timer" in _msg["read_registers"]
            ):
                _type = _msg["read_registers"]["_type"]
                try:
                    env = {}
                    ret = plc.read_registers(_reg_list, _addr, _type=_type)
                    for z, n in enumerate(_reg_list):
                        env[str(n)] = ret[z]
                except Exception as e:
                    env = e
            elif (
                "_timer" in _msg["read_registers"]
                and not "_type" in _msg["read_registers"]
            ):
                _timer = _msg["read_registers"]["_timer"]
                try:
                    env = {}
                    ret = plc.read_registers(_reg_list, _addr, _timer=_timer)
                    for z, n in enumerate(_reg_list):
                        env[str(n)] = ret[z]
                except Exception as e:
                    env = e
            else:
                try:
                    env = {}
                    ret = plc.read_registers(_reg_list, _addr)
                    for z, n in enumerate(_reg_list):
                        env[str(n)] = ret[z]
                except Exception as e:
                    env = e

            return json.dumps({"order": order, "result": env})

        elif "write_register" in _msg:
            _register = _msg["write_register"]["registro"] + reg_shift
            _addr = _msg["write_register"]["addr"]
            _value = _msg["write_register"]["valor"]
            _type = _msg["write_register"]["_type"]

            try:
                _type = getDecoderType(_type)
                if _type == "bits":
                    if (
                        "_writeBit" in _msg["write_register"]
                        and "_regLen" in _msg["write_register"]
                    ):
                        _bit = _msg["write_register"]["_writeBit"]
                        _regLen = _msg["write_register"]["_regLen"]
                        ret = plc.write_bits(
                            _register, _addr, _value, _bit, _count=_regLen
                        )
                else:
                    ret = plc.write_register(_register, _addr, _type, _value)
            except Exception as e:
                ret = e
                return json.dumps({"order": order, "result": {"error": str(ret)}})

            return json.dumps({"order": order, "result": {str(_register): str(ret)}})

        elif "encoder" in _msg:
            _type = _msg["encoder"]["_type"]
            _value = _msg["encoder"]["value"]
            try:
                ret = plc.encoder(_type, _value)
            except Exception as e:
                ret = e

            return json.dumps({"order": order, "result": ret})

        elif "decoder" in _msg:
            _type = _msg["decoder"]["_type"]
            _value = _msg["decoder"]["value"]
            try:
                ret = plc.decoder(_type, _value)
            except Exception as e:
                ret = e
            return json.dumps({"order": order, "result": ret})


if __name__ == "__main__":
    try:
        update_modbus_config()
        mqtt_queue = queue.Queue()
        # TODO: Reload MQTT client on config change
        mqtt_modbus_client = mqtt_client(CONFIG, mqtt_queue)
        # TODO: Reload MODBUS client on config change
        plc = modbus_operator(CONFIG)
        asyncio.run(tasks_manager()) 
    except Exception as e:
        print(str(e))

# TODO:
# Reload MODBUS client on config change
# Reload MQTT client on config change
# Reload MQTT subscription on config change
