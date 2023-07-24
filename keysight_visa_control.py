import pyvisa

class KeysightScope:
    def __init__(self, resource_id: str=None, loud: bool=False) -> None:
        self.loud = loud

        if not resource_id:
            self.scope = self.get_resource()
        else:
            try:
                self.scope = pyvisa.ResourceManager().open_resource(resource_id)
            except OSError:
                print("Resource Identifier '{resource_id}' is invalid...")
                self.scope = self.get_resource()
        
        self.trig_settings = self.get_trigger_setup()
        self.channels = ["channel1", "channel2", "channel3", "channel4"]
        self.chan_settings = {}
        for c in self.channels:
            self.chan_settings[c] = self.get_channel_setup(c)
        self.timebase_settings = self.get_timebase_setup()

    def get_resource(self) -> pyvisa.Resource:
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
            return self.get_resource()

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

    def _query(self, q: str) -> str:
        """Sends a query string to the oscilloscope"""
        result = self.scope.query(q+"?")
        self._check_instrument_errors(q+"?")
        if self.loud:
            print(result, end='')
        return result

    def _command(self, command: str) -> None: 
        """Writes a command string to the oscilloscope"""
        if self.loud:
            print(f"Writing Command '{command}'...")
        self.scope.write(command)
        self._check_instrument_errors(command)

    def force_trigger(self) -> None:
        if self.loud:
            print("Forced Trigger")
        self._command(":TRIGger:FORCe")
    
    def autoscale(self) -> None:
        if self.loud:
            print("Autoscale ...")
        self._command(":AUToscale")

    def setup_trigger_edge(self, source: str=None, level: str=None,
                                 coupling: str=None, slope: str=None, reject: str=None) -> None:

        if not self.trig_settings["Mode"] == "EDGE":
            self._command(":TRIGger:MODE EDGE")

        if source and source.lower() != self.trig_settings["Edge:Source"].lower():
            allowed = ["channel1", "channel2", "channel3", "channel4", 
                       "external", "line", "wgen", "wgen1", "wgen2", "wmod"]
            if source not in allowed:
                print(f"'{source}' is not an invalid type. Must select from: {a for a in allowed}")
            self._command(f":TRIG:EDGE:SOURCE {source}")

        source = self.trig_settings["Edge:Source"] if not source else source 

        if level and level.lower() != self.trig_settings["Edge:Level"].lower():
            self._command(f":TRIG:EDGE:LEVel {level}")

        if coupling and coupling.lower() != self.trig_settings["Edge:Coupling"].lower():
            allowed = ["dc", "ac", "lfreject"]
            if not coupling.lower() in allowed: 
                print(f"'{coupling}' is an invalid coupling type - select (AC, DC, or LFReject)")
            else:
                self._command(f":TRIG:EDGE:COUPling {coupling}")
        
        if slope and slope.lower() != self.trig_settings["Edge:Slope"].lower():
            allowed = ["positive", "negative", "either", "alternate"]
            if slope.lower() not in allowed:
                print(f"'{slope}' is not a valid type. Must be: {a for a in allowed}")
            else:
                self._command(f":TRIG:EDGE:SLOPE {slope}")

        if reject and reject.lower() != self.trig_settings["Edge:Reject"].lower():
            allowed = ["off", "lfreject", "hfreject"]
            if reject.lower() not in allowed:
                print(f"'{reject}' is not a valid type. Must be: {a for a in allowed}")
            else:
                self._command(f":TRIG:EDGE:REJect {reject}")

        self.trig_settings = self.get_trigger_setup()

    # TODO: Make not of every setting changed and give a summary.
    def setup_channel(self, channel: str, scale: str=None, offset: str=None) -> None:

        channel = channel.lower()

        if channel not in self.channels:
            raise ValueError(f"'{channel}' is not an allowed channel. Must be: {c for c in self.channels}")

        def_settings = self.chan_settings[channel]
       
        #TODO: scale can come in format <scale>[suffix] where scale is a number and suffix is mV or V
        #      Want to check for this and only this
        if scale and scale.lower() != def_settings["Scale"].lower():
            self._command(f":{channel}:SCALe {scale}")

        #TODO: Same as scale - suffixes can occur
        if offset and offset.lower() != def_settings["Offset"].lower():
            self._command(f":{channel}:OFFSet {offset}")

        self.chan_settings[channel] = self.get_channel_setup(channel)

    # TODO: Flesh this out some more
    def setup_timebase(self, scale: str=None, position: str=None) -> None:

        if scale and scale.lower() != self.timebase_settings["Scale"].lower():
            self._command(f":TIMebase:SCALe {scale}")

        if position and position.lower() != self.timebase_settings["Position"].lower():
            self._command(f":TIMebase:POSition {position}")
    
        self.timebase_settings = self.get_timebase_setup()

    #TODO: Flesh out with every trigger setting - potentially make settings object
    def get_trigger_setup(self) -> dict[str, str]:
        """Gets the setup of the trigger by querying every setting."""
        trig_settings = {}
        trigger_queries = {"HF_Reject": "HFReject",
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

        for t_set, q in trigger_queries.items():
            trig_settings[t_set] = self._query(f":TRIGger:{q}").strip()
            if self.loud:
                print(f"TRIG: Got-> {t_set} = {trig_settings[t_set]}")
        return trig_settings

    def get_channel_setup(self, channel: str="channel1") -> dict[str, str]:
        if not channel in self.channels:
            print("Invalid channel selection: '{channel}'. Must be: {c for c in allowed}")
            return

        chan_settings = {} 
        chan_queries = {"Bandwidth Limit": "BWLimit",
                        "Coupling": "COUPling",
                        "Display": "DISPlay",
                        "Impedance": "Impedance",
                        "Invert": "INVert",
                        "Label": "LABel",
                        "Offset": "OFFSet",
                        "Probe": "PROBe",
                        #"Probe:Button": "PROBe:BTN",
                        #"Probe:External": "PROBe:EXTernal",
                        #"Probe:External:Gain": "PROBe:EXTernal:GAIN",
                        #"Probe:External:Units": "PROBe:EXTernal:UNITs",
                        #"Probe:ID": "PROBe:ID",
                        #"Probe:Model": "PROBE:MMODel",
                        #"Probe:Mode": "PROBe:MODE",
                        #"Probe:R-Sense": "PROBE:RSENse",
                        #"Probe:Skew": "PROBe:SKEW",
                        #"Probe:SigType": "PROBe:STYPe",
                        #"Probe:Zoom": "PROBe:ZOOM",
                        "Protection": "PROTection",
                        "Range": "RANGe",
                        "Scale": "SCALe",
                        "Units": "UNITs",
                        "Vernier": "VERNier"}

        for c_set, q in chan_queries.items():

            chan_settings[c_set] = self._query(f":{channel}:{q}").strip()
            if self.loud:
                print(f"{channel}: Got-> {c_set} = {chan_settings[c_set]}")
        return chan_settings

    def get_timebase_setup(self) -> dict[str, str]:
        timebase_settings = {}
        timebase_queries = {"Mode": "MODE",
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

        for t_set, q in timebase_queries.items():
            timebase_settings[t_set] = self._query(f":TIMebase:{q}").strip()
            if self.loud:
                print(f"TIMEBASE: Got-> {t_set} = {timebase_settings[t_set]}")

        return timebase_settings

    def setup_capture(self, source) -> dict[str, str]:
        if not source in self.channels:
            raise ValueError(f"'{source}' is not an acceptable channel to source data from.\n",
                               "Must be: {c for c in self.channels}")
        self._command(":WAVeform:POINts:MODE RAW")
        self._command(":WAVEform:POINTs 10240")
        self._command(f":WAVeform:SOURce {source}")
        self._command(f":WAVeform:FORMat BYTE")

    def capture_waveform(self, source: str="channel1", mode: str=None) -> list:
        max_data = 10_000_000
        self.setup_capture(source) 
        data = self.scope.query_binary_values(f":WAVeform:DATA?", datatype='s') 
        self._check_instrument_errors(f":WAVeform:DATA?")
        return data

    def set_loud(self, loud: bool):
        """Setter for 'loud' which will print verbose info about each command"""
        self.loud = loud

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
    scope = KeysightScope("TCPIP::192.168.0.17::INSTR", loud=True)
    scope._query("*IDN")
    print(scope.trig_settings)
    # TODO: Maybe make objects for each thing that can have settings?
    scope.setup_channel(channel="channel1", scale="3.00")
    scope.setup_timebase(scale="0.0002", position="0.0")
    scope._query(":TRIG:EDGE:level")
    scope._query(":ACQuire:TYPE")
    data = scope.capture_waveform()
    print(data)
    scope.close()
