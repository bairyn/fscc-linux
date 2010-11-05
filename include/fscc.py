import struct
import fcntl
import io
import os
import errno

IOCPARM_MASK = 0x7f
#IOC_NONE = 0x20000000
IOC_NONE = 0x00000000
IOC_WRITE = 0x40000000
IOC_READ = 0x80000000


def FIX(x):
    return struct.unpack("i", struct.pack("I", x))[0]


def _IO(x, y):
    return FIX(IOC_NONE | (x << 8) | y)


def _IOR(x, y, t):
    return FIX(IOC_READ | ((t & IOCPARM_MASK) << 16) | (x << 8) | y)


def _IOW(x, y, t):
    return FIX(IOC_WRITE | ((t & IOCPARM_MASK) << 16) | (x << 8) | y)


def _IOWR(x, y, t):
    return FIX(IOC_READ | IOC_WRITE | ((t & IOCPARM_MASK) << 16) | (x << 8) | y)

FSCC_IOCTL_MAGIC = 0x18

FSCC_GET_REGISTERS = _IOR(FSCC_IOCTL_MAGIC, 0, struct.calcsize("i"))
FSCC_SET_REGISTERS = _IOW(FSCC_IOCTL_MAGIC, 1, struct.calcsize("i"))
FSCC_FLUSH_TX = _IO(FSCC_IOCTL_MAGIC, 2)
FSCC_FLUSH_RX = _IO(FSCC_IOCTL_MAGIC, 3)
FSCC_ENABLE_APPEND_STATUS = _IO(FSCC_IOCTL_MAGIC, 4)
FSCC_DISABLE_APPEND_STATUS = _IO(FSCC_IOCTL_MAGIC, 5)

FSCC_UPDATE_VALUE = -2


class Port(io.FileIO):

    class Registers(object):
        register_names = ["FIFOT", "STAR", "CCR0", "CCR1", "CCR2", "BGR",
                          "SSR", "SMR", "TSR", "TMR", "RAR", "RAMR", "PPR",
                          "TCR", "VSTR", "IMR", "DPLLR", "FCR"]

        editable_register_names = [r for r in register_names if r not in ["STAR", "VSTR"]]

        def __init__(self, port=None):
            self.port = port
            self._clear_registers()

            for register in self.register_names:
                self._add_register(register)

        def __iter__(self):
            registers = [-1, -1, self._FIFOT, -1, -1, -1, self._STAR,
                         self._CCR0, self._CCR1, self._CCR2, self._BGR,
                         self._SSR, self._SMR, self._TSR, self._TMR, self._RAR,
                         self._RAMR, self._PPR, self._TCR, self._VSTR, -1,
                         self._IMR, self._DPLLR, self._FCR]

            for register in registers:
                yield register

        def _add_register(self, register):
            fget = lambda self: self._get_register(register)
            fset = lambda self, value: self._set_register(register, value)

            setattr(self.__class__, register, property(fget, fset, None, ""))

        def _get_register(self, register):
            self._clear_registers()
            setattr(self, "_%s" % register, FSCC_UPDATE_VALUE)
            self._get_registers()

            return getattr(self, "_%s" % register)

        def _set_register(self, register, value):
            self._clear_registers()
            setattr(self, "_%s" % register, value)
            self._set_registers()

        def _clear_registers(self):
            for register in self.register_names:
                setattr(self, "_%s" % register, -1)

        def _get_registers(self):
            if not self.port:
                return

            registers = list(self)

            buf = fcntl.ioctl(self.port, FSCC_GET_REGISTERS,
                              struct.pack("q" * len(registers), *registers))

            regs = struct.unpack("q" * len(registers), buf)

            for i, register in enumerate(registers):
                if register != -1:
                    self._set_register_by_index(i, regs[i])

        def _set_registers(self):
            if not self.port:
                return

            registers = list(self)

            fcntl.ioctl(self.port, FSCC_SET_REGISTERS,
                        struct.pack("q" * len(registers), *registers))

        def _set_register_by_index(self, index, value):
            data = [("FIFOT", 2), ("STAR", 6), ("CCR0", 7),
                    ("CCR1", 8), ("CCR2", 9), ("BGR", 10), ("SSR", 11),
                    ("SMR", 12), ("TSR", 13), ("TMR", 14), ("RAR", 15),
                    ("RAMR", 16), ("PPR", 17), ("TCR", 18), ("VSTR", 19),
                    ("IMR", 21), ("DPLLR", 22), ("FCR", 23)]

            for r, i in data:
                if i == index:
                    setattr(self, "_%s" % r, value)

        # Note: clears registers
        def import_from_file(self, import_file):
            import_file.seek(0, os.SEEK_SET)

            for line in import_file:
                if line[0] != "#":
                    d = line.split("=")
                    reg_name, reg_val = d[0].strip().upper(), d[1].strip()

                    if reg_val[0] == "0" and reg_val[1] in ["x", "X"]:
                        reg_val = int(reg_val, 16)
                    else:
                        reg_val = int(reg_val)

                    setattr(self, reg_name, reg_val)

        def export_to_file(self, export_file):
            for i, register_name in enumerate(self.editable_register_names):
                value = getattr(self, register_name)

                if value >= 0:
                    export_file.write("%s = 0x%08x\n" % (register_name, value))


    def __init__(self, file, mode, append_status=False):
        if not os.path.exists(file):
            raise IOError(errno.ENOENT, os.strerror(errno.ENOENT), file)

        io.FileIO.__init__(self, file, mode)

        self.registers = Port.Registers(self)
        self.append_status = append_status

    def flush_tx(self):
        fcntl.ioctl(self, FSCC_FLUSH_TX)

    def flush_rx(self):
        fcntl.ioctl(self, FSCC_FLUSH_RX)

    def _set_append_status(self, append_status):
        if append_status:
            fcntl.ioctl(self, FSCC_ENABLE_APPEND_STATUS)
        else:
            fcntl.ioctl(self, FSCC_DISABLE_APPEND_STATUS)

    append_status = property(fset=_set_append_status)

    def read(self, num_bytes):
        if num_bytes:
            return super(io.FileIO, self).read(num_bytes)
