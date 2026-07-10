class USB6001:
    def __init__(self,device_address):
        global nidaqmx
        import nidaqmx
        global AcquisitionType, Edge, TerminalConfiguration
        from nidaqmx.constants import AcquisitionType, Edge, TerminalConfiguration
        self.device_address = device_address
        device = nidaqmx.system.device.Device(self.device_address)
        device.reset_device()
        for tr in device.terminals:
            print(tr)
    
    def analog_output(self, PIN, voltage):
        with nidaqmx.Task() as task:
            task.ao_channels.add_ao_voltage_chan(self.device_address+"/"+PIN)
            try:
                task.write(voltage, auto_start=True)
            except nidaqmx.DaqError as e:
                print(e)
        
    def analog_input(self, PIN, TRIG_PIN, SAMPLE):
        with nidaqmx.Task() as task:
            task.ai_channels.add_ai_voltage_chan(self.device_address+"/"+PIN, terminal_config=TerminalConfiguration.RSE)
            task.timing.cfg_samp_clk_timing(10000, active_edge=Edge.RISING, sample_mode=AcquisitionType.CONTINUOUS)
            #task.triggers.start_trigger.cfg_dig_edge_start_trig("/"+self.device_address+"/"+TRIG_PIN, Edge.RISING)
            task.in_stream.timeout = 200
            data = task.read(SAMPLE, 120) # sample, timeout [s];
            
        return data

    def digital_output(self, port, PIN, OUTPUT):
        with nidaqmx.Task() as task:
            task.do_channels.add_do_chan(self.device_address+"/port"+str(port)+"/line"+str(PIN))
            try:
                task.write([OUTPUT])
            except nidaqmx.DaqError as e:
                print(e)

import serial
class BM9:
    def __init__(self, port) -> None:
        self.port = port
        self.ser = serial.Serial(port,baudrate=2400,timeout=None,parity=serial.PARITY_ODD,bytesize = serial.SEVENBITS,stopbits = serial.STOPBITS_ONE)
        print("TOPCON BM9 is ready.\n")
    

    def read(self):   
        data = self.ser.read_until(b"\r")
        data = data.decode("ascii").replace("\r", "")
        return data

    def write(self, msg):
        self.ser.write(f"{msg}\r".encode("ascii"))

    def get_luminance(self):
        self.write("DBR0ST")
        line = self.read().split()
        data = float(line[0])
        return data
    
    def close(self):
        self.ser.close()
    