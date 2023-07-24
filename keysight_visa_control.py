import pyvisa
from dataclasses import dataclass

#TODO: Implement the get waveform query here instead of in controller
#      at the very least fully encapsulate so nowhere is calling Scope.scope.<method> instead
#      of just Scope.<method>
class Scope:
    """ A basic wrapper that houses the keysight scope and necessary 
        methods like query and command."""
    def __init__(self, resource_id: str=None, loud: bool=False):
        if not resource_id:
            self.scope = self._get_resource()
        else:
            try:
                self.scope = pyvisa.ResourceManager().open_resource(resource_id)
            except OSError:
                print("Resource Identifier '{resource_id}' is invalid...")
                self.scope = self._get_resource()

        self.loud = loud

    def _get_resource(self) -> pyvisa.Resource:
        """Gets a scope from the visa manager via command line options"""
        # Instantiate the Resource Manager and get the resources
        rm = pyvisa.ResourceManager()
        resources = rm.list_resources()

        # If there is only one resource, just get that
        if len(resources) <= 1:
            return rm.open_resource(resources[0])
    
        # Let user choose one of the resources
        print("Select a resource from the following list:")
        for idx, resource in enumerate(resources):
            print(f"{idx+1}: {resource}")
        
        res = input("\nType the number of the resource desired: ")
        
        # Fancy error checking - recursive (potential danger)
        try:
            return rm.open_resource(resources[int(res)])
        except ValueError:
            print(f"'{res}' is not a selectable resource.")
            print("Restarting...")
            return self._get_resource()

    def _check_instrument_errors(self, command: str) -> None:
        """Checks for an error in a query or command by hitting the system error query"""
        while True:
            error_string = self.scope.query(":SYSTem:ERRor?")
            if error_string: # If there is an error string value.
                if error_string.find("+0,", 0, 3) == -1: # Not "No error".
                    print("ERROR: %s, command: '%s'" % (error_string, command))
                    raise Exception("Exited because of error.")
                else: # "No error"
                    break
            else: # :SYSTem:ERRor? should always return string.
                print("ERROR: :SYSTem:ERRor? returned nothing, command: '%s'" % command)
                print("Exited because of error.")
                raise ValueError("MAJOR SYSTEM ERROR")

    def query(self, q: str) -> str:
        """Sends a query string to the oscilloscope"""
        result = self.scope.query(q+"?")
        self._check_instrument_errors(q+"?")
        if self.loud:
            print(result, end='')
        return result
    
    def command(self, command: str) -> None: 
        """Writes a command string to the oscilloscope"""
        if self.loud:
            print(f"Writing Command '{command}'...")
        self.scope.write(command)
        self._check_instrument_errors(command)

    def close(self):
        """Closes the vxi11 connection"""
        self.scope.close()

@dataclass
class Trigger:
    """A dataclass that houses the Trigger command type"""
    __scope: Scope
    _loud: bool
    __trigger_queries = {"HF_Reject": "HFReject",
                       "Hold-off": "HOLDoff",
                       "Hold-off Maximum": "HOLDoff:MAXimum",
                       "Hold-off Minimum": "HOLDoff:MINimum",
                       "Hold-off Random": "HOLDoff:RANDom",
                       "Mode": "MODE",
                       "Noise reject": "NREJect",
                       "Sweep": "SWEep",
                       "Edge:Coupling": "EDGE:COUPling",
                       "Edge:Reject": "EDGE:REJect",
                       "Edge:Level": "EDGE:LEVel",
                       "Edge:Slope": "EDGE:SLOPe",
                       "Edge:Source": "EDGE:SOURce"}

    __trig_cmds_allwd = {"mode":    ["EDGE", "GLITch", "PATTern", "TV", "EBURst",
                                     "OR", "RUNT", "SHOLd", "TRANsition", "SBUS"],
                         "source":  ["channel1", "channel2", "channel3", "channel4", 
                                     "external", "line", "wgen", "wgen1", "wgen2", "wmod"],
                         "level":   [],
                         "coupling":["dc", "ac", "lfreject"],
                         "slope":   ["positive", "negative", "either", "alternate"],
                         "reject":  ["off", "lfreject", "hfreject"]}

    @property
    def __trigger_lowers(self) -> dict[str]:
        return {k.lower():v for k,v in self.__trigger_queries.items()}

    @property
    def loud(self):
        """The loud property."""
        return self._loud
    @loud.setter
    def loud(self, loud):
        self._loud = loud

    @property
    def state(self) -> dict[str, str]:
        """Gets the setup of the trigger by querying every setting."""
        trig_settings = {}

        for t_set, q in self.__trigger_queries.items():
            trig_settings[t_set] = self.__scope.query(f":TRIGger:{q}").strip()
            if self.loud:
                print(f"TRIG: Got-> {t_set} = {trig_settings[t_set]}")
        return trig_settings

    def get_setting(self, setting):
        if setting not in self.__trigger_queries.keys():
            if self.loud:
                print(f"No trigger setting for '{setting}'.")
                print(f"Allowed settings:\n {x for x in self.__trigger_queries}")
            raise ValueError
        return self.state[setting]

    def set(self, s, val):
        s = s.lower() # Setting desired (key)

        if s not in self.__trig_cmds_allwd.keys():
            raise ValueError(f"'{s}' is not a valid editable settings.\n \
                    Settings allowed include:\n {self.__trig_cmds_allwd.keys()}")

        if (len(self.__trig_cmds_allwd[s]) > 1) and (val not in self.__trig_cmds_allwd[s]):
            raise ValueError(f"'{val}' is not an allowable input type for this setting.\n \
                    allowed parameters are:\n {self.__trig_cmds_allwd[s]}")

        self.__scope.command(f":TRIGger:{self.__trigger_lowers[s]} {val}")

#TODO: Add more settings that can be changed here
@dataclass
class Channel:
    __scope: Scope
    channel_id: str
    _loud: bool = False
    __channel_queries ={"Bandwidth Limit": "BWLimit",
                        "Coupling": "COUPling",
                        "Display": "DISPlay",
                        "Impedance": "Impedance",
                        "Invert": "INVert",
                        "Label": "LABel",
                        "Offset": "OFFSet",
                        "Probe": "PROBe",
                        "Probe:Button": "PROBe:BTN",
                        "Probe:External": "PROBe:EXTernal",
                        "Probe:External:Gain": "PROBe:EXTernal:GAIN",
                        "Probe:External:Units": "PROBe:EXTernal:UNITs",
                        "Probe:ID": "PROBe:ID",
                        "Probe:Model": "PROBE:MMODel",
                        "Probe:Mode": "PROBe:MODE",
                        "Probe:R-Sense": "PROBE:RSENse",
                        "Probe:Skew": "PROBe:SKEW",
                        "Probe:SigType": "PROBe:STYPe",
                        "Probe:Zoom": "PROBe:ZOOM",
                        "Protection": "PROTection",
                        "Range": "RANGe",
                        "Scale": "SCALe",
                        "Units": "UNITs",
                        "Vernier": "VERNier"}

    __chan_cmds_allwd = {"scale": [],
                         "offset": [],
                         "coupling": ["AC", "DC"]}

    @property
    def __channel_lowers(self) -> dict[str]:
        return {k.lower():v for k,v in self.__channel_queries.items()}

    @property
    def loud(self):
        """The loud property."""
        return self._loud

    @loud.setter
    def loud(self, loud):
        self._loud = loud

    @property
    def state(self) -> dict[str, str]:
        """Gets the setup of the trigger by querying every setting."""
        chan_settings = {}

        for c_set, q in self.__channel_queries.items():
            chan_settings[c_set] = self.__scope.query(f":{self.channel_id}:{q}").strip()
            if self.loud:
                print(f"{self.channel_id}: Got-> {c_set} = {chan_settings[c_set]}")
        return chan_settings

    def get_setting(self, setting):
        if setting not in self.__chan_queries.keys():
            if self.loud:
                print(f"No channel setting for '{setting}'.")
                print(f"Allowed settings:\n {x for x in self.__trigger_queries}")
            raise ValueError
        return self.state[setting]
    
    def set(self, s, val):
        s = s.lower() # Setting desired (key)

        if s not in self.__chan_cmds_allwd.keys():
            raise ValueError(f"'{s}' is not a valid editable settings.\n \
                    Settings allowed include:\n {self.__chan_cmds_allwd.keys()}")

        if (len(self.__chan_cmds_allwd[s]) > 1) and (val not in self.__chan_cmds_allwd[s]):
            raise ValueError(f"'{val}' is not an allowable input type for this setting.\n \
                    allowed parameters are:\n {self.__chan_cmds_allwd[s]}")

        self.__scope.command(f":{self.channel_id}:{self.__channel_lowers[s]} {val}")

@dataclass
class Timebase:
    __scope: Scope
    _loud: bool = False
    __tb_queries = {"Mode": "MODE",
                    "Position": "POSition",
                    "Range": "RANGe",
                    "Ref Clock": "REFClock",
                    "Reference": "REFerence",
                    "Reference:Location": "REFerence:LOCation",
                    "Scale": "SCALe",
                    "Vernier": "VERNier",
                    "Window:Position": "WINDow:POSition",
                    "Window:Range": "WINDow:RANGe",
                    "Window:Scale": "WINDow:SCALe"}

    __tb_cmds_allwd = {"scale": [],
                       "position": []}

    @property
    def __tb_lowers(self) -> dict[str]:
        return {k.lower():v for k,v in self.__tb_queries.items()}

    @property
    def loud(self):
        """The loud property."""
        return self._loud

    @loud.setter
    def loud(self, loud):
        self._loud = loud

    @property
    def state(self) -> dict[str, str]:
        """Gets the setup of the trigger by querying every setting."""
        tb_settings = {}

        for tb_set, q in self.__tb_queries.items():
            tb_settings[tb_set] = self.__scope.query(f":TIMebase:{q}").strip()
            if self.loud:
                print(f"TIMEBASE: Got-> {t_set} = {timebase_settings[t_set]}")
        return tb_settings

    def get_setting(self, setting):
        if setting not in self.__tb_queries.keys():
            if self.loud:
                print(f"No timebase setting for '{setting}'.")
                print(f"Allowed settings:\n {self.__trigger_queries.keys()}")
            raise ValueError
        return self.state[setting]
    
    def set(self, s, val):
        s = s.lower() # Setting desired (key)

        if s not in self.__tb_cmds_allwd.keys():
            raise ValueError(f"'{s}' is not a valid editable settings.\n \
                    Settings allowed include:\n {self.__tb_cmds_allwd.keys()}")

        if (len(self.__tb_cmds_allwd[s]) > 1) and (val not in self.__tb_cmds_allwd[s]):
            raise ValueError(f"'{val}' is not an allowable input type for this setting.\n \
                    allowed parameters are:\n {self.__tb_cmds_allwd[s]}")

        self.__scope.command(f":TIMebase:{self.__tb_lowers[s]} {val}")


class KeysightControl:
    def __init__(self, resource_id: str=None, loud: bool=False) -> None: 
        self.loud = loud
        self.scope = Scope(resource_id, loud)
        self.trigger = Trigger(self.scope, loud) 
        self.channel_ids = ["channel1", "channel2", "channel3", "channel4"]
        self.channel1 = Channel(self.scope, "channel1", loud)
        self.channel2 = Channel(self.scope, "channel2", loud)
        self.channel3 = Channel(self.scope, "channel3", loud)
        self.channel4 = Channel(self.scope, "channel4", loud)
        self.timebase = Timebase(self.scope, loud) 
        self.channels = [self.channel1, self.channel2, self.channel3, self.channel4]

    def force_trigger(self) -> None:
        if self.loud:
            print("Forced Trigger")
        self.scope.command(":TRIGger:FORCe")
    
    def autoscale(self) -> None:
        if self.loud:
            print("Autoscale ...")
        self.scope.command(":AUToscale")

    def setup_capture(self, source) -> dict[str, str]:
        if not source in self.channel_ids:
            raise ValueError(f"'{source}' is not an acceptable channel to source data from.\n",
                               "Must be: {c for c in self.channels}")
        self.scope.command(":WAVeform:POINts:MODE RAW")
        self.scope.command(":WAVEform:POINTs 10240")
        self.scope.command(f":WAVeform:SOURce {source}")
        self.scope.command(f":WAVeform:FORMat BYTE")

    def capture_waveform(self, source: str="channel1", mode: str=None) -> list:
        max_data = 10_000_000
        self.setup_capture(source) 
        data = self.scope.scope.query_binary_values(f":WAVeform:DATA?", datatype='s') 
        self.scope._check_instrument_errors(f":WAVeform:DATA?")
        return data

    def set_loud(self, loud: bool):
        """Setter for 'loud' which will print verbose info about each command"""
        self.loud = loud
        self.trigger.loud = loud
        for channel in self.channels.values():
            channel.loud = loud

    def close(self):
        self.scope.close()


class Waveform:
    @staticmethod
    def set_byteorder(value):
        return f":WAVeform:BYTeorder {value}" 

    @staticmethod
    def query_byteorder():
        return ":WAVeform:BYTeorder?"

if __name__ == "__main__":
    control = KeysightControl("TCPIP::192.168.0.17::INSTR", loud=True)
    control.scope.query("*IDN")
    print(control.trigger.state)
    # TODO: Maybe make objects for each thing that can have settings?
    control.trigger.set("mode", "EDGE")
    control.channel1.set("Scale", "3.00")
    control.timebase.set("Scale", "0.0002")
    control.timebase.set("position", "0.0")
    control.scope.query(":TRIG:EDGE:level")
    control.scope.query(":ACQuire:TYPE")
    data = control.capture_waveform()
    print(data)
    control.close()
