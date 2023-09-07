from pymodbus.client import ModbusSerialClient as ModbusClient
from pymodbus.client import ModbusTcpClient as ModbustcpClient
from pymodbus.exceptions import *
from pymodbus.pdu import ExceptionResponse
from pymodbus.constants import Endian
from pymodbus.payload import BinaryPayloadDecoder
from pymodbus.payload import BinaryPayloadBuilder
import time


class modbus_operator(object):
    def __init__(self, config):
        self.config = config["modbus_config"]
        self.endian_bytes = None
        self.endian_words = None
        self.type = self.config["modbus_type"]
        self.addr = self.config["modbus_addr"]
        self.endian_bytes_config = self.config["endian_bytes"]
        self.endian_words_config = self.config["endian_words"]

        if self.endian_bytes_config == "BIG":
            self.endian_bytes = Endian.Big
        else:
            self.endian_bytes = Endian.Little

        if self.endian_words_config == "BIG":
            self.endian_words = Endian.Big
        else:
            self.endian_words = Endian.Little

        if self.type == "rs-485":
            rtu_config = self.config["rtu_config"]
            self.port = rtu_config["rtu_port"]
            self.baudrate = rtu_config["rtu_baudrate"]
            self.bitsize = rtu_config["rtu_bitsize"]
            self.parity = rtu_config["rtu_parity"]
            self.stopbit = rtu_config["rtu_stopbit"]
            self.timeout = rtu_config["timeout"]
            self.connection = False
            self._state = ""
        elif self.type == "tcp":
            tcp_config = self.config["tcp_config"]
            self.tcp_host = tcp_config["tcp_host"]
            self.tcp_port = tcp_config["tcp_port"]

    def mark_print(self, arg):
        print(f"PLC | {str(arg)}")

    def create_client(self):
        if self.type == "rs-485":
            self.client = ModbusClient(
                method="rtu",
                stopbits=self.stopbit,
                bytesize=self.bitsize,
                parity=self.parity,
                baudrate=self.baudrate,
                port=self.port,
                timeout=self.timeout,
            )
            self.mark_print("RTU client created")
        elif self.type == "tcp":
            self.client = ModbustcpClient(host=self.tcp_host, port=self.tcp_port)
            self.mark_print("TCP client created")

    def reconnect(self):
        self.mark_print("Reconnecting")
        self.close()
        time.sleep(2)
        self.connect()

    def value_error(self, error):
        if type(error) == ModbusIOException:
            self._state = "Not connected: ModbusIOException"
            self.connection = False
            self.mark_print(f"ERROR > {self._state} | {error}")
            return "No Connection"
        elif type(error) == ParameterException:
            self._state = "Parameter Error: ParameterException"
            self.mark_print(f"ERROR > {self._state} | {error}")
            return "Parameter Error"
        elif type(error) == NoSuchSlaveException:
            self._state = "Slave Error:  NoSuchSlaveException"
            self.mark_print(f"ERROR > {self._state} | {error}")
            return "No such slave"
        elif type(error) == ConnectionException:
            self._state = "Connection: ConnectionException"
            self.mark_print(f"ERROR > {self._state} | {error}")
            return "Connection Failed"
        elif type(error) == ExceptionResponse:
            error_code = error.exception_code
            if error_code == 2:
                error_msg = f"Error code {str(error_code)} > Illegal Address Error"
            self.mark_print(error_msg)
            return error_msg
        return False

    def connect(self):
        self.mark_print("Setting up PLC connection")
        try:
            self.create_client()
            self.mark_print("PLC query client created")
        except Exception as error:
            self.mark_print("Could not create the PLC query client\n" + error)
            self._state = error
            self.mark_print(self._state)

        try:
            self.mark_print("Loading PLC connection")
            self.connection = self.client.connect()
        except Exception as error:
            self.mark_print("Failed to create the connection\n" + error)
            self._state = error
            self.mark_print(self._state)

        if self.connection:
            self._state = "Connected"
            self.mark_print("Client connected and ready. Awaiting for queries...")
        else:
            self._state = "Not connected"
            self.mark_print("PLC offline, awaiting re-connection...")

        if self.config["keep_reg"] != -1:
            while True:
                try:
                    rr = self.read_bit(self.config["keep_reg"], self.addr)
                    if type(rr) is bool:
                        self.mark_print("Connection stablished")
                        break
                    if rr != "No Connection" and rr.find("Error") == -1:
                        self.mark_print("Connection stablished")
                        break
                    else:
                        self._state = "No communication"
                        self.mark_print(
                            "There's no response from the PLC, please check the keep alive read_bit \nor verify connections to the device"
                        )
                except Exception as error:
                    print(f"Error at plc.connect() | {str(error)}")
                    pass
                self.mark_print(self._state)
                time.sleep(1)
        else:
            self.mark_print(
                "There's no keep alive register configured, forwarding connection..."
            )
            self.mark_print("Connection stablished")

    def close(self):
        if self.connection:
            self.client.close()
            self.mark_print("client close")

        else:
            pass

    def read_bit(self, coil, addr, _count=1):
        if self.connection == False:
            self.reconnect()
        try:
            rr = self.client.read_coils(coil, count=_count, unit=addr)
        except Exception as e:
            print(str(e))

        if not rr.isError() and _count == 1:
            return rr.bits[0]
        elif not rr.isError() and _count > 1:
            return rr.bits
        else:
            exit = self.value_error(rr)
            return exit

    def read_bits(self, bit_list, addr, timer=0.05):
        if self.connection == False:
            self.reconnect()

        Out = []
        if type(bit_list) is list:
            for value in bit_list:
                rr = self.client.read_coils(value, 1, unit=addr)

                if not rr.isError():
                    Out.append(rr.bits[0])
                else:
                    exit = self.value_error(rr)
                    Out.append(exit)
                time.sleep(timer)
            return Out
        else:
            self.mark_print("Value is not of type list")

    def write_bit(self, coil, addr, value):
        if self.connection == False:
            self.reconnect()

        rr = self.client.write_coil(coil, value, unit=addr)

        if not rr.isError():
            return rr.bits[0]
        else:
            exit = self.value_error(rr)
            return exit

    def write_bits(self, register, addr, value, bit, _count=1):
        if value == 0 or value == 1:
            bitList = self.read_bit(register, addr, _count)

            bitList[bit] = bool(value)

            if self.connection == False:
                self.reconnect()

            rr = self.client.write_coils(register, bitList, unit=addr)

            #bitList = self.read_bit(register, addr, _count)

            if not rr.isError():
                return rr
            else:
                exit = self.value_error(rr)
                return exit
        else:
            exit = self.value_error(rr)
            return exit

    def read_register(
        self, register, addr, _count=2, _type="holding", raw_response=False
    ):
        if self.connection == False:
            self.reconnect()

        if _type == "input":
            rr = self.client.read_input_registers(register, _count, addr)

        if _type == "discrete_input":
            rr = self.client.read_discrete_inputs(register, _count, addr)

        elif _type == "holding":
            rr = self.client.read_holding_registers(register, _count, addr)

        if not rr.isError():
            if raw_response:
                return rr
            else:
                if _count == 1:
                    return rr.registers[0]
                else:
                    return rr.registers[0:]
        else:
            exit = self.value_error(rr)
            return exit

    def read_registers(self, reg_list, addr, _type, _timer):
        if self.connection == False:
            self.reconnect()

        Out = []
        _count = 1
        if type(reg_list) is list:
            for value in reg_list:

                if _type == "discrete_input":   # FC 2 <
                    _count = 1
                    rr = self.read_register(
                        value, addr, _count, _type="discrete_input", raw_response=True
                    )
                
                elif _type == "input":          # FC 4 <
                    _count = 1
                    rr = self.read_register(
                        value, addr, _count, _type="input", raw_response=True
                    )

                elif _type == "holding":        # FC 3 v
                    _count = 1
                    rr = self.client.read_holding_registers(
                        value, count=_count, unit=addr
                    )

                elif _type == "holdingstring":
                    _count = 4
                    rr = self.client.read_holding_registers(
                        value, count=_count, unit=addr
                    )

                elif _type == "holdingbit":
                    _count = 1
                    rr = self.client.read_holding_registers(
                        value, count=_count, unit=addr
                    )
                # TODO: Controlar que sólo se puedan consultar registros de al menos el tamaño definido en configuración (_regLen)
                elif _type == "holdinguint8":
                    _count = 1
                    rr = self.client.read_holding_registers(
                        value, count=_count, unit=addr
                    )

                elif _type == "holdinguint16":
                    _count = 1
                    rr = self.client.read_holding_registers(
                        value, count=_count, unit=addr
                    )

                elif _type == "holdinguint32":
                    _count = 2
                    rr = self.client.read_holding_registers(
                        value, count=_count, unit=addr
                    )

                elif _type == "holdingint8":
                    _count = 1
                    rr = self.client.read_holding_registers(
                        value, count=_count, unit=addr
                    )

                elif _type == "holdingint16":
                    _count = 1
                    rr = self.client.read_holding_registers(
                        value, count=_count, unit=addr
                    )

                elif _type == "holdingint32":
                    _count = 2
                    rr = self.client.read_holding_registers(
                        value, count=_count, unit=addr
                    )

                elif _type == "holdingf16":
                    _count = 1
                    rr = self.client.read_holding_registers(
                        value, count=_count, unit=addr
                    )

                elif _type == "holdingf32":
                    _count = 2
                    rr = self.client.read_holding_registers(value, _count, addr)

                if not rr.isError():
                    if _count == 1:
                        Out.append(rr.registers[0])
                    else:
                        Out.append(rr.registers[0:])
                else:
                    exit = self.value_error(rr)
                    Out.append(exit)
                    time.sleep(_timer)
            return Out
        else:
            self.mark_print("Value is not of type list")

    def write_register(self, register, addr, type, value):
        if self.connection == False:
            self.reconnect()

        payload = self.encoder(type, value)
        rr = self.client.write_registers(register, payload, skip_encode=True, unit=addr)

        if not rr.isError():
            return rr
        else:
            exit = self.value_error(rr)
            return exit

    def encoder(self, _type, value):
        encoder = BinaryPayloadBuilder(
            byteorder=self.endian_bytes,
            wordorder=self.endian_words,
        )
        if _type == "input":  # TODO: Check reg leng for encoding or decoding input regs
            assert isinstance(
                value, int
            ), "BinaryPayloadBuilder> input - add_16bit_uint: warning! Value is not 6bit_uint!"
            encoder.add_16bit_uint(value)

        if (
            _type == "discrete_input"
        ):  # TODO: Check reg leng for encoding or decoding input regs
            assert isinstance(
                value, int
            ), "BinaryPayloadBuilder> discrete_input - add_16bit_uint: warning! Value is not 6bit_uint!"
            encoder.add_16bit_uint(value)

        if _type == "string":
            assert isinstance(
                value, str
            ), "BinaryPayloadBuilder> add_string: warning! Value is not string!"
            encoder.add_string(str(value))
        elif _type == "bits":
            assert isinstance(
                value, list
            ), "BinaryPayloadBuilder> add_bits: warning! Value is not list!"
            encoder.add_bits(value)
        elif _type == "8_int":
            assert isinstance(
                value, int
            ), "BinaryPayloadBuilder> add_8bit_int: warning! Value is not integer!"
            encoder.add_8bit_int(hex(value))
        elif _type == "8_uint":
            assert isinstance(
                value, int
            ), "BinaryPayloadBuilder> add_8bit_uint: warning! Value is not integer!"
            encoder.add_8bit_uint(hex(value))
        elif _type == "16_int":
            assert isinstance(
                value, int
            ), "BinaryPayloadBuilder> add_16bit_int: warning! Value is not integer!"
            encoder.add_16bit_int(hex(value))
        elif _type == "16_uint":
            assert isinstance(
                value, int
            ), "BinaryPayloadBuilder> add_16bit_uint: warning! Value is not integer!"
            encoder.add_16bit_uint(hex(value))
        elif _type == "32_int":
            assert isinstance(
                value, int
            ), "BinaryPayloadBuilder> add_32bit_int: warning! Value is not integer!"
            encoder.add_32bit_int(hex(value))
        elif _type == "32_uint":
            assert isinstance(
                value, int
            ), "BinaryPayloadBuilder> add_32bit_uint: warning! Value is not integer!"
            encoder.add_32bit_uint(hex(value))
        elif _type == "16_float":
            assert isinstance(
                value, float
            ), "BinaryPayloadBuilder> add_16bit_float: warning! Value is not float!"
            encoder.add_16bit_float(value)
        elif _type == "32_float":
            assert isinstance(
                value, float
            ), "BinaryPayloadBuilder> add_32bit_float: warning! Value is not float!"
            encoder.add_32bit_float(value)
        return encoder.build()

    def decoder(self, _type, value):
        decoder = BinaryPayloadDecoder.fromRegisters(
            value,
            byteorder=self.endian_bytes,
            wordorder=self.endian_words,
        )

        if _type == "input":
            return (
                decoder.decode_16bit_uint()
            )  # TODO: Check reg leng for encoding or decoding input regs
        if _type == "discrete_input":
            return (
                decoder.decode_16bit_uint()
            )  # TODO: Check reg leng for encoding or decoding input regs
        if _type == "bits":
            return decoder.decode_bits()
        if _type == "string":
            return decoder.decode_string()
        elif _type == "8_int":
            return decoder.decode_8bit_int()
        elif _type == "8_unit":
            return decoder.decode_8bit_uint()
        elif _type == "16_int":
            return decoder.decode_16bit_int()
        elif _type == "16_uint":
            return decoder.decode_16bit_uint()
        elif _type == "32_int":
            return decoder.decode_32bit_int()
        elif _type == "32_uint":
            return decoder.decode_32bit_uint()
        elif _type == "16_float":
            return decoder.decode_16bit_float()
        elif _type == "32_float":
            return decoder.decode_32bit_float()
