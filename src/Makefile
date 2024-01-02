# Sodastream Mod
DEV ?= /dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A10ML25U-if00-port0
# D1-mini
DEV ?= /dev/serial/by-id/usb-1a86_USB_Serial-if00-port0
# Micropython repo: https://github.com/micropython/micropython
MPY_CROSS ?= ../../micropython/micropython/mpy-cross/build/mpy-cross
PYBOARD ?= ../../micropython/micropython/tools/pyboard.py

build-and-upload: .upload.sprudler.mpy .upload.boot.py .upload.main.py .upload.webrepl_cfg.py .upload.wifi_cfg.py

shell:
	tio "${DEV}"

.upload.boot.py: boot.py
	"${PYBOARD}" -d "${DEV}" -f cp boot.py :
	touch .upload.boot.py

.upload.main.py: main.py
	"${PYBOARD}" -d "${DEV}" -f cp main.py :
	touch .upload.main.py

.upload.sprudler.mpy: sprudler.mpy
	"${PYBOARD}" -d "${DEV}" -f cp sprudler.mpy :
	touch .upload.sprudler.mpy

.upload.webrepl_cfg.py: webrepl_cfg.py
	"${PYBOARD}" -d "${DEV}" -f cp webrepl_cfg.py :
	touch .upload.webrepl_cfg.py

.upload.wifi_cfg.py: wifi_cfg.py
	"${PYBOARD}" -d "${DEV}" -f cp wifi_cfg.py :
	touch .upload.wifi_cfg.py

sprudler.mpy: sprudler.py Makefile
	cp sprudler.py .sprudler.gcc-in.py
	@echo "=> Reverting black formatting on preprocessor defines"
	sed -i "s/^# define/#define/" .sprudler.gcc-in.py
	@echo "=> Removing comments"
	sed -i "/^ *# /d" .sprudler.gcc-in.py
	@echo "=> Running preprocessor"
	gcc -E - < .sprudler.gcc-in.py > .sprudler.gcc-out.py
	@echo "=> Building byte code with mpy-cross"
	"${MPY_CROSS}" -march=xtensa -O3 ./.sprudler.gcc-out.py
	mv .sprudler.gcc-out.mpy sprudler.mpy
	@echo "=> Final size:"
	du -b sprudler.mpy

clean:
	rm -f .upload.boot.py .upload.main.py .upload.sprudler.mpy .upload.webrepl_cfg.py .upload.wifi_cfg.py sprudler.mpy .sprudler.gcc-in.py .sprudler.gcc-out.py .sprudler.gcc-out.mpy
