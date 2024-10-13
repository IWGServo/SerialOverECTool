from dataclasses import dataclass
from re import T
import pysoem
import ctypes
import time
import timeit
class StateMachine():
    # Statusword 6041
    NOT_READY_TO_SWITCH_ON = 0b0000_0000
    SWITCH_ON_DISABLED =     0b0100_0000
    READY_TO_SWITCH_ON =     0b0010_0001
    SWITCHED_ON =            0b0010_0011
    OPERATION_ENABLED =      0b0010_0111
    QUICK_STOP_ACTIVE =      0b0000_0111
    FAULT_REACTION_ACTIVE =  0b0000_1111
    FAULT =                  0b0000_1000

    # Controlword 6040 commands:
    SHUTDOWN =               0b0000_0110
    SWITCH_ON =              0b0000_0111 # Verify
    ENABLE_OPERATION =       0b0000_1111
    DISABLE_VOLTAGE =        0b0000_0000
    QUICK_STOP =             0b0000_0010
    DISABLE_OPERATION =      0b0000_0111
    FAULT_RESET =            0b1000_0000

class Master(pysoem.Master):
    _nic_name = None
    mySlaves = []

    def __init__(self) -> None:
        self.connection_status = False
        self.device_count = 0
        super().__init__()

        for nic in pysoem.find_adapters():            
            # If the adapter matches, proceed to open it
            print(f"Searching slaves on {nic.name}...")
            self.open(nic.name)
            self.device_count = self.config_init()
            if self.device_count > 0:
                self.connection_status = True
                print(f"Connected on {nic.name} to {self.device_count} slaves")
                break
            else:
                print(f"no slaves on {nic.name}, next ...")
                self.close()

    def setUpSlaves(self):
        for i,slave in enumerate(self.slaves):
            self.mySlaves.append(mySlave(slave,i))
        return len(self.mySlaves) == len(self.slaves)

class mySlave():
    def __init__(self,slave,position) -> None:
        self.slaveObject = slave
        self.position = position
        self.my_od = self._setupOD()

    def _setupOD(self, try_count=0):
        # From slave.od (object) to self.my_od (dictionary: key = SDO index)
        self.my_od = {}
        try:
            temp_od = self.slaveObject.od # type: ignore
            print("OD Found")
        except pysoem.SdoInfoError as e: # type: ignore
            print(e)
            if try_count < 10:
                print(f"SdoInfoError {try_count}:\t{e}")
                try_count += 1
                self._setupOD(try_count)
        else:
            for obj in temp_od:
                self.my_od[obj.index] = obj
            print(self.slaveObject.name + "OD Created") # type: ignore
            print(f"OD Created for slave {self.position}")
    
    def _sdo_data_from_od(self, index, subindex):
        if not self.my_od:
            self._setupOD()

        coe_obj = self.my_od[index] # type: ignore
        if coe_obj.entries:
            data_type = coe_obj.entries[subindex].data_type
            bit_length = coe_obj.entries[subindex].bit_length
        else:
            data_type = coe_obj.data_type
            bit_length = coe_obj.bit_length
        return data_type, bit_length

    def _choose_ctypes_object(self, data_type:int, bitsize:int):#-> ctypes.c_int8|ctypes.c_int16|ctypes.c_int32|ctypes.c_uint8|ctypes.c_uint16|ctypes.c_uint32|ctypes.c_float|ctypes.c_char_p:
        """ 
        Returns a ctypes object based on the data type and bitsize from slave.od
        dataType    Ctype object
            1       only 2 sync object subindexes 32
            2       INT8
            3       INT16
            4       DINT / INT32
            5       UINT8
            6       UINT16
            7       UINT32
            8       None has been found
            9       String / c_char_p
            32      has enteries
            42      has enteries
        """
        data_type = int(data_type)
        bitsize = int(bitsize)
        match (data_type, bitsize):
            case (2, 8):                # INT8
                return ctypes.c_int8
            case (3, 16):               # INT16
                return ctypes.c_int16
            case (4, 32):               # DINT / INT32
                return ctypes.c_int32
            case (21, 64):               # DINT / INT32
                return ctypes.c_int64
            case (5, 8):                # UINT8
                return ctypes.c_uint8
            case (6, 16):               # UINT16
                return ctypes.c_uint16
            case (7, 32):               # UDINT / UINT32
                return ctypes.c_uint32
            case (27, 64):               # UDINT / UINT64
                return ctypes.c_uint64
            case (8, 32):               # FLOAT32
                return ctypes.c_float   
            case (9, _):                # VISIBLE_STRING
                return ctypes.c_char_p
            case _:
                raise ValueError("Unsupported data type or bitsize")  

    def _convert_from_binary(self, binary_data:bytes, data_type:int, bitsize:int)->str:
        """ Coverting from hex to python data type with _choose_ctypes_object
        _choose_ctypes_object built based on slave.od filetype """
        ctypes_type = self._choose_ctypes_object(data_type, bitsize)
        if (data_type != 9): data = ctypes_type.from_buffer_copy(binary_data).value
        else: data = ctypes_type(binary_data).value.decode() # Decode getting rid of b'...'
        return data

    def _convert_to_binary(self, data, data_type, bitsize)->bytes:
        ctypes_type = self._choose_ctypes_object(data_type, bitsize)
        binary_data = bytes(ctypes_type(data))
        return binary_data

    def readSDO(self, index, subindex)-> str:#, bytesize = None):  # Read & Decode SDO from slave
        try: sdo = self.slaveObject.sdo_read(index, subindex) # type: ignore
            # if bytesize is None: sdo = self.slaveObject.sdo_read(index, subindex)
            # else: sdo = self.slaveObject.sdo_read(index, subindex, bytesize)
        except pysoem.SdoError as e : return e # type: ignore
        # data from dictionary for decoding
        data_type, bit_length = self._sdo_data_from_od(index, subindex)
        return self._convert_from_binary(sdo, data_type, bit_length)

    def writeSDO(self, index, subindex, value)->bool:  # Read & Decode SDO from slave
        # data from dictionary for decoding
        counter=0
        data_type, bit_length = self._sdo_data_from_od(index, subindex)
        # data to binary

        try: self.slaveObject.sdo_write(index, subindex, value.encode('utf-8').hex()) # type: ignore
        except:
            counter=1; 
            pass
        binary_data = self._convert_to_binary(value, data_type, bit_length)
        # Write SDO
        try: self.slaveObject.sdo_write(index, subindex, binary_data) # type: ignore
        except pysoem.SdoError as e: return False # type: ignore
        else: return True
    def writeSDOCMD(self, index, subindex, value)->bool:  # Read & Decode SDO from slave
        # data from dictionary for decoding
        counter=0
        data_type, bit_length = self._sdo_data_from_od(index, subindex)
        # data to binary
        print((value+'\r\n').encode('ascii'))
        try: self.slaveObject.sdo_write(index, subindex, (value+'\n'+'\0').encode('ascii'))
        except pysoem.SdoError as e: return False # type: ignore
        else: return True
    def readSDOCMD(self, index, subindex)->bool:  # Read & Decode SDO from slave
        # data from dictionary for decoding
        counter=0
        data_type, bit_length = self._sdo_data_from_od(index, subindex)
        # data to binary

        try: return self.slaveObject.sdo_read(index, subindex)
        except pysoem.SdoError as e: return False # type: ignore

    def ascii_to_hex(self,command):
        input_str = command
        hex_value = ""
        while input_str:
            chunk = input_str[:3]
            input_str = input_str[3:]
            length_byte = hex(3)[2:].zfill(2).upper()  # Fixed length byte to 3
            chunk = chunk[::-1]  # Reverse the order of ASCII characters
            chunk += "\0" * (3 - len(chunk))  # Pad with zeros if chunk length is less than 3
            hex_value += length_byte
            for char in chunk:
                hex_value += hex(ord(char))[2:].upper().zfill(2)
            hex_value += "\n"

        # Adding the final chunk "020D0A00"
        hex_value += "02" + "0D0A00"
        return hex_value
        # result_label.config(text=hex_value)
        # Clear previous contents
        # hex_text.delete(1.0, tk.END)
        # Display hexadecimal chunks
        # hex_text.insert(tk.END, hex_value)

    def test_SerialOverEcat(self,cmd_from_gui):
        #acsiiCommandsback=['l3kv','getall','en','dis','operationmode','record 1 1000 PWMMtuPeriod cciq ccid','rectrig','recget']
        command=cmd_from_gui# acsiiCommandsback[5]
        # res=self.ascii_to_hex(command)
        # res_clean=res.split('\n')
        self.writeSDO(0x20E0,2,1) #enables the Serial over Ecat
        self.writeSDOCMD(0x20E2,0,command)
        ans=self.readSDOCMD(0x20E2,0)
        print(ans)
        # self.writeSDO(0x20E2,0,1)
        # self.writeSDO(0x20E2,0,1)
        # commandlength=len(command)+2
        # for chunk in res_clean:
        #     data_int = int(chunk, 16)
        #     self.writeSDO(0x20e0, 1, data_int)
        #     #ph.write_sdo(0x20E0,1,hex(chunk))
        array=[]
        totalString=''
        ascii_string=''
        counter=0
        # while '0>>>>' not in totalString and counter<100:
        #     timecap=time.time()
        #     res=str(hex(self.readSDO(0x20E0,1)))[2:]

        #     #print(res)
        #     length = int(res[:1], 16)
        #     res=res[1:]

        #     # Splitting the string into sets of characters
        #     sets_of_chars = [res[i:i+2] for i in range(0, len(res), 2)]
        #     # ascii_chars = [chr(int(char, 16)) for char in sets_of_chars]
        #     ascii_string = ''.join([chr(int(char, 16)) for char in sets_of_chars])
        #     #print(ascii_string)
        #     totalString+=ascii_string

        #     counter+=1



        # print(f'Result: {totalString[commandlength:]}')
        # command=acsiiCommandsback[6]
        # res=self.ascii_to_hex(command)
        # res_clean=res.split('\n')
        # self.writeSDO(0x20E0,2,1)
        # commandlength=len(command)+2
        # for chunk in res_clean:
        #     data_int = int(chunk, 16)
        #     self.writeSDO(0x20e0, 1, data_int)
        #     #ph.write_sdo(0x20E0,1,hex(chunk))
        # array=[]
        # totalString=''
        # ascii_string=''
        # counter=0
        # while '0>>>>' not in totalString and counter<1000:
        #     timecap=time.time()
        #     res=str(hex(self.readSDO(0x20E0,1)))[2:]

        #     #print(res)
        #     length = int(res[:1], 16)
        #     res=res[1:]

        #     # Splitting the string into sets of characters
        #     sets_of_chars = [res[i:i+2] for i in range(0, len(res), 2)]
        #     # ascii_chars = [chr(int(char, 16)) for char in sets_of_chars]
        #     ascii_string = ''.join([chr(int(char, 16)) for char in sets_of_chars])
        #     #print(ascii_string)
        #     if(ascii_string=='IsRemoteEnInput'):
        #         counter+=1
        #     totalString+=ascii_string

        #     counter+=1



        # print(f'Result: {totalString[commandlength:]}')
        # command=acsiiCommandsback[7]
        # res=self.ascii_to_hex(command)
        # res_clean=res.split('\n')
        # self.writeSDO(0x20E0,2,1)
        # commandlength=len(command)+2
        # for chunk in res_clean:
        #     data_int = int(chunk, 16)
        #     self.writeSDO(0x20e0, 1, data_int)
        #     #ph.write_sdo(0x20E0,1,hex(chunk))
        # array=[]
        totalString=''
        # ascii_string=''
        # counter=0
        while '0>>>>' not in totalString: # and counter<512:
            timecap=time.time()
            try:
                # time.sleep(0.002)
                res=self.readSDO(0x20E1,0) #str(hex(self.readSDO(0x20E0,1)))[2:]
                print(res)
            except:
                continue
            # #print(res)
            # length = int(res[:1], 16)
            # res=res[1:]

            # # Splitting the string into sets of characters
            # sets_of_chars = [res[i:i+2] for i in range(0, len(res), 2)]
            # # ascii_chars = [chr(int(char, 16)) for char in sets_of_chars]
            # ascii_string = ''.join([chr(int(char, 16)) for char in sets_of_chars])
            # #print(ascii_string)
            # if(ascii_string=='IsRemoteEnInput'):
            #     counter+=1
            # ascii_string_clean = ascii_string.replace("\x00", "")
            totalString+=res
            
            # if('>>>' in totalString):
            #     break
            # counter+=1



        # print(f'Result: {totalString[commandlength:]}')
        return totalString
       








    #---------------------------------------------
DEBUG = True
if __name__ == "__main__":
    # Connection
    master = Master()
    while not master.connection_status:
        master = Master()
    print("Connected: ", master.connection_status)
    master.setUpSlaves()

    if DEBUG:
        print("You will put a breakpoint here")

        master.mySlaves[0].readSDO(0x6041, 0)

        master.mySlaves[0].test_SerialOverEcat()
        master.mySlaves[0].writeSDO(0x6040, 0, 1)
        master.mySlaves[0].readSDO(0x6040, 0)
        print("You're done with debugging")
    
    # end of program
    master.close()
