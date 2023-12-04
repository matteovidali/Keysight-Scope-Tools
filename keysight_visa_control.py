import pyvisa
from dataclasses import dataclass
from typing import Union
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
        return result.strip()
    
    def command(self, command: str) -> None: 
        """Writes a command string to the oscilloscope"""
        if self.loud:
            print(f"Writing Command '{command}'...")
        self.scope.write(command)
        self._check_instrument_errors(command)

    def close(self):
        """Closes the vxi11 connection"""
        self.scope.close()

class Setting:
    def __init__(self, scope: Scope, cmd_name: str, queries: dict, alwd_cmds: dict, loud):
        self.__scope = scope
        self.__cmd_name = cmd_name
        self.__cmd_short = ''.join([x for x in cmd_name if x.isupper()])
        self.__queries = queries
        self.__alwd_cmds = alwd_cmds
        self._loud = loud
        self.state_in_date = False
        self.state = self.refresh_state()

        if self.loud:
            print(f"Setup command {self.__cmd_name} with short name:{self.__cmd_short}")

    @property
    def __queries_lowers(self) -> dict[str]:
        """Lower Cases the search keys in queries"""
        return {k.lower():v for k,v in self.__queries.items()}

    @property
    def loud(self):
        """The loud property."""
        return self._loud
    @loud.setter
    def loud(self, loud):
        self._loud = loud

    def refresh_state(self) -> dict[str, str]:
        """Gets the setup of the trigger by querying every setting."""
        if self.state_in_date:
            if self.loud:
                print("State settings already in date, no refresh needed")
            return self.state
        settings = {}
        for s, q in self.__queries.items():
            settings[s] = self.__scope.query(f":{self.__cmd_name}:{q}").strip()
            if self.loud:
                print(f"{self.__cmd_short}: Got-> {s} = {settings[s]}")
        self.state = settings
        self.state_in_date = True
        return settings

    def _set(self, s: str, val: Union[str, int, float], refresh=False) -> None:
        s = s.lower() # Setting desired (key)

        if s not in self.__alwd_cmds.keys():
            raise ValueError(f"'{s}' is not a valid editable settings for {self.__cmd_short}.\n \
                    Settings allowed include:\n {self.__alwd_cmds.keys()}")

        if (len(self.__alwd_cmds[s]) > 1) and (val not in self.__alwd_cmds[s]):
            raise ValueError(f"'{val}' is not an allowable input type for this setting.\n \
                    allowed parameters are:\n {self.__alwd_cmds[s]}")

        self.__scope.command(f":{self.__cmd_name}:{self.__queries_lowers[s]} {val}")
        self.state_in_date = False

        if refresh:
            self.refresh_state()

class Trigger(Setting):
    """A Setting Subclass that houses the Trigger setting type"""
    def __init__(self, scope: Scope, loud: bool) -> None:
        _cmd_name = "TRIGger"
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
                             "force": [],
                             "edge:source":  ["channel1", "channel2", "channel3", "channel4", 
                                         "external", "line", "wgen", "wgen1", "wgen2", "wmod"],
                             "edge:level":   [],
                             "edge:coupling":["dc", "ac", "lfreject"],
                             "edge:slope":   ["positive", "negative", "either", "alternate"],
                             "edge:reject":  ["off", "lfreject", "hfreject"]}

        super().__init__(scope, _cmd_name, __trigger_queries, __trig_cmds_allwd, loud)

    @property
    def loud(self):
        """The loud property."""
        return super().loud
    @loud.setter
    def loud(self, loud):
        super().loud = loud

    def set_source(self, chan: str):
        """Sets the trigger source channel: allowed options are:
            1. "channel1", "channel2", "channel3", "channel4", 
            2. "external", "line", "wmod"
            3. "wgen", "wgen1", "wgen2", 
            """
        which = self.state["Mode"]
        super()._set(f"{which}:source", chan)

    def set_level(self, level: float):
        """Sets the level of the edge trigger"""
        which = self.state["Mode"]
        super()._set(f"{which}:level", level)

    # TODO: fill in for other modes
    def set_mode(self, mode: str):
        if mode.lower() != "edge":
            raise ValueError("Only 'EDGE' type triggering currently supported")

        super()._set("mode", mode)

    def set_slope(self, slope: str):
        which = self.state["Mode"]
        super()._set(f"{which}:slope", slope)

    def force(self):
        super()._set(f"force", '')

#TODO: Add more settings that can be changed here
class Channel(Setting):
    def __init__(self, scope:Scope, channel_id: int, loud: bool) -> None:
        channel_id = channel_id
        _cmd_name = f"CHANnel{channel_id}"
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
                            #"Probe:Mode": "PROBe:MODE",
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

        super().__init__(scope, _cmd_name, __channel_queries, __chan_cmds_allwd, loud)

    @property
    def loud(self):
        """The loud property."""
        return super().loud

    @loud.setter
    def loud(self, loud):
        super().loud = loud

    def set_scale(self, scale: float):
        """Set channel vertical Volts per Division [V]"""
        super()._set("scale", scale)

    def set_offset(self, offset: float):
        """Set channel vertical offset 0 for centered"""
        super()._set("offset", offset)

class Timescale(Setting):
    def __init__(self, scope: Scope, loud: bool) -> None:
        _cmd_name = "TIMebase"
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
                           "position": [],
                           "reference": ["left", "right", "center", "custom"],
                           "reference:location": []}

        super().__init__(scope, _cmd_name, __tb_queries, __tb_cmds_allwd, loud)

    @property
    def loud(self):
        """The loud property."""
        return super().loud

    @loud.setter
    def loud(self, loud):
        super().loud = loud

    def set_reference(self, reference: str, loc: float):
        """Set the timescale reference point on screen:
           can be - left, right, center, or custom.
           if 'custom', please specify a loc (argument) as a float
           specifying the location on the screen from 0.0 to 1.0"""
        if reference.lower() == "custom":
            self_set(("reference:location", loc))

        else:
            self._set("reference", reference)

    def set_scale(self, scale: float):
        """Set the horizontal time per division in seconds"""
        self._set("scale", scale)

class Waveform(Setting):
    def __init__(self, scope: Scope, loud: bool, default: bool=True):
        _cmd_name = "WAVeform"
        __wf_queries = {"Byteorder": "BYTeorder",
                        "Count": "COUNt",
                        "Format": "FORMat",
                        "Points": "POINts",
                        "Points:Mode": "POINts:MODE",
                        "Preamble" : "PREamble",
                        #"Segmented All":"SEGmented:ALL",
                        #"Segmented Count":"SEGmented:COUNt",
                        #"Segmented TTAG":"SEGmented:TTAG",
                        #"Segmented X List": "SEGmented:XLISt",
                        "Source": "SOURce",
                        "Subsource": "SOURce:SUBSource",
                        "Type": "TYPE",
                        "Unsigned": "UNSigned",
                        "View": "VIEW",
                        "XIncrement": "XINCrement",
                        "XOrigin": "XORigin",
                        "XReference": "XREFerence",
                        "YIncrement": "YINCrement",
                        "YOrigin": "YORigin",
                        "YReference": "YREFerence",}

        __wf_cmds_allwd = {"points:mode": ["normal", "max", "raw"],
                           "points": [],
                           "source": [*[f"channel{i}" for i in range(1,5)],
                                      *[f"function{i}" for i in range(1, 5)],
                                      *[f"math{i}" for i in range(1,5)],
                                      *[f"WMEMory{i}" for i in range(1,5)]],
                           "format": ["word", "byte", "ascii"]}

        super().__init__(scope, _cmd_name, __wf_queries, __wf_cmds_allwd, loud)

        if default:
            self.default_setup()
       
    @property
    def loud(self):
        """The loud property."""
        return super().loud
    @loud.setter
    def loud(self, loud):
        super().loud = loud

    def default_setup(self):
        self.set_pointsmode("raw")
        self.set_points("10240")
        self.set_source("channel1")
        self.set_format("byte")

    def set_pointsmode(self, mode: str):
        super()._set("points:mode", mode)

    def set_points(self, n_points: float):
        super()._set("points", n_points)

    def set_source(self, source: str):
        super()._set("source", source)

    def set_format(self, format: str):
        super()._set("format", format)

    def get_data():
        pass
 
class KeysightControl:
    def __init__(self, resource_id: str=None, loud: bool=False) -> None: 
        self.loud = loud
        self.scope = Scope(resource_id, loud)
        self.trigger = Trigger(self.scope, loud) 
        self.channel_ids = ["channel1", "channel2", "channel3", "channel4"]
        self.channel1 = Channel(self.scope, 1, loud)
        self.channel2 = Channel(self.scope, 2, loud)
        self.channel3 = Channel(self.scope, 3, loud)
        self.channel4 = Channel(self.scope, 4, loud)
        self.timebase = Timescale(self.scope, loud) 
        self.channels = [self.channel1, self.channel2, self.channel3, self.channel4]
        self.waveform = Waveform(self.scope, loud)

    def force_trigger(self) -> None:
        if self.loud:
            print("Forced Trigger")
        self.trigger.force()
    
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

    def set_trig_single(self):
        self.scope.command(":SINGle")

    def capture_waveform(self, source: str="channel1", mode: str=None) -> list:
        max_data = 10_000_000
        self.scope.command(f":WAVeform:SOURce {source}")
        self.scope.command(":WAVEform:POINTs 10240")
        data = self.scope.scope.query_binary_values(f":WAVeform:DATA?", datatype='s') 
        self.scope._check_instrument_errors(f":WAVeform:DATA?")
        return [float(d) for d in data]

    def set_loud(self, loud: bool):
        """Setter for 'loud' which will print verbose info about each command"""
        self.loud = loud
        self.trigger.loud = loud
        for channel in self.channels.values():
            channel.loud = loud

    def close(self):
        self.scope.close()


if __name__ == "__main__":
    control = KeysightControl("TCPIP::192.168.0.17::INSTR", loud=True)
    control.scope.query("*IDN")
    print(control.trigger.state)
    # TODO: Maybe make objects for each thing that can have settings?
    #control.trigger.set("mode", "EDGE")
    #control.channel1.set("Scale", "3.00")
    #control.timebase.set("Scale", "0.0002")
    #control.timebase.set("position", "0.0")
    #control.scope.query(":TRIG:EDGE:level")
    #control.scope.query(":ACQuire:TYPE")
    data = control.capture_waveform()
    with open("out.txt", "w+") as f:
        for n in data:
            f.write(f"{n},")
    print(data)
    control.close()
