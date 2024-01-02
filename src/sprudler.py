# Test with:
# ./pyboard.py -d /dev/serial/by-id/usb-1a86_USB_Serial-if00-port0 sprudler.py
# Build with:
# ../../micropython/mpy-cross/build/mpy-cross -march=xtensa -O3 ./sprudler.py
# Upload with:
# ./pyboard.py -d /dev/serial/by-id/usb-1a86_USB_Serial-if00-port0 -f cp sprudler.py :sprudler.py
# (beware, `import` prioritizes .py files over .mpy files)

import machine
import uasyncio
import time


# Setup servo

# define SERVO_PIN 2
# define SERVO_PWM_OPEN 50
# define SERVO_PWM_CLOSED 74
# define SERVO_PWM_ACTION 103

servo_pwm = machine.PWM(machine.Pin(SERVO_PIN), freq=50, duty=SERVO_PWM_CLOSED)
# servo_pwm.deinit()  # Workaround for broken PWM after soft-reset
# servo_pwm = machine.PWM(machine.Pin(SERVO_PIN), freq=50, duty=SERVO_PWM_CLOSED)


# Setup port extender

# define PORT_EXT_PIN_SCL 0
# define PORT_EXT_PIN_SDA 4
# define PORT_EXT_PIN_INT 5
# define PORT_EXT_I2C_FREQ 100000
# define PORT_EXT_I2C_ADDR 0b0111000
# define PORT_EXT_I2C_DFLT 0xFF

i2c = machine.I2C(
    scl=machine.Pin(PORT_EXT_PIN_SCL, machine.Pin.IN),
    sda=machine.Pin(PORT_EXT_PIN_SDA, machine.Pin.IN),
    freq=PORT_EXT_I2C_FREQ,
)
i2c_buf = bytearray(1)  # static buffer

# Setup button callback

# define BUTTON_LEFT 0
# define BUTTON_MID 1
# define BUTTON_RIGHT 2

btn_changed_flag = uasyncio.ThreadSafeFlag()
btn_pressed_mask = 0
btn_released_mask = 0


def button_callback(_pin):
    global btn_pressed_mask
    global btn_released_mask

    i2c.readfrom_into(PORT_EXT_I2C_ADDR, i2c_buf)
    btn_up_mask = i2c_buf[0] & 0x7
    # only buttons that were pressed are marked as now released
    btn_released_mask |= btn_up_mask & btn_pressed_mask
    btn_pressed_mask |= 0b111 ^ btn_up_mask  # same as ~btn_up_mask & 0x7

    btn_changed_flag.set()


ext_int = machine.Pin(PORT_EXT_PIN_INT, machine.Pin.IN)
ext_int.irq(trigger=machine.Pin.IRQ_FALLING, handler=button_callback)

# Setup LEDs
led_state = PORT_EXT_I2C_DFLT


def switch_leds(on_bits):
    global led_state

    led_state = (led_state & 0b11000111) | ((0b111 ^ on_bits) << 3)
    i2c_buf[0] = led_state
    i2c.writeto(PORT_EXT_I2C_ADDR, i2c_buf)


# Setup state

# define STATE_DEBUG -1
# define STATE_IDLE 0
# define STATE_ACTION 1
# define STATE_WAITING 2

state = STATE_IDLE
state_since = time.ticks_ms()
state_changed_event = uasyncio.Event()


def change_state(target_state):
    global state
    global state_since

    state = target_state
    state_since = time.ticks_ms()
    state_changed_event.set()
    state_changed_event.clear()


# Initial state
i2c.readfrom_into(PORT_EXT_I2C_ADDR, i2c_buf)
btn_up_mask = i2c_buf[0] & 0x7
if btn_up_mask == 0b111:  # no button pressed
    change_state(STATE_ACTION)
else:
    if btn_up_mask == 0b010:  # left and right button pressed
        import os

        try:
            os.remove("settings.cfg")
        except OSError:
            pass  # file does not exist

        switch_leds(111)
        time.sleep_ms(200)
        switch_leds(000)
        time.sleep_ms(200)
        switch_leds(111)
        time.sleep_ms(200)
        switch_leds(000)

        servo_pwm.duty(SERVO_PWM_OPEN)

        change_state(STATE_IDLE)
    else:  # middle button pressed
        change_state(STATE_DEBUG)

    # Wait until all buttons are unpressed
    while True:
        i2c.readfrom_into(PORT_EXT_I2C_ADDR, i2c_buf)
        btn_up_mask = i2c_buf[0] & 0x7
        if btn_up_mask == 0b111:  # no button pressed
            break

        time.sleep_ms(100)

    btn_pressed_mask = 0
    btn_released_mask = 0


# Coroutines


async def button_handler():
    global btn_pressed_mask
    global btn_released_mask
    global state
    global pump_dur_ms
    global strength

    while True:
        await btn_changed_flag.wait()

        if (1 << BUTTON_LEFT) & btn_released_mask & btn_pressed_mask:
            btn_pressed_mask &= ~(1 << BUTTON_LEFT)
            btn_released_mask &= ~(1 << BUTTON_LEFT)

            # print("Left button was pressed")

            if state == STATE_ACTION or state == STATE_WAITING:
                pump_dur_ms -= 200
            elif state == STATE_IDLE:
                if strength > 0:
                    strength -= 1
                    with open("settings.cfg", "wb") as f:
                        f.write(strength.to_bytes(1, "little"))
                        # kinda unclean but moving this into the led handler sucks
                        switch_leds(0b000)
                        await uasyncio.sleep_ms(300)
                        switch_leds(0b111)

        if (1 << BUTTON_MID) & btn_released_mask & btn_pressed_mask:
            btn_pressed_mask &= ~(1 << BUTTON_MID)
            btn_released_mask &= ~(1 << BUTTON_MID)

            # print("Middle button was pressed")

            if state == STATE_ACTION or state == STATE_WAITING:  # abort
                change_state(STATE_IDLE)
            elif state == STATE_DEBUG or state == STATE_IDLE:  # (re)start
                change_state(STATE_ACTION)

        if (1 << BUTTON_RIGHT) & btn_released_mask & btn_pressed_mask:
            btn_pressed_mask &= ~(1 << BUTTON_RIGHT)
            btn_released_mask &= ~(1 << BUTTON_RIGHT)

            # print("Right button was pressed")

            if state == STATE_ACTION or state == STATE_WAITING:
                pump_dur_ms += 200
            elif state == STATE_IDLE:
                if strength < len(strength_map) - 1:
                    strength += 1
                    with open("settings.cfg", "wb") as f:
                        f.write(strength.to_bytes(1, "little"))
                        # kinda unclean but moving this into the led handler sucks
                        switch_leds(0b000)
                        await uasyncio.sleep_ms(300)
                        switch_leds(0b111)


percentage_done = 0.0


async def led_handler():
    while True:
        while state == STATE_ACTION or state == STATE_WAITING:
            if percentage_done >= 0.99:
                switch_leds(0b111)
                break
            elif percentage_done >= 0.66:
                led_idx = 2
                bitmask = 0b111
            elif percentage_done >= 0.33:
                led_idx = 1
                bitmask = 0b011
            else:
                led_idx = 0
                bitmask = 0b001

            period = 15
            on_time = round((percentage_done - led_idx * 0.33) * 3 * period)
            off_time = period - on_time

            # print(f"ontime {on_time}/{off_time}  {percentage_done}")

            if off_time:
                switch_leds(bitmask >> 1)
                await uasyncio.sleep_ms(off_time)

            if on_time:
                switch_leds(bitmask)
                await uasyncio.sleep_ms(on_time)

        while state == STATE_DEBUG:
            switch_leds(0b111)
            if sta_if and sta_if.isconnected():
                break

            await uasyncio.sleep_ms(500)
            switch_leds(0b000)
            await uasyncio.sleep_ms(500)

        if state == STATE_IDLE:
            switch_leds(0b111)

        await state_changed_event.wait()


async def servo_handler():
    while True:
        if state == STATE_ACTION:
            servo_pwm.duty(SERVO_PWM_ACTION)
        elif state == STATE_WAITING:
            servo_pwm.duty(SERVO_PWM_CLOSED)
        elif state == STATE_IDLE or state == STATE_DEBUG:
            servo_pwm.duty(SERVO_PWM_OPEN)

        await state_changed_event.wait()


# maps strength to (number of pumps, pump duration)
strength_map = [
    (2, 1000),
    (2, 1200),
    (2, 1400),
    (3, 1000),
    (3, 1200),
    (3, 1400),
    (4, 1000),
    (4, 1200),
    (4, 1400),
    (5, 1000),
    (5, 1200),
    (5, 1400),
]
try:
    with open("settings.cfg", "rb") as f:
        strength = int.from_bytes(f.read(), "little")
except OSError:
    # print("No settings.cfg")
    strength = 1

# print(f"Loaded strength = {strength}")
assert strength >= 0 and strength < len(strength_map)

# define WAITING_DUR_MS 1600


async def action_timer():
    global pump_dur_ms
    global percentage_done

    while True:
        num_pumps, pump_dur_ms = strength_map[strength]
        pump = 0
        pumping_since = state_since
        while state == STATE_ACTION or state == STATE_WAITING:
            recalc_period_ms = 50
            if state == STATE_ACTION:
                deadline = time.ticks_add(state_since, pump_dur_ms)

                # `pump_dur_ms` may change mid loop, so we have to recalc
                while time.ticks_diff(deadline, time.ticks_ms()) > 0:
                    deadline = time.ticks_add(state_since, pump_dur_ms)
                    ms_action = (num_pumps - pump - 1) * pump_dur_ms
                    ms_waiting = (num_pumps - pump) * WAITING_DUR_MS
                    pumping_until = time.ticks_add(deadline, ms_action + ms_waiting)
                    percentage_done = time.ticks_diff(
                        time.ticks_ms(), pumping_since
                    ) / time.ticks_diff(pumping_until, pumping_since)

                    if state != STATE_ACTION:  # state might have changed
                        break

                    await uasyncio.sleep_ms(recalc_period_ms)

                if state == STATE_ACTION:  # state might have changed
                    change_state(STATE_WAITING)

            elif state == STATE_WAITING:
                deadline = time.ticks_add(state_since, WAITING_DUR_MS)

                # `pump_dur_ms` may change mid loop, so we have to recalc
                while time.ticks_diff(deadline, time.ticks_ms()) > 0:
                    ms_action = (num_pumps - pump - 1) * pump_dur_ms
                    ms_waiting = (num_pumps - pump - 1) * WAITING_DUR_MS
                    pumping_until = time.ticks_add(deadline, ms_action + ms_waiting)
                    percentage_done = time.ticks_diff(
                        time.ticks_ms(), pumping_since
                    ) / time.ticks_diff(pumping_until, pumping_since)

                    if state != STATE_WAITING:  # state might have changed
                        break

                    await uasyncio.sleep_ms(recalc_period_ms)

                if state == STATE_WAITING:  # state might have changed
                    pump += 1
                    if pump < num_pumps:
                        change_state(STATE_ACTION)
                    else:
                        change_state(STATE_IDLE)

        await state_changed_event.wait()


sta_if = None


async def delayed_setup():
    global sta_if
    import network

    # bug fix for https://github.com/micropython/micropython/issues/9226#issuecomment-1718269312
    network.WLAN(network.AP_IF).active(False)

    if state == STATE_DEBUG:
        try:
            with open("wifi_cfg.py") as f:
                exec(f.read())

            import webrepl

            sta_if = network.WLAN(network.STA_IF)
            sta_if.active(True)
            # print(f'Connecting to "{NETWORK_NAME}"')
            sta_if.connect(NETWORK_NAME, NETWORK_PASS)

            webrepl.start()

            while not sta_if.isconnected():
                await uasyncio.sleep_ms(250)

            # print(f"Got IP. Access to WebREPL via http://{sta_if.ifconfig()[0]}:8266")
        except OSError:
            pass
            # print("No wifi_cfg.py")


async def main():
    await uasyncio.gather(
        servo_handler(),  # run servo_handler first to start action asap
        button_handler(),
        led_handler(),
        action_timer(),
        delayed_setup(),
    )


uasyncio.run(main())
