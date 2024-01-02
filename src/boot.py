import machine

machine.freq(160000000)
machine.PWM(machine.Pin(2), freq=50, duty=74)
