#!/usr/bin/python

import fscc

if __name__ == '__main__':
    port = fscc.Port('/dev/fscc0', 'wb')

    port.CCR0 = 0x00000000
    port.CCR1 = 0x00000000
    port.CCR2 = 0x00000000

    port.set_registers()
