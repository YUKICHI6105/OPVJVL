import serial
import time

class Keithley2400:
    def __init__(self, port):
        self.port = port
        self.ser = serial.Serial(port=self.port, baudrate=9600, bytesize=serial.EIGHTBITS, parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE, timeout=1.0)
        self.ser.reset_input_buffer()
        self.ser.reset_output_buffer()

        try:
            idn = self.query("*IDN?")
            print(f"Connected to: {idn}")
        except Exception as e:
            print(f"Warning: Could not read *IDN? from {port}: {e}")

    # ========= 基本I/O =========
    def write(self, msg: str) -> None:
        self.ser.write((msg + "\n").encode("ascii"))

    def read(self) -> str:
        data = self.ser.readline().decode("ascii").strip()
        return data

    def query(self, msg: str) -> str:
        self.ser.reset_input_buffer()
        self.write(msg)
        return self.read()

    # ========= 基本操作 =========
    def reset(self):
        self.write("*RST")
        time.sleep(1.0)

    def clear_status(self):
        self.write("*CLS")

    def close(self):
        if self.ser.is_open:
            self.ser.close()
            print("Keithley2400 port closed.")

    # ========= ソース設定 =========
    def configure_source_voltage(self, compliance_current=0.02, nplc=1.0, auto_range=True, current_range=1e-3):
        self.write("SOUR:FUNC VOLT")
        self.write("SENS:FUNC 'CURR'")
        self.write(f"SENS:CURR:PROT {compliance_current}")
        self.write(f"SENS:CURR:NPLC {nplc}")
        if auto_range:
            self.write("SENS:CURR:RANG:AUTO ON")
        else:
            self.write("SENS:CURR:RANG:AUTO OFF")
            self.write(f"SENS:CURR:RANG {current_range}")
        self.output_off()

    def configure_source_current(self, nplc=1.0, auto_range=True, voltage_range=20):
        self.write("SOUR:FUNC CURR")
        self.write("SENS:FUNC 'VOLT'")
        self.write(f"SENS:VOLT:NPLC {nplc}")
        if auto_range:
            self.write("SENS:VOLT:RANG:AUTO ON")
        else:
            self.write("SENS:VOLT:RANG:AUTO OFF")
            self.write(f"SENS:VOLT:RANG {voltage_range}")
        self.output_off()

    # ========= 出力制御 =========
    def output_on(self):
        self.write("OUTP ON")

    def output_off(self):
        self.write("OUTP OFF")

    # ========= ソースレベル設定 =========
    def set_voltage(self, voltage: float):
        self.write(f"SOUR:VOLT {voltage}")

    def set_current(self, current: float):
        self.write(f"SOUR:CURR {current}")

    # ========= 測定 =========
    def measure_current(self) -> float:
        resp = self.query("MEAS:CURR?")
        try:
            second = resp.split(",")[1]
            return float(second)
        except Exception:
            print(f"Warning: could not parse current from '{resp}'")
            return float("nan")

    def measure_voltage(self) -> float:
        resp = self.query("MEAS:VOLT?")
        try:
            first = resp.split(",")[0]
            return float(first)
        except Exception:
            print(f"Warning: could not parse voltage from '{resp}'")
            return float("nan")

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